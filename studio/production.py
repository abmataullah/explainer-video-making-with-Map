"""Production scripts: the producer's document with sections, narration and visual directions.

Format it understands (Bangla or English labels, markdown marks are ignored):

    ডেঙ্গু ২০২৬: এক মাসে আট মাসের মৃত্যু ছাড়াল
    চ্যানেল: POLITICAL ANALYTICA | দৈর্ঘ্য: ৩-৪ মিনিট | ডেটা কাটঅফ: ২৪ সেপ্টেম্বর ২০২৬, DGHS

    অংশ ১: হুক (০:০০ - ০:২০)
    ন্যারেশন:
    ...spoken text...
    ভিজ্যুয়াল:
    - B-roll: ...
    - HUD counter ...

    ভয়েসওভারের জন্য শুধু ন্যারেশন      <- skipped (same words again)
    চার্ট ডেটা শিট                       <- kept as reference data for the planner

The narration of each section is cut into beats of one or two sentences (about 5-10 s of speech),
and every beat gets its own visual. That is what keeps the screen moving while the voice runs.
"""
import json
import re

BN_DIG = "০১২৩৪৫৬৭৮৯"


def en_digits(s):
    return re.sub(r"[০-৯]", lambda m: str(BN_DIG.index(m.group(0))), s or "")


def _strip(line):
    t = line.strip()
    t = re.sub(r"^#+\s*", "", t)
    t = t.replace("**", "").replace("__", "").strip()
    return t


SECTION_RE = re.compile(r"^(?:অংশ|পর্ব|সেকশন|section|part|segment)\s*[-#]?\s*([০-৯0-9]+)\s*[:：.\-–]?\s*(.*)$", re.I)
NARR_RE = re.compile(r"^(?:ন্যারেশন|ন্যারেশান|বর্ণনা|ভয়েস ?ওভার|ভয়েসওভার|narration|voice ?over|vo)\s*[:：]\s*(.*)$", re.I)
VIS_RE = re.compile(r"^(?:ভিজ্যুয়াল|ভিজুয়াল|দৃশ্য|visuals?|on[- ]screen)\s*[:：]\s*(.*)$", re.I)
VO_ONLY_RE = re.compile(r"(শুধু ন্যারেশন|কেবল ন্যারেশন|narration only|voice ?over only|vo only)", re.I)
DATA_RE = re.compile(r"(ডেটা শিট|ডাটা শিট|তথ্য শিট|data ?sheet|chart data|সূত্র তালিকা)", re.I)
TIME_RE = re.compile(r"\(\s*[০-৯0-9]{1,2}:[০-৯0-9]{2}\s*[-–—]\s*[০-৯0-9]{1,2}:[০-৯0-9]{2}\s*\)")
META = {
    "channel": re.compile(r"(?:চ্যানেল|channel)\s*[:：]\s*([^|।\n]+)", re.I),
    "duration": re.compile(r"(?:দৈর্ঘ্য|সময়কাল|duration|length)\s*[:：]\s*([^|\n]+)", re.I),
    "cutoff": re.compile(r"(?:ডেটা কাটঅফ|ডাটা কাটঅফ|তথ্য হালনাগাদ|কাটঅফ|data cut-?off|cut-?off|data as of)\s*[:：]\s*([^|\n]+)", re.I),
    "title": re.compile(r"^(?:শিরোনাম|টাইটেল|title)\s*[:：]\s*(.+)$", re.I),
}
BULLET_RE = re.compile(r"^(?:[-•*▪►●◦–]|[০-৯0-9]{1,2}[.)])\s*")


def is_production(text):
    t = text or ""
    return bool(re.search(r"(ন্যারেশন|narration)\s*[:：]", t, re.I)) and bool(
        re.search(r"(ভিজ্যুয়াল|ভিজুয়াল|visuals?)\s*[:：]", t, re.I))


def parse_production(text):
    lines = (text or "").replace("\r\n", "\n").split("\n")
    doc = {"title": "", "channel": "", "duration": "", "cutoff": "", "sections": [], "data": ""}
    cur, mode, data_lines, skipping = None, None, [], False
    for raw in lines:
        line = _strip(raw)
        if not line:
            continue
        low = line.lower()
        if DATA_RE.search(line) and len(line) < 80:
            mode, skipping = "data", False
            continue
        if mode == "data":
            data_lines.append(line)
            continue
        if VO_ONLY_RE.search(line) and len(line) < 80:
            skipping = True
            continue
        m = SECTION_RE.match(line)
        if m:
            skipping = False
            title = TIME_RE.sub("", m.group(2)).strip(" :-–")
            tm = TIME_RE.search(m.group(2))
            cur = {"n": len(doc["sections"]) + 1, "title": title, "time": tm.group(0).strip("() ") if tm else "",
                   "narration": [], "visuals": []}
            doc["sections"].append(cur)
            mode = None
            continue
        if skipping:
            continue
        found_meta = False
        for k in ("channel", "duration", "cutoff"):
            mm = META[k].search(line)
            if mm and not doc[k] and (cur is None or len(line) < 120):
                doc[k] = mm.group(1).strip(" *")
                found_meta = True
        if found_meta and cur is None:
            continue
        mt = META["title"].match(line)
        if mt and cur is None:
            doc["title"] = mt.group(1).strip()
            continue
        m = NARR_RE.match(line)
        if m:
            mode = "narr"
            if m.group(1).strip():
                cur and cur["narration"].append(m.group(1).strip())
            continue
        m = VIS_RE.match(line)
        if m:
            mode = "vis"
            if m.group(1).strip() and cur:
                cur["visuals"].append(m.group(1).strip())
            continue
        if cur is None:
            if not doc["title"] and len(line) < 140:
                doc["title"] = line
            continue
        if mode == "narr":
            cur["narration"].append(re.sub(r"^[\"“”]|[\"“”]$", "", line))
        elif mode == "vis":
            cur["visuals"].append(BULLET_RE.sub("", line))
    for s in doc["sections"]:
        s["narration"] = " ".join(s["narration"]).strip()
    doc["sections"] = [s for s in doc["sections"] if s["narration"]]
    doc["data"] = "\n".join(data_lines)[:6000]
    return doc


SENT_RE = re.compile(r"[^।!?\n]+(?:[।!?]+|$)")


def beats(text, lo=60, hi=150):
    """One or two sentences per beat, about 5-10 seconds of Bangla speech."""
    sents = [x.strip() for x in SENT_RE.findall(text or "") if x.strip()]
    out = []
    for s in sents:
        if len(s) > hi * 1.4:          # a very long sentence: split at a comma
            parts, buf = [], ""
            for piece in re.split(r"(?<=[,，;])\s+", s):
                if buf and len(buf) + len(piece) > hi:
                    parts.append(buf); buf = piece
                else:
                    buf = (buf + " " + piece).strip()
            if buf:
                parts.append(buf)
        else:
            parts = [s]
        for p in parts:
            if out and len(out[-1]) < lo and len(out[-1]) + len(p) <= hi:
                out[-1] += " " + p
            else:
                out.append(p)
    if len(out) > 1 and len(out[-1]) < 35:
        out[-2] += " " + out.pop()
    return out


def beat_list(doc):
    items = []
    for s in doc["sections"]:
        bs = beats(s["narration"])
        for j, b in enumerate(bs):
            items.append({"text": b, "section": s["title"], "sec": s["n"], "first": j == 0, "k": j, "of": len(bs)})
    return items


PLAN_PROMPT = """You are the motion-graphics director of a Bangla news-analysis channel ({channel}).
The producer wrote a production script: for every section there is fixed narration and a list of visual
directions. The narration is already recorded. It has been cut into numbered beats (5-10 s each).
Give every beat ONE visual, following that section's directions in order. Spread the directions over
the section's beats; a direction may cover two beats, and a beat may combine a card with a lower third,
a tag flash or a footnote.

Video title: {title}
Data cutoff note: {cutoff}

{sections}

Reference data sheet from the producer (use these numbers and sources, nothing else):
{data}

Return ONLY a JSON array with exactly {n} objects, beat 1 first. Allowed objects (omit unused keys):
- {{"type":"broll","broll":"English stock search, 2-4 words that NAME THE PLACE, e.g. Dhaka hospital ward","headline":""}}
- {{"type":"title","title":"","subtitle":""}}   (only for the very first beat, if the directions open on a title)
- {{"type":"versus","versus":{{"title":"","a":{{"label":"","value":"","note":""}},"b":{{"label":"","value":"","note":""}}}}}}
- {{"type":"tiles","tiles_title":"","tiles":[{{"label":"","value":"","note":""}}]}}   (2-4 tiles)
- {{"type":"stat","stat":{{"value":"","label":"","source":""}}}}
- {{"type":"chart","chart":{{"kind":"bar|hbar|line|area|donut|pie|stacked|lollipop|waffle","title":"","unit":"",
    "data":[{{"label":"","value":0,"partial":false}}],"source":""}},"note":"footnote text"}}
  ("partial": true marks an incomplete period, e.g. the running year; it is drawn striped with an asterisk)
- {{"type":"spread","mode":"heat","focus":["BGD"],"level":1,"effect":"disease","heat":{{"Dhaka":0}},"unit":"","headline":""}}
  (division heat map of Bangladesh; keys are division names in English)
- {{"type":"spread","mode":"regions","focus":["BGD"],"effect":"disease|flood|conflict|protest","regions":["district"],"origin":"district"}}
- {{"type":"map","focus":["ISO3"],"highlight":{{"ISO3":"red"}},"points":[{{"name":"","lat":0,"lon":0}}],"headline":""}}
- {{"type":"timeline","headline":"","events":[{{"date":"","text":""}}]}}
- {{"type":"bullets","headline":"","bullets":[""]}}
- {{"type":"blocks","blocks":{{"title":"","items":[{{"icon":"one emoji","title":"","text":""}}]}}}}
- {{"type":"pyramid","pyramid":{{"title":"","levels":["bottom level","...","top level"]}}}}
- {{"type":"checklist","checklist":{{"title":"","items":[""]}}}}
- {{"type":"quote","quote":"","by":""}}
- {{"type":"compare","compare":{{"a":"","b":"","rows":[{{"label":"","a":"","b":""}}]}}}}
Extra keys any beat may carry: "lower":[{{"name":"","role":""}}] (lower-third name card), "tag_flash":"SHORT TAG",
"note":"footnote", "headline":"max 6 words", "sfx":["heartbeat","siren","alarm","rain"] (only if it fits).

Rules:
- On-screen text in Bangla, except tags the producer wrote in English (keep them as written).
- Numbers only from the narration or the data sheet, copied exactly. Never invent values.
- A direction that asks for B-roll gets a "broll" beat. Every section should have at least one broll beat
  unless its directions say otherwise; never two broll beats in a row; never put a "broll" key on other types.
- Never use the same card type on more than two beats in a row.
- A counter or "A vs B" comparison is "versus"; three numbers side by side are "tiles".
- A division heat map is "spread" with mode "heat". A question-mark animation can be a "stat" with value "?".
- For an end card or closing line use "quote" or "bullets"; the channel end card is added automatically.
  Never put the channel name or "subscribe" on a card.
- A heat map needs a real value for every division from the data sheet or narration. Without those values use
  "hbar" of the numbers you do have, or "spread" mode "regions".
- A "chart" should not cover more than two beats in a row: after the chart, move to the next direction.
"""


def plan_prompt(doc, items, channel):
    parts = []
    for s in doc["sections"]:
        parts.append(f"SECTION {s['n']}: {s['title']}" + (f" ({s['time']})" if s["time"] else ""))
        parts.append("Visual directions:")
        parts += [f"  - {v}" for v in s["visuals"]] or ["  - (none given)"]
        parts.append("Beats:")
        for i, it in enumerate(items):
            if it["sec"] == s["n"]:
                parts.append(f"  {i + 1}. {it['text']}")
        parts.append("")
    return PLAN_PROMPT.format(channel=channel or "the channel", title=doc.get("title", ""), cutoff=doc.get("cutoff", ""),
                              sections="\n".join(parts), data=doc.get("data") or "(none)", n=len(items))


# ---- without Gemini: a plain plan from keywords in the directions ----
BROLL_WORDS = [
    (r"হাসপাতাল|ওয়ার্ড|রোগী|hospital|ward|patient", "Dhaka hospital patients"),
    (r"মশা|এডিস|mosquito|aedes", "Bangladesh mosquito"),
    (r"রাস্তা|শহর|ঢাকা|street|city", "Dhaka street crowd"),
    (r"বৃষ্টি|বর্ষা|জলাবদ্ধ|rain|monsoon", "Dhaka rain street"),
    (r"গ্রাম|কৃষক|village|farmer", "Bangladesh village"),
    (r"বন্যা|flood", "Bangladesh flood"),
    (r"সংসদ|সরকার|parliament|government", "Dhaka parliament"),
]


def rule_plan(doc, items):
    out = []
    for it in items:
        sec = next(s for s in doc["sections"] if s["n"] == it["sec"])
        vis = sec["visuals"] or [""]
        d = vis[min(len(vis) - 1, int(it["k"] * len(vis) / max(1, it["of"])))]
        low = d.lower()
        sc = {}
        if re.search(r"b-?roll|বি-?রোল|ফুটেজ|footage|stock", low) and (not out or out[-1].get("type") != "broll"):
            q = next((qq for pat, qq in BROLL_WORDS if re.search(pat, d + " " + it["text"], re.I)), "Dhaka street crowd")
            sc.update(type="broll", broll=q, focus=["BGD"])
        else:
            sc.update(type="map", focus=["BGD"], highlight={"BGD": "red"})
        out.append(sc)
    return out


def _nums_in(text):
    t = en_digits(text or "")
    t = re.sub(r"(?<=\d),(?=\d{2,3})", "", t)
    vals = set()
    for m in re.finditer(r"\d+(?:\.\d+)?", t):
        vals.add(float(m.group(0)))
    # "৬৯ হাজার ১৪৯" and "তিন লাখ" style amounts
    for m in re.finditer(r"(\d+)\s*হাজার(?:\s*(\d+))?", t):
        vals.add(float(m.group(1)) * 1000 + float(m.group(2) or 0))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*লাখ", t):
        vals.add(float(m.group(1)) * 100000)
    return vals


def _known(v, pool):
    try:
        x = float(en_digits(str(v)).replace(",", "").strip().rstrip("%"))
    except Exception:
        return True          # not a plain number (a label, "?"): nothing to check
    return any(abs(x - p) < 0.51 for p in pool)


def _with_shares(pool):
    """Add every percentage that follows from two numbers in the script, and its complement."""
    base = sorted(x for x in pool if x > 0)[:60]
    out = set(pool)
    for a in base:
        for b in base:
            if a < b:
                p = a / b * 100
                out.update({round(p), round(p, 1), round(100 - p), round(100 - p, 1)})
    for x in list(pool):
        if 0 < x < 100:
            out.add(100 - x)
    return out


TYPES = {"title", "map", "globe", "spread", "choropleth", "chart", "broll", "stat", "bullets", "quote", "timeline",
         "compare", "tiles", "versus", "pyramid", "blocks", "checklist"}


def clean_plan(plan, items, doc=None, log=None):
    """Keep the director's plan honest: narration from the script, no broll keys on graphics, no broll twice
    in a row, and no number on screen that the script or the data sheet does not contain."""
    pool = _nums_in(" ".join(it["text"] for it in items) + "\n" + ((doc or {}).get("data") or ""))
    say = log or (lambda m: None)
    shares = _with_shares(pool)
    out = []
    for i, (v, it) in enumerate(zip(plan, items)):
        v = dict(v) if isinstance(v, dict) else {"type": "map"}
        v["narration"] = it["text"]
        v["section"] = it["section"]
        t = v.get("type") or "map"
        if t not in TYPES:
            # a name card or anything unknown: footage of the place, with the card on top
            prev_broll = bool(out and out[-1].get("type") == "broll")
            t = v["type"] = "map" if prev_broll else "broll"
            if t == "broll":
                v["broll"] = v.get("broll") or "Dhaka hospital doctor"
        if t != "broll":
            v.pop("broll", None)
        elif not str(v.get("broll") or "").strip() or (out and out[-1].get("type") == "broll"):
            v["type"] = "map"
        v.setdefault("focus", ["BGD"])
        ch = v.get("chart") if v.get("type") == "chart" else None
        if isinstance(ch, dict):
            pp = shares if ch.get("kind") in ("donut", "pie", "waffle") or "%" in str(ch.get("unit", "")) else pool
            bad = [d.get("value") for d in ch.get("data") or [] if isinstance(d, dict) and not _known(d.get("value"), pp)]
            if bad:
                say(f"Beat {i + 1}: chart dropped, these numbers are not in your script or data sheet: {bad[:4]}")
                v = {"type": "map", "focus": ["BGD"], "highlight": {"BGD": "red"}, "narration": it["text"],
                     "section": it["section"], "headline": ch.get("title") or v.get("headline", "")}
        if v.get("type") == "spread" and v.get("mode") == "heat" and isinstance(v.get("heat"), dict):
            bad = [x for x in v["heat"].values() if not _known(x, pool)]
            if bad:
                say(f"Beat {i + 1}: heat-map values {bad[:4]} are not in your script, showing the regions without numbers")
                v["regions"] = list(v["heat"].keys())
                v["mode"] = "regions"
                v.pop("heat", None)
        if v.get("type") == "tiles":
            v["tiles"] = [t for t in v.get("tiles") or [] if isinstance(t, dict) and _known(t.get("value"), shares)] or None
            if not v["tiles"]:
                v["type"] = "map"
        if v.get("type") == "stat" and isinstance(v.get("stat"), dict) and re.search(
                r"subscribe|সাবস্ক্রাইব|analytica|অ্যানালিটিকা", json.dumps(v["stat"], ensure_ascii=False), re.I):
            v = {"type": "broll", "broll": "Dhaka city skyline", "narration": it["text"], "section": it["section"], "focus": ["BGD"]}
        if isinstance(v.get("quote"), str):
            v["quote"] = {"text": v["quote"], "by": v.pop("by", "")}
        if v.get("type") == "map" and not (v.get("highlight") or v.get("points") or v.get("arrows")):
            v["highlight"] = {c: "red" for c in v.get("focus") or ["BGD"]}
        if v.get("type") == "spread" and v.get("mode") == "heat":
            v["level"] = int(v.get("level") or 1)
            h = v.get("heat")
            if not isinstance(h, dict) or not h:
                v["type"] = "map"
        out.append(v)
    return out
