import subprocess
"""Geo Explainer Studio - local web app.

topic -> Gemini script (scene JSON) -> edit -> Gemini TTS per scene -> Remotion render.
Run with ..\\..\\envs\\tts\\Scripts\\python.exe server.py  ->  http://localhost:7870
"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, threading, time, traceback, uuid, wave, webbrowser

from flask import Flask, jsonify, request, send_file, send_from_directory, abort

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # geo-explainer/
PARENT = os.path.dirname(ROOT)                    # My video avatar creation/
PROJECTS = os.path.join(ROOT, "projects")
OUTPUTS = os.path.join(ROOT, "outputs")
MUSIC = os.path.join(ROOT, "music")
PUBLIC_RENDER = os.path.join(ROOT, "public", "_render")
SETTINGS_FILE = os.path.join(ROOT, "settings.json")
PORT = 7870
for d in (PROJECTS, OUTPUTS, MUSIC, PUBLIC_RENDER):
    os.makedirs(d, exist_ok=True)

DEFAULTS = {
    "gemini_key": "",
    "script_model": "gemini-3.8-flash",
    "script_fallback": "gemini-flash-latest, gemini-3.7-flash, gemini-3.5-flash, gemini-3.1-flash-lite, gemini-pro-latest",
    "tts_model": "gemini-2.5-pro-preview-tts",
    "tts_fallback": "gemini-3.8-flash-tts, gemini-3.1-flash-tts-preview",
    "voice": "Charon",
    "style": "Read like a calm, authoritative Bangladeshi documentary narrator. Clear, measured pace.",
    "channel": "GEO EXPLAINER",
    "channels": ["GEO EXPLAINER", "POLITICAL ANALYTICA", "TRUE NEWS"],
    "font": "'Hind Siliguri','Noto Sans Bengali','Nirmala UI',Arial,sans-serif",
    "font_text": "Hind Siliguri",
    "font_caption": "Hind Siliguri",
    "look": "classic",
    "pexels_key": "",
    "pixabay_key": "",
    "broll_region": "auto",
    "broll_strict": True,
    "recent_music": [],
    "local_model": "gemma4:latest",
    "bg": "navy",
    "text_scale": 1.25,
    "music_library": r"E:\Organized\Audio\royality free music",
    "music_volume": 0.1,
    "output_dir": "",
}
VOICES = ["Charon", "Kore", "Puck", "Fenrir", "Aoede", "Zephyr", "Leda", "Orus", "Callirrhoe", "Autonoe",
          "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina", "Erinome", "Algenib", "Rasalgethi",
          "Laomedeia", "Achernar", "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird",
          "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat"]


def out_dir():
    """Where finished videos go: the folder chosen in Settings, or geo-explainer/outputs."""
    d = (load_settings().get("output_dir") or "").strip()
    if d:
        try:
            os.makedirs(d, exist_ok=True)
            if os.access(d, os.W_OK):
                return d
        except Exception:
            pass
    return OUTPUTS


def load_settings():
    s = dict(DEFAULTS)
    if os.path.exists(SETTINGS_FILE):
        try:
            s.update(json.load(open(SETTINGS_FILE, encoding="utf-8")))
        except Exception:
            pass
    return s


def save_settings(s):
    json.dump(s, open(SETTINGS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def gemini_key():
    k = load_settings().get("gemini_key", "").strip()
    if not k:
        kf = os.path.join(PARENT, "gemini_key.txt")
        if os.path.exists(kf):
            k = open(kf, encoding="utf-8").read().strip()
    k = k or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not k:
        raise RuntimeError("No Gemini API key. Open Settings and paste your key from aistudio.google.com.")
    return k


def client():
    from google import genai
    return genai.Client(api_key=gemini_key())


EXTRA_SCRIPT = ["gemini-flash-latest", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-pro-latest"]
EXTRA_TTS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview", "gemini-3.8-flash-lite-tts"]


def is_busy(e):
    m = str(e)
    return any(x in m for x in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL", "overloaded", "high demand", "deadline"))


def model_list(first, rest, extra=()):
    out = [first] + [m.strip() for m in (rest or "").split(",")] + list(extra)
    return [m for i, m in enumerate(out) if m and m not in out[:i]]


def safe_name(n):
    n = re.sub(r"[^\w\-\u0980-\u09FF ]+", "", (n or "").strip()).strip().replace(" ", "_")
    return n[:60] or "untitled"


def proj_dir(name):
    d = os.path.join(PROJECTS, safe_name(name))
    os.makedirs(os.path.join(d, "audio"), exist_ok=True)
    return d


def load_project(name):
    f = os.path.join(proj_dir(name), "project.json")
    if not os.path.exists(f):
        return None
    return json.load(open(f, encoding="utf-8"))


def save_project(p):
    p["name"] = safe_name(p.get("name"))
    p["scenes"] = [normalize_scene(sc) for sc in p.get("scenes", []) if isinstance(sc, dict)]
    p["updated"] = time.strftime("%Y-%m-%d %H:%M")
    f = os.path.join(proj_dir(p["name"]), "project.json")
    json.dump(p, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return p


# ---------------------------------------------------------------- jobs --
JOBS = {}


def start_job(kind, fn, *args):
    jid = uuid.uuid4().hex[:10]
    job = {"id": jid, "kind": kind, "status": "running", "progress": 0, "log": [], "result": None, "error": None}
    JOBS[jid] = job

    def run():
        try:
            job["result"] = fn(job, *args)
            job["status"] = "done"
            job["progress"] = 100
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
            job["log"].append(traceback.format_exc())
    threading.Thread(target=run, daemon=True).start()
    return jid


def log(job, msg):
    job["log"].append(time.strftime("%H:%M:%S ") + msg)
    if len(job["log"]) > 300:
        del job["log"][:-300]  # trim in place: one-click shares this list across steps


# -------------------------------------------------------------- script --
SCRIPT_PROMPT = """You write scripts for a geopolitics explainer video channel (style: maps, arrows,
highlighted countries, clear narration). Write in {langname}.

Topic / notes from the producer:
---
{source}
---

Target length: about {minutes} minutes of narration (~{words} words total), {scenes} scenes.

Return ONLY a JSON object, no markdown fences, in exactly this shape:
{{
  "title": "video title",
  "mood": "one of: humanitarian | war | spy | power-games | trade-strategy | history | tension | mystery | hopeful | environment | sombre",
  "scenes": [
    {{
      "type": "title" | "map" | "globe" | "spread" | "choropleth" | "chart" | "broll" | "stat" | "bullets" | "quote" | "timeline" | "compare",
      "narration": "what the narrator says in this scene (2-4 sentences, spoken style)",
      "headline": "short on-screen headline, max 6 words",
      "focus": ["ISO3", ...],              // countries the camera should frame, ISO 3166 alpha-3
      "highlight": {{"ISO3": "red|amber|teal|blue|violet|green|yellow|pink|grey"}},
      "arrows": [{{"from": "ISO3", "to": {{"lon": 93.5, "lat": 19.4}}, "label": "short", "color": "yellow"}}],  // each end is an ISO3 string OR a {{"lon","lat"}} object
      "points": [{{"name": "city/port name", "lat": 0.0, "lon": 0.0}}],
      "title": "only for type title", "subtitle": "only for type title",
      "stat": {{"value": "number as shown", "label": "what it measures", "source": "publisher, year"}},
      "bullets": ["max 4 short items"],
      "quote": {{"text": "exact quote", "by": "speaker, year"}},
      "events": [{{"date": "1971", "text": "max 5 words"}}],          // only for timeline, 3-5 events
      "compare": {{"a": "ISO3", "b": "ISO3", "rows": [{{"label": "Population", "a": "value", "b": "value"}}], "source": "publisher, year"}},
      "chart": {{"kind": "bar|hbar|lollipop|line|area|stacked|donut|pie|waffle|treemap", "title": "chart title", "unit": "% or unit",
                "data": [{{"label": "2020", "value": 12.5, "group": "series name, only for several series"}}], "source": "publisher, year"}},
      "values": {{"ISO3": 12.5}}, "unit": "unit of the values", "source": "publisher, year",   // only for choropleth
      "broll": "English stock-footage search, 2-4 words",     // only for broll
      "effect": "flood|conflict|fire|drought|disease|protest|control|cyclone",  // only for spread
      "regions": ["districts or divisions named in the narration, English names"], "origin": "place where it starts",
      "mode": "regions|spread", "level": 2, "legend": "short label", "track": [[lon, lat], ...],  // track only for a cyclone path
      "sfx": ["effect names from: rain, storm, thunder, water, flood, waves, wind, war, explosions_far, explosion, bomb, gunshot, gunfire, fire, protest, crowd_angry, cheer, press, march, war_drums, war_horn, fanfare, siren, police, alarm, helicopter, heartbeat, drumroll, riser, impact, clock, drone"]
    }}
  ]
}}

Rules:
- First scene is type "title". Last scene wraps up the argument.
- Most scenes should be "map". Every scene needs "focus" (the map stays on screen behind cards).
- Use real ISO alpha-3 codes (BGD, MMR, IND, CHN, LKA, PAK, USA, RUS ...).
- Use "points" only for well-known places whose coordinates you are sure of. Write point names,
  headlines, arrow labels, bullets and card text in {langname} too (e.g. কক্সবাজার, not Cox's Bazar).
- Use "stat" only for figures that are well established; always give the source. Never invent numbers.
  If unsure of a figure, use a map scene instead.
- Use "quote" only for real, verifiable quotes. Otherwise do not use it.
- Use "timeline" when the story has 3-5 key dates. Dates must be accurate.
- Use "compare" for two countries side by side, 2-4 rows, only with well-established figures and a source.
- "globe" is a rotating 3D globe (same focus/highlight/arrows/points as map). Use it for the opening map or to
  show where a place sits in the world. At most 2.
- "choropleth" shades countries by a number ("values" per ISO3 + "unit" + "source"). Only with well-established
  figures and a source.
- "chart" is a real chart. 3-8 data points, labels in {langname}. line/area = change over time, bar = a few values,
  hbar/lollipop = ranking, donut/pie/waffle = shares of a whole, treemap = many shares, stacked = parts over time.
  Only well-established figures with a source; never invent numbers. At most 2 charts.
- "spread" animates something spreading INSIDE a country: flood, fighting, protests, disease, drought, fire,
  territory control, or a cyclone "track". "focus" = that country. "regions" = only districts/divisions the
  narration or the producer's notes actually name, in English, in the order they are hit; "origin" = where it
  starts. If no areas are named, leave "regions" empty and use "mode": "spread" from the origin. level 2 = districts
  (Bangladesh), 1 = divisions/provinces. Never invent affected areas.
- "sfx" (optional, any scene): at most 2 effects that match what the narration describes (rain for rain,
  gunfire for shooting, fanfare or cheer for a victory). Leave it out when nothing fits.
- "broll" search words must name the place and its people: "Dhaka street crowd", "Bangladeshi farmer paddy field",
  "Chittagong port ships", "Saudi Arabia Riyadh street", "Arab market Cairo". Never generic Western scenes.
- "broll" is real stock footage for human, ground-level moments (people, ports, ships, protests, factories,
  parliament). 1-3 per video, never two in a row. Still give "focus".
- Aim for variety: mostly map and globe scenes, plus at most one each of stat, timeline, compare, bullets,
  choropleth, up to 2 charts and up to 3 broll.
- Narration must be natural spoken {langname}. {langrule}
- Omit keys that a scene does not use.
"""


COUNTRIES = json.load(open(os.path.join(HERE, "countries.json"), encoding="utf-8"))


def _norm(k):
    return re.sub(r"[\s.'’\-]+", "", str(k).strip().lower())


_LOOK = {}
for _c in COUNTRIES:
    for _n in [_c["iso"], _c["iso2"], _c["name"], _c["bn"]] + _c.get("aliases", []):
        if _n:
            _LOOK.setdefault(_norm(_n), _c["iso"])
_ISO = {c["iso"] for c in COUNTRIES}
COLOR_BN = {"লাল": "red", "কমলা": "amber", "ফিরোজা": "teal", "নীল": "blue", "বেগুনি": "violet",
            "সবুজ": "green", "হলুদ": "yellow", "গোলাপি": "pink", "ধূসর": "grey", "orange": "amber",
            "purple": "violet", "gray": "grey", "cyan": "teal"}


def to_iso(name):
    """'Bangladesh' / 'বাংলাদেশ' / 'bd' / 'BGD' -> 'BGD'. Unknown -> original text."""
    if not isinstance(name, str):
        return name
    k = name.strip()
    if k.upper() in _ISO:
        return k.upper()
    return _LOOK.get(_norm(k), k)


def to_color(c):
    c = str(c or "red").strip()
    return COLOR_BN.get(c, COLOR_BN.get(c.lower(), c.lower() if not c.startswith("#") else c))


NUMPAIR = re.compile(r"^\s*[\[{(]?\s*(?:lon\w*\s*[:=]\s*)?(-?\d+(?:\.\d+)?)\s*,\s*(?:lat\w*\s*[:=]\s*)?(-?\d+(?:\.\d+)?)\s*[\]})]?\s*$", re.I)


def norm_end(e):
    """Arrow endpoint -> 'ISO3' or {lon,lat}. Accepts '{93.5, 19.4}' strings (lon,lat)."""
    if isinstance(e, dict):
        try:
            return {"lon": float(e.get("lon")), "lat": float(e.get("lat"))}
        except Exception:
            return None
    if isinstance(e, (list, tuple)) and len(e) == 2:
        return {"lon": float(e[0]), "lat": float(e[1])}
    if isinstance(e, str):
        m = NUMPAIR.match(e)
        if m:
            return {"lon": float(m.group(1)), "lat": float(m.group(2))}
        return to_iso(e)
    return None


BN2EN = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
CHART_KINDS = {"bar", "hbar", "lollipop", "line", "area", "stacked", "donut", "pie", "waffle", "treemap"}


def _num(v):
    return float(re.sub(r"[^\d.\-]", "", str(v).translate(BN2EN)))


def normalize_scene(sc):
    sc.setdefault("type", "map")
    ch = sc.get("chart")
    if isinstance(ch, dict):
        data = []
        for r in ch.get("data") or []:
            if not isinstance(r, dict):
                continue
            try:
                item = {"label": str(r.get("label", "")), "value": _num(r.get("value"))}
            except Exception:
                continue
            if r.get("group"):
                item["group"] = str(r["group"])
            if r.get("partial") in (True, "true", 1, "1", "yes"):
                item["partial"] = True
            data.append(item)
        ch["data"] = data[:16]
        if ch.get("kind") not in CHART_KINDS:
            ch["kind"] = "bar"
    if isinstance(sc.get("values"), dict):
        vals = {}
        for k, v in sc["values"].items():
            try:
                vals[to_iso(k)] = _num(v)
            except Exception:
                pass
        sc["values"] = vals
        if sc.get("type") == "choropleth" and not sc.get("focus"):
            sc["focus"] = list(vals.keys())[:12]
    sc["focus"] = [to_iso(str(x)) for x in (sc.get("focus") or []) if str(x).strip()]
    h = sc.get("highlight")
    if isinstance(h, list):
        h = {x: c for x, c in zip(h, ["red", "amber", "teal", "blue", "violet"] * 3)}
    if isinstance(h, dict):
        sc["highlight"] = {to_iso(k): to_color(v) for k, v in h.items() if str(k).strip()}
    if isinstance(sc.get("compare"), dict):
        sc["compare"]["a"] = to_iso(sc["compare"].get("a", ""))
        sc["compare"]["b"] = to_iso(sc["compare"].get("b", ""))
    arrows = []
    for a in sc.get("arrows") or []:
        f, t = norm_end(a.get("from")), norm_end(a.get("to"))
        if f and t:
            a["from"], a["to"] = f, t
            arrows.append(a)
    if arrows or "arrows" in sc:
        sc["arrows"] = arrows
    pts = []
    for p in sc.get("points") or []:
        try:
            pts.append({"name": p.get("name", ""), "lat": float(p["lat"]), "lon": float(p["lon"])})
        except Exception:
            pass
    if pts or "points" in sc:
        sc["points"] = pts
    return sc


def parse_json_loose(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < 0:
        raise RuntimeError("Gemini did not return JSON:\n" + text[:500])
    return json.loads(text[a:b + 1])


def gen_script(job, req):
    s = load_settings()
    lang = req.get("lang", "bn")
    minutes = float(req.get("minutes") or 3)
    words = int(minutes * (80 if lang == "bn" else 140))
    prompt = SCRIPT_PROMPT.format(
        langname="Bangla (Bangladeshi standard, Bengali script)" if lang == "bn" else "English",
        langrule=("Use the danda (।). Write numbers and years in Bangla words or Bangla digits so the voice reads them well."
                  if lang == "bn" else "Short sentences."),
        source=(req.get("topic", "") + "\n" + req.get("notes", "")).strip(),
        minutes=minutes, words=words, scenes=max(6, int(minutes * 5)))
    from google.genai import types
    c = client()
    plain = types.GenerateContentConfig(response_mime_type="application/json")
    grounded = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    attempts = []
    if req.get("grounded"):
        attempts += [(m, grounded, True) for m in model_list(s["script_model"], "")]
    attempts += [(m, plain, False) for m in model_list(s["script_model"], s["script_fallback"], EXTRA_SCRIPT)]
    last, data, r = None, None, None
    waits = [15, 30, 60]
    for rnd in range(len(waits) + 1):
        busy_only = True
        for model, cfg, g in attempts:
            try:
                log(job, f"Writing script with {model}" + (" + Google Search..." if g else "..."))
                job["progress"] = 20
                r = c.models.generate_content(model=model, contents=prompt, config=cfg)
                data = parse_json_loose(r.text)
                break
            except Exception as e:
                last = e
                short = str(e).split(".")[0][:120]
                log(job, f"{model} failed: {short}")
                if not is_busy(e):
                    busy_only = False
        if data is not None:
            break
        if rnd < len(waits):
            log(job, f"Google's servers are busy. Waiting {waits[rnd]} s and trying again (round {rnd + 2} of {len(waits) + 1})...")
            time.sleep(waits[rnd])
        # after grounded attempts failed once, drop them for the next rounds
        attempts = [a for a in attempts if not a[2]] or attempts
    if data is None:
        raise RuntimeError("Gemini is overloaded right now (all models busy for over 2 minutes). "
                           f"Wait a few minutes and press the button again. Last error: {str(last)[:200]}")
    sources = []
    try:
        gm = r.candidates[0].grounding_metadata
        for ch in (gm.grounding_chunks or []):
            if ch.web:
                sources.append({"title": ch.web.title, "uri": ch.web.uri})
    except Exception:
        pass
    data["scenes"] = [normalize_scene(sc) for sc in data.get("scenes", []) if isinstance(sc, dict)]
    name = safe_name(req.get("name") or data.get("title") or req.get("topic"))
    p = load_project(name) or {}
    p.update({"name": name, "title": data.get("title", ""), "mood": data.get("mood", ""), "lang": lang, "topic": req.get("topic", ""),
              "scenes": data.get("scenes", []), "sources": sources})
    save_project(p)
    log(job, f"Script ready: {len(p['scenes'])} scenes.")
    return {"project": p["name"]}


# ----------------------------------------------------------------- tts --
BREAK = re.compile(r"\[break\s*:\s*(\d+)\s*\]", re.I)
SENT = re.compile(r"[^।.!?\n]+[।.!?]*", re.UNICODE)


def tts_chunk(c, models, text, voice, style):
    last = None
    for wait in (0, 10, 30, 60):
        if wait:
            if last is not None and "quota" in str(last).lower():
                break
            time.sleep(wait)
        for model in models:
            try:
                return tts_chunk_one(c, model, text, voice, style)
            except Exception as e:
                last = e
                msg = str(e)
                if is_busy(e) or "404" in msg or "NOT_FOUND" in msg or "NoneType" in msg:
                    continue
                raise
    if "quota" in str(last).lower():
        raise RuntimeError("Your Gemini voice quota is used up for today (free tier). It resets at 1 PM Bangladesh time "
                           "(midnight Pacific). Until then: use '🎧 I have my own audio', or add billing in AI Studio. "
                           "Finished scenes are kept.")
    raise RuntimeError(f"Gemini voice is overloaded right now. Wait a few minutes and press the button again "
                       f"(finished scenes are kept). Last error: {str(last)[:200]}")


TTS_FORMAT = "v3"  # bump to force re-voicing when the prompt format changes


def tts_prompt(text, style):
    """Gemini TTS has no separate style field (system instructions are rejected),
    so the direction goes in the prompt. Plain 'style + text' makes the model read
    the direction aloud. Labelled sections keep it as direction only."""
    if not style:
        return text
    return ("# DIRECTOR'S NOTES (do not read aloud)\n" + style.strip() +
            "\n\n# TRANSCRIPT (read only this, exactly)\n" + text)


def tts_chunk_one(c, model, text, voice, style):
    from google.genai import types
    prompt = tts_prompt(text, style)
    for attempt in range(3):
        try:
            resp = c.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
            return resp.candidates[0].content.parts[0].inline_data.data
        except Exception as e:
            msg = str(e)
            if attempt < 1 and is_busy(e):
                time.sleep(5)
                continue
            raise


def estimate_cues(text, dur, lead=0.0):
    sents = [x.strip() for x in SENT.findall(text) if x.strip()]
    # split long sentences at commas so captions stay short
    parts = []
    for s_ in sents:
        if len(s_) > 90 and "," in s_:
            bits = [b.strip() for b in s_.split(",") if b.strip()]
            parts += [b + "," for b in bits[:-1]] + [bits[-1]]
        else:
            parts.append(s_)
    if not parts:
        return []
    w = [max(len(p_), 1) for p_ in parts]
    tot, t, out = sum(w), lead, []
    for p_, wi in zip(parts, w):
        d = dur * wi / tot
        out.append({"start": round(t, 2), "end": round(t + d, 2), "text": p_})
        t += d
    return out


def find_pauses(x, sr=24000, min_len=0.16):
    """Silent stretches in int16 speech -> list of (start, end) seconds."""
    import numpy as np
    hop = int(sr * 0.02)
    n = len(x) // hop
    if n < 5:
        return []
    fr = x[:n * hop].astype(np.float32).reshape(n, hop)
    rms = np.sqrt((fr ** 2).mean(axis=1)) + 1e-6
    thr = max(np.percentile(rms, 20) * 2.5, rms.max() * 0.03)
    quiet = rms < thr
    out, start = [], None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * 0.02 >= min_len:
                out.append((start * 0.02, i * 0.02))
            start = None
    return out


def split_caption_parts(text, max_len=70):
    """Sentences, with long ones cut at commas or word gaps into ~2-line captions."""
    sents = [x.strip() for x in SENT.findall(text) if x.strip()]
    parts = []
    for s_ in sents:
        if len(s_) <= max_len:
            parts.append(s_)
            continue
        pieces = [b.strip() for b in re.split(r"(?<=[,;:])\s+", s_) if b.strip()]
        for pc in pieces:
            if len(pc) <= max_len:
                parts.append(pc)
                continue
            words = pc.split()
            n = -(-len(pc) // max_len)
            per = len(pc) / n
            cur, out = [], []
            for w_ in words:
                cur.append(w_)
                if len(" ".join(cur)) >= per and len(out) < n - 1:
                    out.append(" ".join(cur)); cur = []
            if cur:
                out.append(" ".join(cur))
            parts += out
    return parts


def aligned_cues(text, speech, offset):
    """Caption cues timed to the real voice track.
    Text length is mapped onto *speaking* time (pauses excluded), so dramatic
    pauses do not throw the timing off; each boundary then snaps to a nearby pause."""
    parts = split_caption_parts(text)
    dur = len(speech) / 24000
    if not parts or dur <= 0:
        return []
    pauses = find_pauses(speech)
    lead = pauses[0][1] if pauses and pauses[0][0] < 0.05 else 0.0
    tail = pauses[-1][0] if pauses and pauses[-1][1] > dur - 0.05 else dur
    inner = [p for p in pauses if p[0] > lead + 0.05 and p[1] < tail - 0.05]

    def voiced_to_real(v):
        t, left = lead, v
        for a, b in inner:
            seg = a - t
            if left <= seg:
                return t + left
            left -= seg
            t = b
        return min(t + left, tail)

    voiced_total = (tail - lead) - sum(b - a for a, b in inner)
    w = [max(len(p), 1) for p in parts]
    tot = sum(w)
    bounds, acc, used = [], 0, set()
    for wi in w[:-1]:
        acc += wi
        est = voiced_to_real(voiced_total * acc / tot)
        best, bd = None, 0.9
        for j, (a, b) in enumerate(inner):
            m = (a + b) / 2
            dist = 0 if a - 0.1 <= est <= b + 0.1 else abs(m - est)
            if j not in used and dist < bd and (not bounds or m > bounds[-1] + 0.4):
                best, bd = j, dist
        if best is not None:
            used.add(best)
            bounds.append((inner[best][0] + inner[best][1]) / 2)
        else:
            bounds.append(max(est, bounds[-1] + 0.4) if bounds else est)
    edges = [lead] + bounds + [tail]
    return [{"start": round(offset + edges[i], 2), "end": round(offset + edges[i + 1], 2), "text": parts[i]}
            for i in range(len(parts))]


def synth_scene(c, s, p, i, sc):
    import numpy as np
    text = (sc.get("narration") or "").strip()
    audio_rel = f"audio/s{i:02d}.wav"
    out = os.path.join(proj_dir(p["name"]), audio_rel)
    if not text:
        sc["audio"], sc["duration"], sc["cues"] = None, float(sc.get("duration") or 3), []
        return
    voice = p.get("voice") or s["voice"]
    style = sc.get("style") or p.get("style") or s["style"]
    chunks, breaks, pos = [], [], 0
    for m in BREAK.finditer(text):
        chunks.append(text[pos:m.start()]); breaks.append(int(m.group(1))); pos = m.end()
    chunks.append(text[pos:]); breaks.append(0)
    waves = []
    for ch, br in zip(chunks, breaks):
        if ch.strip():
            pcm = tts_chunk(c, model_list(s["tts_model"], s.get("tts_fallback"), EXTRA_TTS), ch.strip(), voice, style)
            waves.append(np.frombuffer(pcm, dtype=np.int16))
        if br:
            waves.append(np.zeros(int(24000 * br / 1000), dtype=np.int16))
    lead = np.zeros(int(24000 * 0.25), dtype=np.int16)
    tail = np.zeros(int(24000 * 0.45), dtype=np.int16)
    audio = np.concatenate([lead] + waves + [tail])
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(audio.tobytes())
    # captions: align each [break]-separated chunk separately (its timing is exact)
    cues, t = [], 0.25
    for ch, br, wv in zip_chunks(chunks, breaks, waves):
        cues += aligned_cues(ch, wv, t)
        t += len(wv) / 24000 + br / 1000
    sc["audio"] = audio_rel
    sc["audio_src"] = "tts"
    sc["duration"] = round(len(audio) / 24000, 2)
    sc["cues"] = cues
    sc["audio_hash"] = hash_scene(sc, voice, style)


def zip_chunks(chunks, breaks, waves):
    """Pair each non-empty text chunk with its synthesized wave (silence waves are separate)."""
    import numpy as np
    out, wi = [], 0
    for ch, br in zip(chunks, breaks):
        if ch.strip():
            out.append((ch.strip(), br, waves[wi]))
            wi += 1
        elif br:
            out.append(("", br, np.zeros(0, dtype=np.int16)))
        if br:
            wi += 1  # skip the silence wave appended after this chunk
    return out


def hash_scene(sc, voice, style):
    import hashlib
    return hashlib.md5(f"{sc.get('narration')}|{voice}|{style}|{TTS_FORMAT}".encode("utf-8")).hexdigest()


def gen_audio(job, name, only=None, force=False):
    s = load_settings()
    p = load_project(name)
    if not p:
        raise RuntimeError("project not found")
    c = client()
    idxs = [only] if only is not None else list(range(len(p["scenes"])))
    for n, i in enumerate(idxs):
        sc = p["scenes"][i]
        voice = p.get("voice") or s["voice"]
        style = sc.get("style") or p.get("style") or s["style"]
        if sc.get("audio_src") == "upload" and not force:
            log(job, f"Scene {i + 1}: uses your uploaded audio, skipping")
            job["progress"] = int(100 * (n + 1) / len(idxs))
            continue
        existing = sc.get("audio") and os.path.exists(os.path.join(proj_dir(name), sc["audio"]))
        if not force and existing and sc.get("audio_hash") == hash_scene(sc, voice, style):
            log(job, f"Scene {i + 1}: unchanged, keeping audio")
        else:
            log(job, f"Scene {i + 1}/{len(p['scenes'])}: generating voice ({voice})...")
            synth_scene(c, s, p, i, sc)
            save_project(p)
        job["progress"] = int(100 * (n + 1) / len(idxs))
    save_project(p)
    total = sum(float(x.get("duration") or 0) for x in p["scenes"])
    log(job, f"Audio ready. Total length {int(total // 60)}:{int(total % 60):02d}")
    return {"project": name}


# -------------------------------------------------------------- render --
# Benchmarked on this PC: GPU (--gl=angle) was 33% slower; 12-14 threads = default speed.
RENDER_FLAGS = [f"--concurrency={max(2, min(12, (os.cpu_count() or 8) - 4))}"]


def music_credits():
    f = os.path.join(MUSIC, "credits.json")
    try:
        return json.load(open(f, encoding="utf-8"))
    except Exception:
        return {}


MOOD_TRACK = {"humanitarian": "Heartbreaking.mp3", "war": "Impact Lento.mp3", "spy": "Covert Affair.mp3",
              "power-games": "Hidden Agenda.mp3", "trade-strategy": "Sovereign Quarter.mp3",
              "history": "Echoes of Time v2.mp3", "tension": "Crypto.mp3", "mystery": "Unanswered Questions.mp3",
              "hopeful": "Floating Cities.mp3", "environment": "Lightless Dawn.mp3", "sombre": "Ossuary 6 - Air.mp3"}
DEFAULT_TRACK = "Hidden Agenda.mp3"


USER_MOODS = [(r"tension|suspense|thriller|countdown|dark|battle|epic|war|drum|chase|action", "tension"),
              (r"sad|sorrow|emotional|piano|grief|global.?warming", "sombre"),
              (r"cosmic|drift|ambient|space|mystery|mysterious", "mystery"),
              (r"hope|inspir|uplift|bright|happy", "hopeful")]


def sync_user_music(job=None):
    """Bring the producer's own licensed library (Settings > music_library) into the music list.
    MP3 is copied, WAV-only tracks are turned into 320k MP3, zips are opened into music/_lib. Their own
    tracks carry no credit line. Returns {file: mood}."""
    import zipfile
    lib = (load_settings().get("music_library") or "").strip()
    if not lib or not os.path.isdir(lib):
        return {}
    cr = music_credits()
    unz = os.path.join(MUSIC, "_lib")
    audio = (".mp3", ".wav", ".m4a", ".aiff", ".flac")
    for root, dirs, files in os.walk(lib):
        dirs[:] = [d for d in dirs if d != "__MACOSX"]
        for f in files:
            if f.lower().endswith(".zip"):
                dst = os.path.join(unz, os.path.splitext(f)[0])
                if os.path.isdir(dst):
                    continue
                try:
                    with zipfile.ZipFile(os.path.join(root, f)) as z:
                        names = [n for n in z.namelist() if n.lower().endswith(audio) and "__MACOSX" not in n
                                 and not os.path.basename(n).startswith("._")]
                        if names and not any(os.path.splitext(os.path.basename(n))[0] + ".mp3" in os.listdir(MUSIC) for n in names):
                            os.makedirs(dst, exist_ok=True)
                            for n in names:
                                open(os.path.join(dst, os.path.basename(n)), "wb").write(z.read(n))
                        else:
                            os.makedirs(dst, exist_ok=True)
                except Exception:
                    pass
    found = {}
    for base in (lib, unz):
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d != "__MACOSX"]
            for f in files:
                stem, ext = os.path.splitext(f)
                if f.startswith("._") or ext.lower() not in audio:
                    continue
                if ext.lower() == ".mp3" or stem not in found:
                    found[stem] = os.path.join(root, f)
    ff = shutil.which("ffmpeg")
    out, changed = {}, False
    for stem, src in found.items():
        fn = stem + ".mp3"
        dst = os.path.join(MUSIC, fn)
        if not os.path.exists(dst):
            try:
                if src.lower().endswith(".mp3"):
                    shutil.copyfile(src, dst)
                elif ff:
                    subprocess.run([ff, "-y", "-loglevel", "error", "-i", src, "-b:a", "320k", dst], check=True, timeout=300)
                else:
                    continue
                if job is not None:
                    log(job, f"Added your track: {stem}")
            except Exception:
                continue
        mood = next((m for pat, m in USER_MOODS if re.search(pat, stem, re.I)), "tension")
        if cr.get(fn, {}).get("mood") != mood or not cr.get(fn, {}).get("user"):
            cr[fn] = {"user": True, "mood": mood, "title": stem, "from": src}
            changed = True
        out[fn] = mood
    if changed:
        json.dump(cr, open(os.path.join(MUSIC, "credits.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return out


def pick_music(p, job=None):
    """Tension-first music: the producer's own library first, then a pool per mood, rotating so
    consecutive videos do not share a track."""
    try:
        mine = sync_user_music(job)
    except Exception:
        mine = {}
    have = set(os.listdir(MUSIC))
    mood = str(p.get("mood") or "").strip().lower()
    want = {"war": "tension", "power-games": "tension", "spy": "tension", "trade-strategy": "tension",
            "humanitarian": "sombre", "history": "sombre", "environment": "tension"}.get(mood, mood or "tension")
    pool = [t for t, m in sorted(mine.items()) if m == want and t in have and 'short' not in t.lower()]
    if not pool:
        pool = [t for t in MUSIC_POOLS.get(mood) or MUSIC_POOLS["tension"] if t in have]
    if not pool:
        pool = [t for t in MUSIC_POOLS["tension"] if t in have] or sorted(f for f in have if f.endswith(".mp3"))
    if not pool:
        return None
    st = load_settings()
    recent = st.get("recent_music") or []
    fresh = [t for t in pool if t not in recent] or pool
    t = fresh[int(hashlib.md5((p.get("name") or "").encode()).hexdigest(), 16) % len(fresh)]
    st["recent_music"] = ([t] + [x for x in recent if x != t])[:6]
    save_settings(st)
    if job is not None:
        log(job, f"Music: {os.path.splitext(t)[0]} (mood '{mood or 'tension'}', not used in your last videos)")
    return t


def credit_text(music_file):
    """YouTube-description credit for a track (Kevin MacLeod tracks need it: CC BY 4.0)."""
    c = music_credits().get(music_file)
    if c is None or c.get("user"):
        return None          # the producer's own upload: no credit line added
    title = c.get("title") or os.path.splitext(music_file)[0]
    author = c.get("author", "Kevin MacLeod (incompetech.com)")
    lic = c.get("license", "Licensed under Creative Commons: By Attribution 4.0\nhttps://creativecommons.org/licenses/by/4.0/")
    return f"Music: {title} by {author}\n{lic}"


def node_exe():
    return shutil.which("node") or r"C:\Program Files\nodejs\node.exe"


# ============================================================ fonts --
FONT_DIRS = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
             os.path.join(ROOT, "fonts")]
FAVOURITE_FONTS = ["Hind Siliguri", "Kalpurush", "Li MadanMohan", "Purno", "Noto Sans Bengali", "Noto Serif Bengali",
                   "Baloo Da 2", "Tiro Bangla", "Galada", "Mina", "SolaimanLipi", "Nirmala UI"]
_FONTS = None


def font_catalog(rescan=False):
    """Every installed font that really contains Bangla letters (Unicode, not Bijoy/ANSI).
    Drop extra .ttf files into geo-explainer/fonts to add them."""
    global _FONTS
    if _FONTS is not None and not rescan:
        return _FONTS
    from fontTools.ttLib import TTFont
    os.makedirs(os.path.join(ROOT, "fonts"), exist_ok=True)
    fams = {}
    for d in FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith((".ttf", ".otf", ".ttc")):
                continue
            path = os.path.join(d, f)
            try:
                t = TTFont(path, lazy=True, fontNumber=0)
                cmap = t.getBestCmap() or {}
                if 0x0995 not in cmap or 0x09CD not in cmap:
                    t.close(); continue
                nm = t["name"]
                fam = (nm.getDebugName(16) or nm.getDebugName(1) or "").strip()
                sub = (nm.getDebugName(17) or nm.getDebugName(2) or "").strip().lower()
                t.close()
            except Exception:
                continue
            if not fam or "italic" in sub or "oblique" in sub:
                continue
            e = fams.setdefault(fam, {})
            if sub == "bold":
                e.setdefault("bold", path)
            elif sub in ("regular", "book", "normal", "roman", ""):
                e.setdefault("regular", path)
            else:
                e.setdefault(sub, path)
    out = []
    for fam, e in fams.items():
        reg = e.get("regular") or e.get("medium") or next(iter(e.values()))
        out.append({"family": fam, "regular": reg, "bold": e.get("bold") or e.get("semibold") or reg})
    rank = lambda x: next((i for i, n in enumerate(FAVOURITE_FONTS) if n.lower() in x["family"].lower()), 99)
    out.sort(key=lambda x: (rank(x), x["family"].lower()))
    _FONTS = out
    return out


def font_entry(family):
    fams = font_catalog()
    return next((f for f in fams if f["family"] == family), None) or \
        next((f for f in fams if (family or "").lower() in f["family"].lower()), None) or (fams[0] if fams else None)


# ============================================================ R charts --
CHARTS_R = os.path.join(HERE, "charts.R")


def rscript():
    exe = shutil.which("Rscript")
    if exe:
        return exe
    found = sorted(glob.glob(r"C:\Program Files\R\R-*\bin\Rscript.exe"))
    return found[-1] if found else None


TEXT_SCALE = {"k": 1.25}
BG_RED = {"on": False}


def render_chart(job, sc, i, look, lang, font, vertical):
    """Draw the chart in R as an animated PNG sequence. Returns (folder, frame count) under public/_render."""
    ch = sc.get("chart") or {}
    if not ch.get("data"):
        return None
    R = rscript()
    if not R:
        log(job, "R is not installed, chart scenes show as maps.")
        return None
    w, h = (980, 1000) if vertical else (1640, 780)
    spec = {"kind": ch.get("kind", "bar"), "data": ch["data"], "unit": ch.get("unit", ""), "lang": lang,
            "look": look, "font_regular": font["regular"] if font else "", "font_bold": font["bold"] if font else "",
            "w": w, "h": h, "frames": 66, "v": 3, "scale": round(float(TEXT_SCALE.get("k", 1.25)), 2)}
    if BG_RED.get("on"):
        spec["accent"] = "#ffc233"
    key = hashlib.md5(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:14]
    cache = os.path.join(ROOT, "cache", "charts")
    os.makedirs(cache, exist_ok=True)
    fdir = os.path.join(cache, key)
    frames = sorted(glob.glob(os.path.join(fdir, "f*.png")))
    if len(frames) < spec["frames"]:
        jf = os.path.join(cache, key + ".json")
        json.dump(spec, open(jf, "w", encoding="utf-8"), ensure_ascii=False)
        log(job, f"Scene {i + 1}: animating the {spec['kind']} chart in R (about 15 s)...")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run([R, CHARTS_R, jf, fdir], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600, creationflags=flags)
        frames = sorted(glob.glob(os.path.join(fdir, "f*.png")))
        if r.returncode != 0 or not frames:
            log(job, f"Chart in scene {i + 1} failed in R: {(r.stderr or r.stdout)[-240:]}")
            return None
    dst = os.path.join(PUBLIC_RENDER, f"chart{i:02d}")
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(fdir, dst)
    return f"_render/chart{i:02d}", len(frames)


# ============================================================ B-roll --
BROLL_CACHE = os.path.join(PARENT, "assets", "broll_cache")
_STOP = {"a", "an", "the", "of", "in", "on", "at", "and", "with", "for", "to", "from", "by", "shot", "footage",
         "cinematic", "wide", "close", "view", "scene", "aerial", "4k", "hd"}


def pexels_key():
    k = (load_settings().get("pexels_key") or "").strip()
    if not k:
        try:
            k = json.load(open(os.path.join(PARENT, "app_settings.json"), encoding="utf-8-sig")).get("pexels_key", "")
        except Exception:
            k = ""
    return k


def pixabay_key():
    k = (load_settings().get("pixabay_key") or "").strip()
    if not k:
        try:
            k = json.load(open(os.path.join(PARENT, "app_settings.json"), encoding="utf-8-sig")).get("pixabay_key", "")
        except Exception:
            k = ""
    return k


def fetch_broll(job, query, vertical, used, need, region="global", strict=True):
    """Footage from the scene's own country (see broll_region.py). Returns (local path, label) or None."""
    try:
        import stock                      # studio/stock.py (Pexels / Pixabay search)
    except ImportError:
        if PARENT not in sys.path:
            sys.path.insert(0, PARENT)
        from pipeline import stock
    import broll_region as BR
    got = BR.find_broll(query, region, root=ROOT, stock=stock, pexels_key=pexels_key(), pixabay_key=pixabay_key(),
                        used=used, need=need, orientation="portrait" if vertical else "landscape", strict=strict,
                        log=lambda m: log(job, m))
    if not got and vertical:       # tall stock footage of Bangladesh is rare: a landscape clip is cropped to fit
        got = BR.find_broll(query, region, root=ROOT, stock=stock, pexels_key=pexels_key(), pixabay_key=pixabay_key(),
                            used=used, need=need, orientation="landscape", strict=strict, log=lambda m: log(job, m))
    if not got:
        return None
    src, label, remote = got
    if not remote:
        return src, label
    prov, r = src
    os.makedirs(BROLL_CACHE, exist_ok=True)
    path = os.path.join(BROLL_CACHE, f"{prov}_{r['id']}.mp4")
    try:
        if not os.path.exists(path) or os.path.getsize(path) < 10000:
            stock.download(r["file"], path)
    except Exception as e:
        log(job, f"B-roll download failed: {str(e)[:100]}")
        return None
    try:
        slug = (r.get("url") or "").rstrip("/").split("/")[-1][:80] or f"{prov}_{r['id']}"
        keep_dir = os.path.join(ROOT, "broll", region if region else "global")
        os.makedirs(keep_dir, exist_ok=True)
        keep = os.path.join(keep_dir, re.sub(r"[^\w\-]", "_", slug) + ".mp4")
        if not os.path.exists(keep):
            shutil.copyfile(path, keep)
    except Exception:
        pass
    return path, label


# ============================================================ exports --
def _ts(t, srt=True):
    h, m, s_ = int(t // 3600), int(t % 3600 // 60), t % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(s_):02d},{int(round((s_ % 1) * 1000)) % 1000:03d}"
    return f"{h}:{m:02d}:{int(s_):02d}" if h else f"{m}:{int(s_):02d}"


def write_extras(job, p, props, out, credit, lang):
    """SRT captions + a YouTube description file with chapters, sources and music credit."""
    try:
        intro = 2.6 if (props.get("intro") and props.get("channel")) else 0.0
        t, n, srt, chapters = intro, 1, [], []
        for sc in props["scenes"]:
            for c in sc.get("cues") or []:
                srt.append(f"{n}\n{_ts(t + c['start'])} --> {_ts(t + c['end'])}\n{c['text']}\n")
                n += 1
            head = (sc.get("title") if sc.get("type") == "title" else
                    sc.get("headline") or (sc.get("chart") or {}).get("title")) or ""
            if head and (not chapters or t - chapters[-1][0] >= 10):
                chapters.append([t, head.strip()])
            t += float(sc.get("duration") or 5)
        base = os.path.splitext(out)[0]
        if srt:
            open(base + ".srt", "w", encoding="utf-8").write("\n".join(srt))
        lines = [p.get("title") or "", ""]
        if len(chapters) >= 3:
            chapters[0][0] = 0.0
            lines += ["অধ্যায়:" if lang == "bn" else "Chapters:"] + [f"{_ts(a, False)} {b}" for a, b in chapters] + [""]
        src = []
        for sc in props["scenes"]:
            for k in ("stat", "compare", "chart"):
                v = (sc.get(k) or {}).get("source")
                if v:
                    src.append(v)
            if sc.get("type") == "choropleth" and sc.get("source"):
                src.append(sc["source"])
        src += [x.get("uri") for x in p.get("sources") or [] if x.get("uri")]
        if src:
            lines += ["সূত্র:" if lang == "bn" else "Sources:"] + [f"- {x}" for x in dict.fromkeys(src)] + [""]
        if credit:
            lines += [credit, ""]
        lines += [x for x in props.get("credits_extra") or []]
        open(base + "_YOUTUBE.txt", "w", encoding="utf-8").write("\n".join(lines))
        log(job, "Saved captions (.srt) and a YouTube description with chapters (_YOUTUBE.txt) next to the video.")
    except Exception as e:
        log(job, f"Could not write the extra files: {e}")


def make_thumbnail(job, props_file, out, props):
    try:
        intro = 2.6 if (props.get("intro") and props.get("channel")) else 0.0
        frame = int((intro + 1.2) * 30)
        cli = os.path.join(ROOT, "node_modules", "@remotion", "cli", "remotion-cli.js")
        thumb = os.path.splitext(out)[0] + "_thumbnail.jpg"
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run([node_exe(), cli, "still", "src/index.jsx", "Explainer", thumb, f"--props={props_file}",
                            f"--frame={frame}", "--image-format=jpeg", "--jpeg-quality=92"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=flags, timeout=300)
        if r.returncode == 0:
            log(job, "Thumbnail saved (_thumbnail.jpg).")
    except Exception as e:
        log(job, f"Thumbnail skipped: {e}")


# ============================================================ boundaries inside a country --
ADM_DIR = os.path.join(ROOT, "data", "adm")
BGD_BN = {"Bagerhat": "বাগেরহাট", "Bandarban": "বান্দরবান", "Barguna": "বরগুনা", "Barisal": "বরিশাল", "Bhola": "ভোলা",
          "Bogra": "বগুড়া", "Brahamanbaria": "ব্রাহ্মণবাড়িয়া", "Chandpur": "চাঁদপুর", "Chittagong": "চট্টগ্রাম",
          "Chuadanga": "চুয়াডাঙ্গা", "Comilla": "কুমিল্লা", "Cox's Bazar": "কক্সবাজার", "Dhaka": "ঢাকা", "Dinajpur": "দিনাজপুর",
          "Faridpur": "ফরিদপুর", "Feni": "ফেনী", "Gaibandha": "গাইবান্ধা", "Gazipur": "গাজীপুর", "Gopalganj": "গোপালগঞ্জ",
          "Habiganj": "হবিগঞ্জ", "Jamalpur": "জামালপুর", "Jessore": "যশোর", "Jhalokati": "ঝালকাঠি", "Jhenaidah": "ঝিনাইদহ",
          "Joypurhat": "জয়পুরহাট", "Khagrachhari": "খাগড়াছড়ি", "Khulna": "খুলনা", "Kishoreganj": "কিশোরগঞ্জ",
          "Kurigram": "কুড়িগ্রাম", "Kushtia": "কুষ্টিয়া", "Lakshmipur": "লক্ষ্মীপুর", "Lalmonirhat": "লালমনিরহাট",
          "Madaripur": "মাদারীপুর", "Magura": "মাগুরা", "Manikganj": "মানিকগঞ্জ", "Maulvibazar": "মৌলভীবাজার",
          "Meherpur": "মেহেরপুর", "Munshiganj": "মুন্সীগঞ্জ", "Mymensingh": "ময়মনসিংহ", "Naogaon": "নওগাঁ", "Narail": "নড়াইল",
          "Narayanganj": "নারায়ণগঞ্জ", "Narsingdi": "নরসিংদী", "Natore": "নাটোর", "Nawabganj": "চাঁপাইনবাবগঞ্জ",
          "Netrakona": "নেত্রকোনা", "Nilphamari": "নীলফামারী", "Noakhali": "নোয়াখালী", "Pabna": "পাবনা", "Panchagarh": "পঞ্চগড়",
          "Patuakhali": "পটুয়াখালী", "Pirojpur": "পিরোজপুর", "Rajbari": "রাজবাড়ী", "Rajshahi": "রাজশাহী", "Rangamati": "রাঙ্গামাটি",
          "Rangpur": "রংপুর", "Satkhira": "সাতক্ষীরা", "Shariatpur": "শরীয়তপুর", "Sherpur": "শেরপুর", "Sirajganj": "সিরাজগঞ্জ",
          "Sunamganj": "সুনামগঞ্জ", "Sylhet": "সিলেট", "Tangail": "টাঙ্গাইল", "Thakurgaon": "ঠাকুরগাঁও"}
REGION_ALIAS = {"chattogram": "chittagong", "ctg": "chittagong", "cumilla": "comilla", "barishal": "barisal", "bogura": "bogra",
                "jashore": "jessore", "chapainawabganj": "nawabganj", "chapainababganj": "nawabganj",
                "brahmanbaria": "brahamanbaria", "moulvibazar": "maulvibazar", "netrokona": "netrakona",
                "jhalakathi": "jhalokati", "jhalokathi": "jhalokati", "khagrachari": "khagrachhari", "coxsbazar": "coxsbazar",
                "laxmipur": "lakshmipur", "narshingdi": "narsingdi", "rangamati hill": "rangamati"}


def _round_geom(c):
    if isinstance(c, (list, tuple)) and c and isinstance(c[0], (int, float)):
        return [round(c[0], 3), round(c[1], 3)]
    return [_round_geom(x) for x in c]


def _signed_area(r):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1])) / 2


def _d3_wind(geom):
    """d3-geo reads polygons as spherical: the outer ring must be clockwise, holes anticlockwise.
    GeoJSON files use the opposite order, which d3 would draw as 'the whole world except this area'."""
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    fixed = []
    for poly in polys:
        rings = []
        for k, ring in enumerate(poly):
            a = _signed_area(ring)
            rings.append(ring[::-1] if (k == 0 and a > 0) or (k > 0 and a < 0) else ring)
        fixed.append(rings)
    return {"type": geom["type"], "coordinates": fixed[0] if geom["type"] == "Polygon" else fixed}


def _ring_centroid(r):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
        k = x0 * y1 - x1 * y0
        a += k; cx += (x0 + x1) * k; cy += (y0 + y1) * k
    if abs(a) < 1e-12:
        return [sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r)], 0
    return [cx / (3 * a), cy / (3 * a)], abs(a) / 2


def adm_data(iso, level, job=None):
    """Sub-national boundaries (geoBoundaries gbOpen, simplified), cached in geo-explainer/data/adm."""
    os.makedirs(ADM_DIR, exist_ok=True)
    out = os.path.join(ADM_DIR, f"{iso}_ADM{level}.json")
    if os.path.exists(out):
        d = json.load(open(out, encoding="utf-8"))
        if d.get("v") == 2:
            return d
    import urllib.request
    if job is not None:
        log(job, f"Downloading {iso} level-{level} boundaries (geoBoundaries, once)...")
    meta = json.load(urllib.request.urlopen(f"https://www.geoboundaries.org/api/current/gbOpen/{iso}/ADM{level}/", timeout=60))
    gj = json.load(urllib.request.urlopen(meta["simplifiedGeometryGeoJSON"], timeout=180))
    feats = []
    for f in gj["features"]:
        name = re.sub(r"\s+(Division|District|Province|State|Region|Zila|Zilla)$", "", f["properties"].get("shapeName", ""), flags=re.I).strip()
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        best, area = None, -1
        xs, ys = [], []
        for poly in polys:
            c, a = _ring_centroid(poly[0])
            if a > area:
                best, area = c, a
            xs += [p[0] for p in poly[0]]; ys += [p[1] for p in poly[0]]
        feats.append({"name": name, "bn": BGD_BN.get(name) if iso == "BGD" else None,
                      "c": [round(best[0], 4), round(best[1], 4)], "bbox": [min(xs), min(ys), max(xs), max(ys)],
                      "geometry": _d3_wind({"type": g["type"], "coordinates": _round_geom(g["coordinates"])})})
    data = {"v": 2, "iso": iso, "level": level, "source": meta.get("boundarySource", ""), "license": meta.get("boundaryLicense", ""),
            "features": feats}
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    return data


def _rkey(n):
    k = re.sub(r"[^a-z]", "", str(n).lower())
    return REGION_ALIAS.get(k, k)


def match_region(name, feats):
    import difflib
    n = str(name or "").strip()
    if not n:
        return None
    for f in feats:
        if f.get("bn") and f["bn"] == n:
            return f["name"]
    k = _rkey(n)
    keys = {_rkey(f["name"]): f["name"] for f in feats}
    if k in keys:
        return keys[k]
    m = difflib.get_close_matches(k, list(keys), n=1, cutoff=0.8)
    return keys[m[0]] if m else None


def prepare_spread(job, sc, i):
    """Resolve the affected districts/divisions, the origin and the camera box for a 'spread' scene."""
    iso = to_iso(str((sc.get("focus") or ["BGD"])[0]))
    level = int(sc.get("level") or (2 if iso == "BGD" else 1))
    data = adm_data(iso, level, job)
    fname = f"adm_{iso}_{level}.json"
    dst = os.path.join(PUBLIC_RENDER, fname)
    if not os.path.exists(dst):
        json.dump({"features": [{k: f[k] for k in ("name", "bn", "c", "geometry")} for f in data["features"]]},
                  open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    feats = data["features"]
    by = {f["name"]: f for f in feats}
    heat = {}
    if sc.get("mode") == "heat" and isinstance(sc.get("heat"), dict):
        for k, v in sc["heat"].items():
            key = re.sub(r"\s*(বিভাগ|division|সিটি|city)\s*$", "", str(k), flags=re.I).strip()
            m = match_region(key, feats)
            try:
                val = _num(v)
            except Exception:
                continue
            if m:
                heat[m] = heat.get(m, 0) + val
            else:
                log(job, f"Scene {i + 1}: '{k}' is not a region on the {iso} map, left out of the heat map")
        sc = dict(sc, regions=sorted(heat, key=lambda n: -heat[n]), order="value")
    regions = sc.get("regions") or []
    if isinstance(regions, str):
        regions = [x for x in re.split(r"[,\n،]+", regions) if x.strip()]
    aff, miss = [], []
    for r in regions:
        m = match_region(r, feats)
        if m and m not in aff:
            aff.append(m)
        elif not m:
            miss.append(str(r))
    if miss:
        log(job, f"Scene {i + 1}: could not find {', '.join(miss)} on the {iso} map")
    o = sc.get("origin")
    origin = None
    if isinstance(o, dict) and o.get("lat") is not None:
        origin = [float(o["lon"]), float(o["lat"])]
    elif isinstance(o, str) and o.strip():
        m = match_region(o, feats)
        origin = by[m]["c"] if m else None
    if origin is None and aff:
        origin = by[aff[0]]["c"]
    mode = sc.get("mode") or ("spread" if not aff else "regions")
    if origin and sc.get("order", "distance") == "distance" and aff:
        aff.sort(key=lambda n: (by[n]["c"][0] - origin[0]) ** 2 + (by[n]["c"][1] - origin[1]) ** 2)
    zoom = sc.get("zoom") or ("regions" if 0 < len(aff) <= 12 else "country")
    pool = [by[n] for n in aff] if (aff and zoom == "regions") else feats
    bb = [min(f["bbox"][0] for f in pool), min(f["bbox"][1] for f in pool), max(f["bbox"][2] for f in pool), max(f["bbox"][3] for f in pool)]
    if mode == "spread" and origin is None:
        origin = [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2]
    track = []
    for p in sc.get("track") or []:
        try:
            track.append([float(p[0]), float(p[1])] if isinstance(p, (list, tuple)) else [float(p["lon"]), float(p["lat"])])
        except Exception:
            pass
    if track:
        bb = [min(bb[0], *[p[0] for p in track]), min(bb[1], *[p[1] for p in track]),
              max(bb[2], *[p[0] for p in track]), max(bb[3], *[p[1] for p in track])]
    log(job, f"Scene {i + 1}: {sc.get('effect', 'flood')} spreading over {len(aff) or 'the whole'} "
             f"{'area' if not aff else ('districts' if level == 2 else 'regions')} ({mode})")
    extra = {"adm": f"_render/{fname}", "affected": aff, "origin_ll": origin, "zoom_bbox": bb, "mode": mode,
             "level": level, "track": track}
    if heat:
        extra["heat"] = heat
        extra["mode"] = "heat"
    return extra, f"Boundaries: geoBoundaries ({data.get('source', '')}), {data.get('license', '')}"

# ============================================================ sound effects --
SFX_DIR = os.path.join(ROOT, "public", "sfx", "lib")


def sfx_library():
    try:
        return json.load(open(os.path.join(SFX_DIR, "library.json"), encoding="utf-8"))
    except Exception:
        return {}


# narration words -> effect (first ambient + first hit that match are used)
SFX_RULES = [
    (r"বন্যা|প্লাবিত|জলাবদ্ধ|পানিবন্দি|flood", "flood"), (r"ঘূর্ণিঝড়|ঝড়|জলোচ্ছ্বাস|cyclone|storm", "storm"),
    (r"বৃষ্টি|বর্ষা|rain", "rain"), (r"গুলি|গোলাগুলি|গুলিবর্ষণ|gunfire|shooting|shots? fired", "gunfire"),
    (r"বিস্ফোরণ|বোমা|হামলা|explosion|bomb|airstrike", "explosion"), (r"যুদ্ধ|সংঘাত|সংঘর্ষ|লড়াই|war|fighting|conflict", "war"),
    (r"বিজয়|জয়ী|জিতে|জয় লাভ|victory|won the", "fanfare"), (r"উল্লাস|উদযাপন|celebrat", "cheer"),
    (r"বিক্ষোভ|আন্দোলন|মিছিল|অবরোধ|protest|rally", "protest"), (r"আগুন|অগ্নিকাণ্ড|পুড়ে|fire|burn", "fire"),
    (r"সেনাবাহিনী|সৈন্য|সেনা মোতায়েন|troops|soldiers|army", "march"), (r"হেলিকপ্টার|helicopter", "helicopter"),
    (r"অ্যাম্বুলেন্স|হাসপাতাল|ambulance|hospital", "siren"), (r"পুলিশ|police", "police"),
    (r"সংবাদ সম্মেলন|press conference", "press"), (r"সমুদ্র|সাগর|উপকূল|sea|coast|ocean", "waves"),
    (r"নদী|river", "water"), (r"খরা|drought|মরুভূমি", "wind"), (r"বজ্রপাত|thunder|lightning", "thunder"),
    (r"সতর্ক|হুঁশিয়ারি|alert|warning", "alarm"), (r"মহামারি|সংক্রমণ|disease|epidemic|outbreak", "heartbeat"),
]
EFFECT_SFX = {"flood": "flood", "conflict": "war", "fire": "fire", "drought": "wind", "disease": "heartbeat",
              "protest": "protest", "cyclone": "storm", "control": "march"}


def scene_sfx(sc, auto=True, level=1.0):
    """Sound effects for one scene: the producer's list ('rain, gunshot@2.5') or automatic ones."""
    lib = sfx_library()
    if not lib:
        return []
    want = sc.get("sfx")
    if isinstance(want, str):
        want = [x for x in re.split(r"[,\n]+", want) if x.strip()]
    items = []
    if want:
        for w in want:
            name, _, at = str(w).strip().partition("@")
            name = name.strip().lower().replace(" ", "_")
            if name in lib:
                items.append((name, float(at) if at.strip() else None))
    elif auto:
        text = " ".join([sc.get("narration") or "", sc.get("headline") or ""]).lower()
        amb = hit = None
        if sc.get("type") == "spread":
            amb = EFFECT_SFX.get(sc.get("effect") or "flood")
            if sc.get("track"):
                amb = "storm"
        for rx, name in SFX_RULES:
            if name not in lib or not re.search(rx, text):
                continue
            if lib[name]["kind"] == "amb" and not amb:
                amb = name
            elif lib[name]["kind"] == "hit" and not hit:
                hit = name
        items = [(n, None) for n in (amb, hit) if n and n in lib]
    out = []
    for name, at in items:
        e = lib[name]
        amb = e["kind"] == "amb"
        out.append({"src": f"sfx/lib/{name}.mp3", "name": name, "loop": amb,
                    "vol": round(e.get("vol", 0.3) * (0.7 if amb else 1.0) * level, 3),
                    "at": at if at is not None else (0.0 if amb else 0.6)})
    return out


# ============================================================ music pools --
MUSIC_POOLS = {
    "war": ["Five Armies.mp3", "Clash Defiant.mp3", "Hitman.mp3", "Colossus.mp3", "Big Drumming.mp3", "Firebrand.mp3", "Killers.mp3", "Impact Lento.mp3"],
    "tension": ["Drums of the Deep.mp3", "Controlled Chaos.mp3", "Gloom Horizon.mp3", "Enter the Maze.mp3", "I Can Feel it Coming.mp3",
                "Night of Chaos.mp3", "Darkening Developments.mp3", "Asian Drums.mp3", "Darkness is Coming.mp3", "Crypto.mp3"],
    "power-games": ["Hitman.mp3", "Clash Defiant.mp3", "Gloom Horizon.mp3", "Bet You Can ver 2.mp3", "Hidden Agenda.mp3"],
    "spy": ["I Can Feel it Coming.mp3", "Enter the Maze.mp3", "Darkening Developments.mp3", "Covert Affair.mp3"],
    "mystery": ["Controlled Chaos.mp3", "Night of Chaos.mp3", "Asian Drums.mp3", "Unanswered Questions.mp3"],
    "trade-strategy": ["Firebrand.mp3", "Big Drumming.mp3", "I Can Feel it Coming.mp3", "Sovereign Quarter.mp3"],
    "humanitarian": ["Death of Kings.mp3", "Crusade.mp3", "Heartbreaking.mp3"],
    "sombre": ["Death of Kings.mp3", "Crusade.mp3", "Ossuary 6 - Air.mp3"],
    "history": ["Crusade.mp3", "Dhaka.mp3", "Echoes of Time v2.mp3"],
    "environment": ["Drums of the Deep.mp3", "Gloom Horizon.mp3", "Lightless Dawn.mp3"],
    "hopeful": ["At Launch.mp3", "Floating Cities.mp3"],
}

def render(job, name, opts):
    s = load_settings()
    p = load_project(name)
    if not p:
        raise RuntimeError("project not found")
    missing = [i + 1 for i, sc in enumerate(p["scenes"]) if (sc.get("narration") or "").strip() and not sc.get("audio")]
    if missing:
        raise RuntimeError(f"Scenes {missing} have no audio yet. Generate audio first.")
    # fresh public/_render with this project's audio
    for f in os.listdir(PUBLIC_RENDER):
        fp = os.path.join(PUBLIC_RENDER, f)
        try:
            shutil.rmtree(fp) if os.path.isdir(fp) else os.remove(fp)
        except Exception:
            pass
    vertical = opts.get("aspect") == "9:16"
    look = opts.get("look") or s.get("look") or "classic"
    lang = p.get("lang", "bn")
    f_text = font_entry(opts.get("font_text") or s.get("font_text"))
    f_cap = font_entry(opts.get("font_caption") or s.get("font_caption"))
    if opts.get("musicVolume") is not None:
        s["music_volume"] = float(opts["musicVolume"])
    bg = opts.get("bg") or s.get("bg") or "navy"
    tscale = float(opts.get("textScale") or s.get("text_scale") or 1.25)
    s["bg"], s["text_scale"] = bg, tscale
    TEXT_SCALE["k"] = tscale
    BG_RED["on"] = bg in ("red", "maroon") and look != "light"
    if opts.get("broll_region"):
        s["broll_region"] = opts["broll_region"]
    if "broll_strict" in opts:
        s["broll_strict"] = bool(opts["broll_strict"])
    for k in ("channel", "look", "font_text", "font_caption"):      # remember the last choices
        if opts.get(k):
            s[k] = opts[k]
    if opts.get("channel") and opts["channel"] not in s.get("channels", []):
        s["channels"] = s.get("channels", []) + [opts["channel"]]
    save_settings({k: v for k, v in s.items() if k in DEFAULTS})
    font_files = []
    for tag, fe in (("t", f_text), ("c", f_cap)):
        if not fe:
            continue
        for wname, wt in (("regular", 400), ("bold", 700)):
            dst = f"font_{tag}{wt}{os.path.splitext(fe[wname])[1].lower()}"
            try:
                shutil.copyfile(fe[wname], os.path.join(PUBLIC_RENDER, dst))
                font_files.append({"family": fe["family"], "src": f"_render/{dst}", "weight": wt})
            except Exception:
                pass
    scenes, used, adm_credits, used_sfx = [], set(), set(), set()
    import broll_region as BR
    region_mode = opts.get("broll_region") or "auto"
    strict = opts.get("broll_strict", True) is not False
    video_region = BR.detect_region(p["scenes"], lang) if region_mode == "auto" else region_mode
    if any(sc.get("type") == "broll" for sc in p["scenes"]):
        log(job, f"B-roll region: {BR.REGIONS.get(video_region, BR.REGIONS['global'])['name']}"
                 + (" (only footage that names the place)" if strict else ""))
        os.makedirs(os.path.join(ROOT, "broll", video_region), exist_ok=True)
    for i, sc in enumerate(p["scenes"]):
        sc2 = dict(sc)
        if sc.get("audio"):
            src = os.path.join(proj_dir(name), sc["audio"])
            dst = f"s{i:02d}.wav"
            shutil.copyfile(src, os.path.join(PUBLIC_RENDER, dst))
            sc2["audio"] = f"_render/{dst}"
        if sc.get("type") == "chart":
            got = render_chart(job, sc, i, look, lang, f_text, vertical)
            if got:
                sc2["chart"] = dict(sc.get("chart") or {}, dir=got[0], frames=got[1])
                log(job, f"Scene {i + 1}: {sc2['chart'].get('kind')} chart drawn in R")
            else:
                sc2["type"] = "map"
                sc2.setdefault("highlight", {c: "red" for c in (sc.get("focus") or ["BGD"])})
        if sc.get("type") == "spread":
            try:
                extra, credit_line = prepare_spread(job, sc, i)
                sc2.update(extra)
                adm_credits.add(credit_line)
            except Exception as e:
                log(job, f"Scene {i + 1}: could not load boundaries ({str(e)[:120]}), showing the plain map")
                sc2["type"] = "map"
        fx = scene_sfx(sc2, auto=opts.get("auto_sfx", True), level=float(opts.get("sfx_level", 1.0)))
        if fx:
            sc2["sfx"] = fx
            used_sfx.update(x["name"] for x in fx)
        else:
            sc2.pop("sfx", None)
        if sc.get("type") == "broll":
            import broll_region as BR
            reg = sc.get("broll_region") or (BR.scene_region(sc, video_region) if region_mode == "auto" else region_mode)
            got = fetch_broll(job, sc.get("broll") or "", vertical, used, float(sc.get("duration") or 6), reg, strict)
            if not got and used:     # nothing new fits: a clip already in this video beats an empty map
                got = fetch_broll(job, sc.get("broll") or "", vertical, set(), float(sc.get("duration") or 6), reg, strict)
                if got:
                    sc2["broll_offset"] = 4
            if got:
                dst = f"broll{i:02d}.mp4"
                shutil.copyfile(got[0], os.path.join(PUBLIC_RENDER, dst))
                sc2["broll_file"] = f"_render/{dst}"
                log(job, f"Scene {i + 1}: B-roll [{BR.REGIONS[reg]['name']}] {got[1]}")
            else:
                sc2["type"] = "map"
                sc2.setdefault("highlight", {c: "red" for c in (sc.get("focus") or ["BGD"])})
                log(job, f"Scene {i + 1}: no verified {BR.REGIONS[reg]['name']} footage for '{sc.get('broll', '')}'"
                         + ("" if pexels_key() else " (add a Pexels key in Settings)") + ", showing the map instead")
        scenes.append(sc2)
    music = None
    if opts.get("music") == "auto":
        opts = dict(opts, music=pick_music(p, job) or "")
    if opts.get("music"):
        mp = os.path.join(MUSIC, os.path.basename(opts["music"]))
        if os.path.exists(mp):
            ext = os.path.splitext(mp)[1]
            shutil.copyfile(mp, os.path.join(PUBLIC_RENDER, "music" + ext))
            music = "_render/music" + ext
    props = {"scenes": scenes, "lang": lang, "channel": opts.get("channel", s.get("channel", "")),
             "font": s["font"], "look": look, "fontFiles": font_files, "title": p.get("title", ""), "dataNote": p.get("data_note", ""), "bg": bg, "textScale": tscale,
             "credits_extra": sorted(adm_credits) + (["Sound effects: Mixkit (mixkit.co) and BigSoundBank.com"] if used_sfx else []),
             "fontText": f_text["family"] if f_text else "Hind Siliguri",
             "fontCaption": f_cap["family"] if f_cap else "Hind Siliguri", "captions": bool(opts.get("captions", True)), "music": music,
             "musicVolume": float(opts.get("musicVolume", 0.08)), "musicBoost": float(opts.get("musicBoost", 1.8)),
             "sfx": bool(opts.get("sfx", True)), "intro": bool(opts.get("intro", True)),
             "outro": bool(opts.get("outro", True)),
             "width": 1080 if vertical else 1920, "height": 1920 if vertical else 1080}
    props_file = os.path.join(proj_dir(name), "render_props.json")
    json.dump(props, open(props_file, "w", encoding="utf-8"), ensure_ascii=False)
    out = os.path.join(out_dir(), f"{name}_{time.strftime('%Y%m%d_%H%M')}{'_vertical' if vertical else ''}.mp4")
    cli = os.path.join(ROOT, "node_modules", "@remotion", "cli", "remotion-cli.js")
    cmd = [node_exe(), cli, "render", "src/index.jsx", "Explainer", out, f"--props={props_file}",
           "--codec=h264", "--crf=20"] + RENDER_FLAGS
    log(job, "Rendering... (first render of a session bundles the project, give it a minute)")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    pr = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace", creationflags=flags)
    job["pid"] = pr.pid
    rx = re.compile(r"Rendered (\d+)/(\d+)")
    ex = re.compile(r"Encoded (\d+)/(\d+)")
    tail = []
    for line in pr.stdout:
        line = line.strip()
        if not line:
            continue
        tail.append(line); tail = tail[-40:]
        m = rx.search(line)
        if m:
            job["progress"] = int(85 * int(m.group(1)) / max(1, int(m.group(2))))
            continue
        m = ex.search(line)
        if m:
            job["progress"] = 85 + int(15 * int(m.group(1)) / max(1, int(m.group(2))))
            continue
        if "Bundling" in line:
            continue
        log(job, line[:300])
    pr.wait()
    if pr.returncode != 0 or not os.path.exists(out):
        raise RuntimeError("Render failed:\n" + "\n".join(tail[-15:]))
    log(job, "Done: " + out)
    credit = credit_text(os.path.basename(opts.get("music") or "")) if opts.get("music") else None
    if credit:
        open(os.path.splitext(out)[0] + "_CREDITS.txt", "w", encoding="utf-8").write(
            "Paste this in the YouTube description (required by the music licence):\n\n" + credit + "\n")
        log(job, "Music credit saved next to the video (_CREDITS.txt). Paste it in the YouTube description.")
    write_extras(job, p, props, out, credit, lang)
    make_thumbnail(job, props_file, out, props)
    return {"file": os.path.basename(out), "credit": credit}


def one_click(job, req):
    """topic -> script -> voice -> video, in one job."""
    def run(fn, lo, hi, *a):
        j = {"log": job["log"], "progress": 0}
        err = []
        def wrapped():
            try:
                j["result"] = fn(j, *a)
            except Exception as e:
                err.append(e)
        th = threading.Thread(target=wrapped, daemon=True)
        th.start()
        while th.is_alive():
            job["progress"] = int(lo + (hi - lo) * j.get("progress", 0) / 100)
            time.sleep(0.5)
        if err:
            raise err[0]
        job["progress"] = hi
        return j.get("result")

    existing = load_project(req["resume"]) if req.get("resume") else None
    if existing and existing.get("scenes"):
        name = existing["name"]
        log(job, "STEP 1/3  Script already written, reusing it")
        job["progress"] = 15
    else:
        log(job, "STEP 1/3  Writing the script")
        r = run(gen_script, 0, 15, req)
        name = r["project"]
    job["project"] = name
    p = load_project(name)
    if req.get("voice"):
        p["voice"] = req["voice"]
    if req.get("style"):
        p["style"] = req["style"]
    save_project(p)
    log(job, "STEP 2/3  Recording the voice")
    run(gen_audio, 15, 55, name, None, False)
    log(job, "STEP 3/3  Rendering the video")
    out = run(render, 55, 100, name, req.get("render", {}))
    return {"project": name, "file": out["file"], "credit": out.get("credit")}


# ============================================================ own audio --
# The producer uploads a recording + the exact script. We split the audio into
# scenes at the natural pauses, time captions to the voice, and design the maps
# (Gemini if available, otherwise automatic country detection). No TTS needed.

AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma", ".webm", ".mp4")


def ffmpeg_exe():
    f = shutil.which("ffmpeg")
    if f:
        return f
    import glob
    hits = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\ffmpeg.exe"))
    if hits:
        return hits[0]
    raise RuntimeError("ffmpeg not found. Install it with: winget install ffmpeg")


def load_audio_24k(path):
    """Any audio file -> mono 24 kHz int16 numpy array (same format as Gemini TTS)."""
    import numpy as np
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    r = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", path, "-ac", "1", "-ar", "24000", "-f", "s16le", "-"],
                       capture_output=True, creationflags=flags)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("Could not read the audio file: " + r.stderr.decode("utf-8", "replace")[:300])
    return np.frombuffer(r.stdout, dtype=np.int16)


def write_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(x.tobytes())


HEADER_RE = re.compile(r"^\s*(?:#+\s*.*|\**\s*\[[^\]]*\]\s*\**\s*|\**\s*\(?\d{1,2}:\d{2}\s*[-–—]\s*\d{1,2}:\d{2}\)?\s*\**)$")
TIMECODE_RE = re.compile(r"[\(\[]?\s*\d{1,2}:\d{2}\s*[-–—]\s*\d{1,2}:\d{2}\s*[\)\]]?")


def _clean_line(t):
    t = re.sub(r"\*\*|__", "", t)                 # markdown bold
    t = re.sub(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", "", t)  # list bullets
    return t.strip()


def _section_name(line):
    t = re.sub(r"[#*\[\]]", "", line)
    t = TIMECODE_RE.sub("", t)
    return t.strip(" —–-:").strip()


def parse_script(text, min_chars=100, max_chars=260):
    """Recorded script -> [{"text", "section"}].
    - Lines like **[India — 0:20–0:55]**, # headings or bare timecodes are NOT spoken:
      they start a new section and give its name, but get no audio time.
    - Markdown ** marks are removed.
    - Short paragraphs in the same section are joined so each scene lasts ~6-15 s."""
    text = text.replace("\r\n", "\n")
    paras, section, cur = [], "", []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            if cur:
                paras.append({"text": " ".join(cur), "section": section}); cur = []
            continue
        if HEADER_RE.match(line):
            if cur:
                paras.append({"text": " ".join(cur), "section": section}); cur = []
            section = _section_name(line)
            continue
        cl = _clean_line(line)
        if cl:
            cur.append(cl)
    if cur:
        paras.append({"text": " ".join(cur), "section": section})
    if len(paras) == 1:  # one big block: ~2 sentences per scene
        sents = [x.strip() for x in SENT.findall(paras[0]["text"]) if x.strip()]
        paras = [{"text": x, "section": paras[0]["section"]} for x in sents]
    # join short neighbours inside the same section
    out = []
    for p_ in paras:
        if (out and out[-1]["section"] == p_["section"] and len(out[-1]["text"]) < min_chars
                and len(out[-1]["text"]) + len(p_["text"]) <= max_chars):
            out[-1]["text"] += " " + p_["text"]
        else:
            out.append(dict(p_))
    # a very short last piece of a section joins the previous one
    fixed = []
    for p_ in out:
        if fixed and len(p_["text"]) < 40 and fixed[-1]["section"] == p_["section"]:
            fixed[-1]["text"] += " " + p_["text"]
        else:
            fixed.append(p_)
    # a paragraph that runs past ~20 s gets cut into sentence groups, so one picture never sits for 40 s
    import production as PR
    final = []
    for p_ in fixed:
        if len(p_["text"]) > max_chars + 60:
            final += [{"text": b, "section": p_["section"]} for b in PR.beats(p_["text"], 90, max_chars - 40)]
        else:
            final.append(p_)
    return final


def split_script(text):
    return [p_["text"] for p_ in parse_script(text)]


def scene_boundaries(x, texts):
    """Where each scene starts (seconds). Text share is mapped onto speaking time,
    then each cut snaps to the longest nearby pause (scene changes are usually
    the longest breaths)."""
    sr = 24000
    dur = len(x) / sr
    if len(texts) < 2:
        return []
    pauses = find_pauses(x, sr, min_len=0.2)
    lead = pauses[0][1] if pauses and pauses[0][0] < 0.05 else 0.0
    tail = pauses[-1][0] if pauses and pauses[-1][1] > dur - 0.05 else dur
    inner = [p for p in pauses if p[0] > lead + 0.1 and p[1] < tail - 0.1]
    voiced_total = (tail - lead) - sum(b - a for a, b in inner)

    def voiced_to_real(v):
        t, left = lead, v
        for a, b in inner:
            seg = a - t
            if left <= seg:
                return t + left
            left -= seg
            t = b
        return min(t + left, tail)

    w = [max(len(t), 1) for t in texts]
    tot, acc, cuts, used = sum(w), 0, [], set()
    for wi in w[:-1]:
        acc += wi
        est = voiced_to_real(voiced_total * acc / tot)
        win = max(1.5, (tail - lead) / len(texts) * 0.35)
        best, score = None, -1e9
        for j, (a, b) in enumerate(inner):
            m = (a + b) / 2
            if j in used or abs(m - est) > win or (cuts and m < cuts[-1] + 1.0):
                continue
            sc = (b - a) - 0.35 * abs(m - est)
            if sc > score:
                best, score = j, sc
        if best is not None:
            used.add(best)
            cuts.append((inner[best][0] + inner[best][1]) / 2)
        else:
            cuts.append(max(est, cuts[-1] + 1.0) if cuts else est)
    return [round(c, 2) for c in cuts]


# ---- speech recognition alignment (GPU Whisper) ----
# Python with faster-whisper / torchaudio + uroman for speech alignment. Set GEO_ALIGN_PY to use another one.
WHISPER_PY = os.environ.get("GEO_ALIGN_PY") or os.path.join(PARENT, "envs", "wav2lip", "Scripts", "python.exe")


def whisper_words(job, x, lang, workdir, texts=None):
    """Word times for the recording. With the script known, forced alignment (MMS) places each
    script word on the voice; Whisper is only the fallback. Returns [{s,e,w}] or None."""
    if not os.path.exists(WHISPER_PY):
        log(job, "Speech recognition not installed; using pause detection.")
        return None
    wav = os.path.join(workdir, "for_whisper.wav")
    write_wav(wav, x)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    if texts:
        toks = [w for t in texts for w in re.findall(r"\S+", t)]
        wf, of = os.path.join(workdir, "script_words.json"), os.path.join(workdir, "mms.json")
        json.dump(toks, open(wf, "w", encoding="utf-8"), ensure_ascii=False)
        log(job, "Matching your script to the recording word by word (forced alignment)...")
        try:
            r = subprocess.run([WHISPER_PY, os.path.join(HERE, "align_mms.py"), wav, wf, of], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=1800, creationflags=flags,
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            if r.returncode == 0 and os.path.exists(of):
                d = json.load(open(of, encoding="utf-8"))
                # words squeezed into < 50 ms were not really spoken; leaving them out lets the
                # coverage check drop script lines that are missing from the recording
                ws = [{"s": t[0], "e": t[1], "w": w} for w, t in zip(toks, d["times"]) if t and t[1] - t[0] >= 0.05]
                if len(ws) >= 0.6 * len(toks):
                    log(job, f"Placed {len(ws)} of {len(toks)} script words on your voice ({d.get('device', '').upper()}).")
                    return ws
                log(job, f"Forced alignment placed only {len(ws)} of {len(toks)} words; trying Whisper.")
            else:
                log(job, "Forced alignment failed; trying Whisper. " + (r.stderr or "")[-160:])
        except Exception as e:
            log(job, f"Forced alignment error ({e}); trying Whisper.")
    out = os.path.join(workdir, "words.json")
    log(job, "Listening to your recording with Whisper (graphics card if ready, otherwise processor; about 1 minute)...")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        r = subprocess.run([WHISPER_PY, os.path.join(HERE, "align_whisper.py"), wav, lang, out],
                           capture_output=True, text=True, timeout=1800, creationflags=flags)
        if r.returncode != 0 or not os.path.exists(out):
            log(job, "Speech recognition failed; using pause detection. " + (r.stderr or "")[-200:])
            return None
        d = json.load(open(out, encoding="utf-8"))
        log(job, f"Heard {len(d['words'])} words ({d['device'].upper()}).")
        return d["words"] or None
    except Exception as e:
        log(job, f"Speech recognition error ({e}); using pause detection.")
        return None


# Sound skeleton: Bangla, Devanagari and romanised Latin all reduce to the same
# consonant classes, so a transcript in any of those scripts can be matched to the script.
_BN_CLASS = {}
for _chars, _cls in [("কখগঘ", "K"), ("চছজঝযৎ", "C"), ("টঠডঢতথদধ", "T"), ("পফবভ", "P"), ("ম", "M"),
                     ("ঙঞণন", "N"), ("রড়ঢ়ঋ", "R"), ("ল", "L"), ("শষস", "S"), ("হ", "H"), ("য়", "Y"),
                     ("০১২৩৪৫৬৭৮৯", "D")]:
    for _c in _chars:
        _BN_CLASS[_c] = _cls


def _skeleton_chars(t):
    """Text -> list of consonant-class letters (vowels and marks dropped)."""
    import unicodedata
    t = unicodedata.normalize("NFC", t)
    out, i, low = [], 0, t.lower()
    while i < len(low):
        ch = low[i]
        o = ord(ch)
        if 0x0900 <= o <= 0x097F:
            ch = chr(o + 0x80)
        if ch in _BN_CLASS:
            out.append(_BN_CLASS[ch]); i += 1; continue
        two = low[i:i + 2]
        if two in ("ch", "sh", "th", "dh", "ph", "bh", "kh", "gh", "jh"):
            out.append({"ch": "C", "sh": "S", "th": "T", "dh": "T", "ph": "P", "bh": "P", "kh": "K", "gh": "K", "jh": "C"}[two])
            i += 2; continue
        m = {"k": "K", "q": "K", "g": "K", "c": "C", "j": "C", "z": "C", "x": "K", "t": "T", "d": "T",
             "p": "P", "b": "P", "f": "P", "v": "P", "w": "P", "m": "M", "n": "N", "r": "R", "l": "L",
             "s": "S", "h": "H", "y": "Y"}.get(ch)
        if m:
            out.append(m)
        elif ch.isdigit():
            out.append("D")
        i += 1
    # collapse repeats (double letters, conjuncts)
    res = []
    for c in out:
        if not res or res[-1] != c:
            res.append(c)
    return res


def _norm_chars(t):
    return _skeleton_chars(t)


def align_positions(script_text, words, positions, two_sided=False):
    """Map character offsets in script_text to times using whisper words.
    Returns a time (seconds) for each offset, or None when unmatched."""
    import difflib
    # script: skeleton letters with the offset of the source character
    S, S_off = [], []
    for i, ch in enumerate(script_text):
        sk = _skeleton_chars(script_text[i:i + 2])[:1] if ch.isalpha() or ch.isdigit() else []
        if sk and not (S and S[-1] == sk[0] and S_off and i - S_off[-1] <= 2):
            S.append(sk[0]); S_off.append(i)
    # transcript: skeleton letters with a time each
    T, T_time = [], []
    for w in words:
        cs = _skeleton_chars(w["w"])
        for k, ch in enumerate(cs):
            T.append(ch)
            T_time.append(w["s"] + (w["e"] - w["s"]) * k / max(len(cs), 1))
    if not S or not T:
        return [None] * len(positions)
    sm = difflib.SequenceMatcher(None, S, T, autojunk=False)
    s2t = {}
    for a, b, size in sm.get_matching_blocks():
        if size >= 3:                      # ignore accidental 1-2 letter matches
            for k in range(size):
                s2t[a + k] = b + k
    rate = (T_time[-1] - T_time[0]) / max(len(T), 1)   # seconds per skeleton letter
    import bisect
    out = []
    for pos in positions:
        si = bisect.bisect_left(S_off, pos)
        after = before = None
        for j in range(si, min(si + 60, len(S))):          # first solid match at/after the offset
            if j in s2t:
                after = (max(0.0, T_time[s2t[j]] - (j - si) * rate), j - si)
                break
        for j in range(si - 1, max(si - 60, -1), -1):      # last solid match before it
            if j in s2t:
                before = (T_time[s2t[j]] + (si - 1 - j + 1) * rate, si - 1 - j)
                break
        out.append((before, after) if two_sided else (after[0] if after else None))
    return out


def spoken_coverage(texts, words):
    """For each scene: share of its sounds that were heard in the recording (0..1)."""
    import difflib
    S, owner = [], []
    for i, t in enumerate(texts):
        sk = _skeleton_chars(t)
        S += sk; owner += [i] * len(sk)
    T = []
    for w in words:
        T += _skeleton_chars(w["w"])
    got = [0] * len(texts)
    tot = [0] * len(texts)
    for o in owner:
        tot[o] += 1
    if not S or not T:
        return [0.0] * len(texts)
    sm = difflib.SequenceMatcher(None, S, T, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        if size >= 3:
            for k in range(size):
                got[owner[a + k]] += 1
    return [g / t if t else 0.0 for g, t in zip(got, tot)]


def word_boundaries(texts, words, total, x=None):
    """Scene cut times. Each cut is anchored on the recognised words at the end of the
    previous scene and the start of the next; placed on the best pause between them.
    Cuts Whisper could not anchor are interpolated between their anchored neighbours."""
    joined, starts = "", []
    for t in texts:
        starts.append(len(joined))
        joined += t + "\n\n"
    sides = align_positions(joined, words, starts[1:], two_sided=True)
    pauses = find_pauses(x, 24000, min_len=0.15) if x is not None else []
    cuts = []
    for before, after in sides:
        good = [v for v in (before, after) if v and v[1] <= 12]
        if not good:
            cuts.append(None)
            continue
        best = min(good, key=lambda v: v[1])[0]
        lo = min(v[0] for v in good) - 0.6
        hi = max(v[0] for v in good) + 0.6
        prev = next((c for c in reversed(cuts) if c is not None), 0.0)
        cand = [(a, b) for a, b in pauses if lo <= (a + b) / 2 <= hi and (a + b) / 2 > prev + 0.8]
        if cand:
            a, b = max(cand, key=lambda p_: (p_[1] - p_[0]) - 0.25 * abs((p_[0] + p_[1]) / 2 - best))
            c = (a + b) / 2
        else:
            c = best - 0.15
        cuts.append(round(max(c, prev + 0.8, 0.1), 2) if c > prev else None)
    # fill the gaps: share the time between anchored neighbours by text length
    n = len(cuts)
    lens = [max(len(t), 1) for t in texts]
    i = 0
    while i < n:
        if cuts[i] is not None:
            i += 1
            continue
        j = i
        while j < n and cuts[j] is None:
            j += 1
        left = cuts[i - 1] if i > 0 else 0.0
        right = cuts[j] if j < n else total
        seg = lens[i:j + 1]   # scenes i+1 .. j+1 share (left, right)
        acc, tot_len = 0, sum(seg)
        for k in range(i, j):
            acc += lens[k]
            est = left + (right - left) * acc / tot_len
            near = [(a, b) for a, b in pauses if abs((a + b) / 2 - est) < 1.2]
            cuts[k] = round((lambda p_: (p_[0] + p_[1]) / 2)(max(near, key=lambda p_: p_[1] - p_[0])) if near else est, 2)
        i = j
    ok = all(0 < c < total for c in cuts) and all(b > a for a, b in zip(cuts, cuts[1:]))
    return cuts if ok else None


def word_cues(text, words, scene_start, scene_len):
    """Caption cues for one scene from recognised words."""
    parts = split_caption_parts(text)
    if not parts:
        return []
    offs, pos = [], 0
    for ptxt in parts:
        k = text.find(ptxt[:10], pos)
        k = pos if k < 0 else k
        offs.append(k); pos = k + len(ptxt)
    sw = [w for w in words if scene_start - 0.2 <= w["s"] < scene_start + scene_len]
    times = align_positions(text, sw, offs) if sw else [None] * len(parts)
    if any(t is None for t in times) or any(b <= a for a, b in zip(times, times[1:])):
        return None
    last_end = max([w["e"] for w in sw] or [scene_start + scene_len]) - scene_start
    rel = [max(0.0, t - scene_start) for t in times] + [min(last_end + 0.2, scene_len)]
    return [{"start": round(rel[i], 2), "end": round(rel[i + 1], 2), "text": parts[i]} for i in range(len(parts))]


def cut_scenes(p, x, cuts, words=None):
    """Write one wav per scene at the given cut times and rebuild captions."""
    import numpy as np
    sr = 24000
    edges = [0.0] + list(cuts) + [len(x) / sr]
    d = proj_dir(p["name"])
    for i, sc in enumerate(p["scenes"]):
        a, b = int(edges[i] * sr), int(edges[i + 1] * sr)
        clip = x[a:b]
        tail = np.zeros(int(sr * 0.15), dtype=np.int16)  # tiny breath so the cut is not abrupt
        clip = np.concatenate([clip, tail])
        rel = f"audio/u{i:02d}.wav"
        write_wav(os.path.join(d, rel), clip)
        sc["audio"] = rel
        sc["audio_src"] = "upload"
        sc["duration"] = round(len(clip) / sr, 2)
        sc["start"] = round(edges[i], 2)
        cues = word_cues(sc.get("narration", ""), words, edges[i], edges[i + 1] - edges[i]) if words else None
        sc["cues"] = cues or aligned_cues(sc.get("narration", ""), clip, 0.0)
    p["upload"]["cuts"] = list(cuts)


# ---- visuals without Gemini: find countries mentioned in each scene ----
_NAME_LIST = None


def _names():
    global _NAME_LIST
    if _NAME_LIST is None:
        items = []
        for c in COUNTRIES:
            for n in [c["name"], c["bn"]] + c.get("aliases", []):
                if not n:
                    continue
                latin = re.match(r"^[A-Za-z .'’\-]+$", n) is not None
                if latin and len(n) < 4:   # skip US, UK, BD... too ambiguous inside words
                    continue
                items.append((n, c["iso"], latin))
        items.sort(key=lambda t: -len(t[0]))  # longest first: "South Korea" before "Korea"
        _NAME_LIST = items
    return _NAME_LIST


def countries_in(text):
    found, low = [], text.lower()
    for n, iso, latin in _names():
        if latin:
            hit = re.search(r"(?<![A-Za-z])" + re.escape(n.lower()) + r"(?![a-z])", low)
        else:
            hit = n in text  # Bangla: suffixes attach (বাংলাদেশের), plain substring is right
        if hit and iso not in found:
            found.append(iso)
    return found


def auto_visuals(texts, title, lang, sections=None):
    cols = ["red", "amber", "teal", "blue", "violet"]
    scenes, last = [], ["BGD"]
    for i, t in enumerate(texts):
        cs = countries_in(t)[:4]
        focus = cs or last
        sc = {"narration": t, "focus": focus}
        if i == 0:
            sc.update(type="title", title=title or t.split("।")[0][:60])
        else:
            sc.update(type="map", headline=(sections[i] if sections and (i == 0 or sections[i] != sections[i - 1]) else ""))
            if cs:
                sc["highlight"] = {c: cols[j % 5] for j, c in enumerate(cs)}
        if cs:
            last = cs
        scenes.append(sc)
    return scenes


VISUAL_PROMPT = """You design the visuals for a geopolitics explainer video. The narration is FIXED:
do not change, shorten or translate it. For each numbered scene below, return the visuals only.
On-screen text (headline, labels, point names, bullets) must be in {langname}.

Scenes:
{scenes}

Return ONLY a JSON array with exactly {n} objects, in order, each like:
{{"type": "title|map|globe|choropleth|chart|broll|stat|bullets|timeline|compare|quote", "headline": "max 6 words",
  "focus": ["ISO3"], "highlight": {{"ISO3": "red|amber|teal|blue|violet|green|yellow|pink|grey"}},
  "arrows": [{{"from": "ISO3", "to": {{"lon": 0, "lat": 0}}, "label": "short"}}],
  "points": [{{"name": "place", "lat": 0, "lon": 0}}],
  "title": "", "subtitle": "", "stat": {{"value": "", "label": "", "source": ""}}, "bullets": [],
  "events": [{{"date": "", "text": ""}}], "compare": {{"a": "ISO3", "b": "ISO3", "rows": [{{"label": "", "a": "", "b": ""}}], "source": ""}},
  "chart": {{"kind": "bar|hbar|lollipop|line|area|stacked|donut|pie|waffle|treemap", "title": "", "unit": "", "data": [{{"label": "", "value": 0}}], "source": ""}},
  "values": {{"ISO3": 0}}, "unit": "", "source": "", "broll": "English stock-footage search, 2-4 words"}}
Rules: first object type "title". Mostly "map" (at least half the scenes). Every object needs "focus".
Use "bullets" rarely (max 3 in the whole video) and only when the narration lists items.
"globe" = rotating 3D globe (max 2). "spread" = something spreading inside a country (flood, fighting, protests,
disease, drought, cyclone): {{"effect": "...", "regions": ["only districts the narration names"], "origin": "...",
"mode": "regions|spread", "track": [[lon, lat]] for a cyclone}}. Optional "sfx": ["rain", "gunfire", "fanfare", ...]
only when the narration describes that sound. "broll" = stock footage for human moments, 1-3 per video, never two in a row. B-roll words must name the place and
its people ("Dhaka street crowd", "Bangladeshi garment workers", "Riyadh street Saudi").
Only use stat/compare/timeline/chart/choropleth when the narration itself states those facts; copy numbers exactly
from the narration, never add new ones. Points only for places named in the narration whose
coordinates you are sure of. Omit unused keys."""


def gemini_visuals(job, texts, lang, sections=None):
    s = load_settings()
    from google.genai import types
    c = client()
    sections = sections or [""] * len(texts)
    numbered = "\n".join(f"{i + 1}. " + (f"[section: {sec}] " if sec else "") + t for i, (t, sec) in enumerate(zip(texts, sections)))
    prompt = VISUAL_PROMPT.format(scenes=numbered, n=len(texts),
                                  langname="Bangla (Bengali script)" if lang == "bn" else "English")
    cfg = types.GenerateContentConfig(response_mime_type="application/json")
    last = None
    for wait in (0, 15, 30):
        if wait:
            log(job, f"Gemini busy, waiting {wait} s...")
            time.sleep(wait)
        for model in model_list(s["script_model"], s["script_fallback"], EXTRA_SCRIPT):
            try:
                log(job, f"Designing the maps with {model}...")
                r = c.models.generate_content(model=model, contents=prompt, config=cfg)
                t = r.text.strip()
                t = t[t.find("["): t.rfind("]") + 1]
                arr = json.loads(t)
                if isinstance(arr, list) and len(arr) == len(texts):
                    return arr
                log(job, f"{model} returned {len(arr)} scenes instead of {len(texts)}, trying again")
            except Exception as e:
                last = e
                log(job, f"{model} failed: {str(e).split('.')[0][:100]}")
                if not is_busy(e):
                    continue
    raise RuntimeError(f"Gemini unavailable: {last}")


def gemini_array(job, prompt, n, what="the visuals"):
    s = load_settings()
    from google.genai import types
    c = client()
    cfg = types.GenerateContentConfig(response_mime_type="application/json")
    last = None
    for wait in (0, 20):
        if wait:
            log(job, f"Gemini busy, waiting {wait} s...")
            time.sleep(wait)
        for model in model_list(s["script_model"], s["script_fallback"], EXTRA_SCRIPT):
            try:
                log(job, f"Planning {what} with {model}...")
                r = c.models.generate_content(model=model, contents=prompt, config=cfg)
                t = r.text.strip()
                t = t[t.find("["): t.rfind("]") + 1]
                try:
                    arr = json.loads(t)
                except ValueError:       # small models leave trailing commas or comments
                    t2 = re.sub(r",\s*([}\]])", r"\1", re.sub(r"//[^\n\"]*\n", "\n", t))
                    arr = json.loads(t2)
                if isinstance(arr, list) and len(arr) == n:
                    return arr
                log(job, f"{model} returned {len(arr)} items instead of {n}, trying again")
            except Exception as e:
                last = e
                log(job, f"{model} failed: {str(e).split('.')[0][:100]}")
    arr = ollama_array(job, prompt, n, what)
    if arr is not None:
        return arr
    raise RuntimeError(f"Gemini unavailable: {last}")


def parse_json_array(t):
    t = t[t.find("["): t.rfind("]") + 1]
    try:
        return json.loads(t)
    except ValueError:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", t))


def ollama_array(job, prompt, n, what):
    """Local planner (Ollama on this PC). Settings: local_model (default gemma4:latest)."""
    import urllib.request
    want = (load_settings().get("local_model") or "gemma4:latest").strip()
    try:
        tags = json.load(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=4))
        names = [m["name"] for m in tags.get("models", [])]
    except Exception:
        log(job, "Ollama is not running on this PC, no local planner.")
        return None
    order = [m for m in [want, "gemma4:latest", "qwen3.6:latest"] if m in names]
    for model in dict.fromkeys(order):
        try:
            log(job, f"Gemini is out of quota. Planning {what} on this PC with {model} (a minute or two)...")
            body = json.dumps({"model": model, "prompt": prompt + "\n\nReply with the JSON array only.", "stream": False,
                               "options": {"num_ctx": 16384, "temperature": 0.3}}).encode()
            r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate", body,
                                       {"Content-Type": "application/json"}), timeout=900)
            txt = json.load(r).get("response", "")
            txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
            arr = parse_json_array(txt)
            if isinstance(arr, list) and len(arr) == n:
                return arr
            log(job, f"{model} returned {len(arr) if isinstance(arr, list) else 0} items instead of {n}")
        except Exception as e:
            log(job, f"{model} failed: {str(e)[:100]}")
    return None


def build_from_audio(job, req):
    import numpy as np
    name = safe_name(req.get("name") or req.get("title") or "my_audio")
    d = proj_dir(name)
    os.makedirs(os.path.join(d, "upload"), exist_ok=True)
    src = req["audio_path"]
    lang = req.get("lang", "bn")
    title = req.get("title", "").strip()
    raw = req.get("script", "")
    try:
        open(os.path.join(d, "upload", "script.txt"), "w", encoding="utf-8").write(raw)
    except Exception:
        pass
    import production as PR
    prod = PR.parse_production(raw) if PR.is_production(raw) else None
    if prod and prod["sections"]:
        items = PR.beat_list(prod)
        texts = [it["text"] for it in items]
        sections = [it["section"] for it in items]
        title = title or prod["title"]
        log(job, f"Production script: {len(prod['sections'])} sections, cut into {len(texts)} beats of one or two "
                 f"sentences. Channel: {prod['channel'] or '-'}. Data note: {prod['cutoff'] or '-'}.")
        if prod["channel"] and isinstance(req.get("render"), dict):
            req["render"]["channel"] = prod["channel"]
    else:
        prod = None
        parsed = parse_script(raw)
        texts = [p_["text"] for p_ in parsed]
        sections = [p_["section"] for p_ in parsed]
    if not texts or not any(texts):
        raise RuntimeError("Paste the script you recorded, so captions and maps can follow it.")
    log(job, f"Script: {len(texts)} scenes. Section markers like [India — 0:20] are treated as headings, not speech; "
             "short lines are joined so each scene lasts about 6-15 seconds.")
    job["progress"] = 5

    log(job, "Reading your audio...")
    x = load_audio_24k(src)
    dur = len(x) / 24000
    log(job, f"Audio length {int(dur // 60)}:{int(dur % 60):02d}")
    peak = int(np.abs(x).max()) if len(x) else 0
    if dur < 2 or peak < 300:
        raise RuntimeError("The audio file looks empty or silent.")
    job["progress"] = 15

    scenes = None
    if prod:
        try:
            if req.get("design", "gemini") != "gemini":
                raise RuntimeError("automatic design chosen")
            ch = (req.get("render") or {}).get("channel") or prod["channel"]
            plan = gemini_array(job, PR.plan_prompt(prod, items, ch), len(items), "the visuals from your directions")
            log(job, "Visual directions turned into scenes by Gemini.")
        except Exception as e:
            plan = PR.rule_plan(prod, items)
            log(job, f"Gemini could not plan the directions ({str(e)[:80]}). Simple plan used: B-roll where you asked "
                     "for it, maps elsewhere. Charts and cards need Gemini.")
        scenes = PR.clean_plan(plan, items, prod, lambda m: log(job, m))
    if scenes is None and req.get("design", "gemini") == "gemini":
        try:
            vis = gemini_visuals(job, texts, lang, sections)
            scenes = []
            for t, v in zip(texts, vis):
                v = v if isinstance(v, dict) else {}
                v["narration"] = t          # the producer's words, always
                if v.get("broll") and v.get("type") != "broll":
                    if v.get("type") in ("map", None) and not (scenes and scenes[-1].get("type") == "broll"):
                        v["type"] = "broll"     # footage was asked for: show it, not a map
                    else:
                        v.pop("broll", None)
                scenes.append(v)
            log(job, "Maps designed by Gemini.")
        except Exception as e:
            log(job, f"Gemini could not design the maps ({str(e)[:80]}). Using automatic maps instead.")
    if scenes is None:
        scenes = auto_visuals(texts, title, lang, sections)
        log(job, "Automatic maps: each scene shows the countries its narration mentions.")
    job["progress"] = 45

    p = load_project(name) or {}
    p.update({"name": name, "title": title or p.get("title") or name, "lang": lang,
              "topic": title, "scenes": scenes, "sources": [],
              "upload": {"file": os.path.basename(src)}})
    if prod:
        p["data_note"] = ("তথ্য: " if lang == "bn" else "Data: ") + prod["cutoff"] if prod["cutoff"] else ""
        p["channel"] = prod["channel"]
    else:
        p.pop("data_note", None)
    p["scenes"] = [normalize_scene(sc) for sc in p["scenes"]]
    words = whisper_words(job, x, lang, os.path.join(d, "upload"), texts) if req.get("whisper", True) else None
    job["progress"] = 55
    if words:
        cov = spoken_coverage(texts, words)
        missing = [i for i, c in enumerate(cov) if c < 0.2]
        if missing and len(missing) < len(texts):
            for i in missing:
                log(job, f"NOT IN YOUR RECORDING, left out: \"{texts[i][:70]}...\"")
            keep = [i for i in range(len(texts)) if i not in missing]
            texts = [texts[i] for i in keep]
            sections = [sections[i] for i in keep]
            p["scenes"] = [p["scenes"][i] for i in keep]
            if p["scenes"] and p["scenes"][0].get("type") != "title" and scenes and scenes[0].get("type") == "title":
                p["scenes"][0]["type"] = "title"
            log(job, f"{len(missing)} scene(s) removed because the voice never says them. "
                     "If they should be in the video, re-record or fix the script and build again.")
    cuts = word_boundaries(texts, words, dur, x) if words else None
    if cuts:
        log(job, "Scene changes found from the recognised words.")
    else:
        if words:
            log(job, "Could not match every scene to the words; using pause detection for the cuts.")
        cuts = scene_boundaries(x, texts)
    cut_scenes(p, x, cuts, words)
    save_project(p)
    job["project"] = name
    log(job, "Scenes start at: " + ", ".join(f"{sc['start']:.1f}s" for sc in p["scenes"]))
    job["progress"] = 60
    if req.get("render"):
        log(job, "Rendering the video...")
        sub = {"log": job["log"], "progress": 0}
        th_err = []

        def go():
            try:
                sub["result"] = render(sub, name, req["render"])
            except Exception as e:
                th_err.append(e)
        th = threading.Thread(target=go, daemon=True)
        th.start()
        while th.is_alive():
            job["progress"] = 60 + int(40 * sub.get("progress", 0) / 100)
            time.sleep(0.5)
        if th_err:
            raise th_err[0]
        return {"project": name, "file": sub["result"]["file"], "credit": sub["result"].get("credit")}
    return {"project": name}


def recut(job, name, cuts):
    p = load_project(name)
    if not p or not p.get("upload"):
        raise RuntimeError("This project has no uploaded audio.")
    src = os.path.join(proj_dir(name), "upload", p["upload"]["file"])
    x = load_audio_24k(src)
    cuts = sorted(float(c) for c in cuts)
    if len(cuts) != len(p["scenes"]) - 1:
        raise RuntimeError(f"Need {len(p['scenes']) - 1} start times, got {len(cuts)}.")
    wf = os.path.join(proj_dir(name), "upload", "words.json")
    words = json.load(open(wf, encoding="utf-8"))["words"] if os.path.exists(wf) else None
    cut_scenes(p, x, cuts, words)
    save_project(p)
    log(job, "Re-cut done.")
    return {"project": name}


# ---------------------------------------------------------------- app --
app = Flask(__name__, static_folder=None)


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.post("/api/music/upload")
def api_music_upload():
    """Add the producer's own track to the music list (marked as theirs, so no credit line is written)."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="No file"), 400
    base, ext = os.path.splitext(os.path.basename(f.filename))
    ext = ext.lower()
    if ext not in (".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"):
        return jsonify(error="Use an mp3, wav, m4a, ogg, aac or flac file"), 400
    name = re.sub(r"[^\w\- ().\u0980-\u09FF]", "_", base).strip() or "my_music"
    fn = name + ext
    f.save(os.path.join(MUSIC, fn))
    cr = music_credits()
    cr[fn] = {"title": name, "user": True, "mood": "your upload", "keywords": []}
    json.dump(cr, open(os.path.join(MUSIC, "credits.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return jsonify(ok=True, file=fn)


@app.post("/api/music/delete")
def api_music_delete():
    fn = os.path.basename((request.json or {}).get("file", ""))
    cr = music_credits()
    if not fn or not (cr.get(fn) or {}).get("user"):
        return jsonify(error="Only your own uploads can be removed here"), 400
    try:
        os.remove(os.path.join(MUSIC, fn))
    except Exception:
        pass
    cr.pop(fn, None)
    json.dump(cr, open(os.path.join(MUSIC, "credits.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return jsonify(ok=True)


@app.get("/music/<path:f>")
def music_file(f):
    return send_from_directory(MUSIC, os.path.basename(f))


@app.get("/api/fonts")
def api_fonts():
    return jsonify([f["family"] for f in font_catalog(bool(request.args.get("rescan")))])


@app.get("/api/settings")
def get_settings():
    s = load_settings()
    s["has_key"] = bool(s.get("gemini_key")) or os.path.exists(os.path.join(PARENT, "gemini_key.txt"))
    s["gemini_key"] = ("*" * 8 + s["gemini_key"][-4:]) if s.get("gemini_key") else ""
    s["voices"] = VOICES
    try:
        sync_user_music()
    except Exception:
        pass
    s["music_files"] = sorted(f for f in os.listdir(MUSIC) if f.lower().endswith((".mp3", ".wav", ".m4a")))
    s["music_moods"] = {k: v.get("mood", "") for k, v in music_credits().items() if isinstance(v, dict)}
    s["output_dir_now"] = out_dir()
    s["music_user"] = [k for k, v in music_credits().items() if isinstance(v, dict) and v.get("user")]
    return jsonify(s)


@app.post("/api/settings")
def post_settings():
    s = load_settings()
    od = ((request.json or {}).get("output_dir") or "").strip()
    if od:
        try:
            os.makedirs(od, exist_ok=True)
            if not os.access(od, os.W_OK):
                raise OSError("not writable")
        except Exception as e:
            return jsonify(error=f"Cannot save videos in {od}: {e}"), 400
    for k, v in (request.json or {}).items():
        if k in DEFAULTS and not (k == "gemini_key" and (not v or v.startswith("*"))):
            s[k] = v
    save_settings(s)
    return jsonify(ok=True)


@app.get("/api/projects")
def projects():
    out = []
    for d in sorted(os.listdir(PROJECTS)):
        f = os.path.join(PROJECTS, d, "project.json")
        if os.path.exists(f):
            try:
                p = json.load(open(f, encoding="utf-8"))
                out.append({"name": d, "title": p.get("title", d), "updated": p.get("updated", "")})
            except Exception:
                pass
    out.sort(key=lambda x: x["updated"], reverse=True)
    return jsonify(out)


@app.get("/api/project/<name>")
def get_project(name):
    p = load_project(name)
    return jsonify(p) if p else (jsonify(error="not found"), 404)


@app.post("/api/project")
def put_project():
    p = request.json or {}
    return jsonify(save_project(p))


@app.post("/api/script")
def api_script():
    return jsonify(job=start_job("script", gen_script, request.json or {}))


@app.post("/api/audio/<name>")
def api_audio(name):
    body = request.json or {}
    only = body.get("scene")
    return jsonify(job=start_job("audio", gen_audio, name, only, bool(body.get("force"))))


@app.post("/api/render/<name>")
def api_render(name):
    return jsonify(job=start_job("render", render, name, request.json or {}))


@app.post("/api/oneclick")
def api_oneclick():
    return jsonify(job=start_job("oneclick", one_click, request.json or {}))


@app.post("/api/own_audio")
def api_own_audio():
    f = request.files.get("audio")
    if not f or not f.filename:
        return jsonify(error="No audio file"), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in AUDIO_EXT:
        return jsonify(error=f"Unsupported audio type {ext}"), 400
    name = safe_name(request.form.get("name") or request.form.get("title") or os.path.splitext(f.filename)[0])
    up = os.path.join(proj_dir(name), "upload")
    os.makedirs(up, exist_ok=True)
    path = os.path.join(up, "original" + ext)
    f.save(path)
    req = {"name": name, "title": request.form.get("title", ""), "script": request.form.get("script", ""),
           "lang": request.form.get("lang", "bn"), "design": request.form.get("design", "gemini"),
           "audio_path": path}
    if request.form.get("render"):
        req["render"] = json.loads(request.form["render"])
    return jsonify(job=start_job("own_audio", build_from_audio, req))


@app.post("/api/recut/<name>")
def api_recut(name):
    return jsonify(job=start_job("recut", recut, name, (request.json or {}).get("cuts", [])))


@app.get("/api/countries")
def api_countries():
    return send_from_directory(HERE, "countries.json")


@app.get("/lib/<path:f>")
def lib(f):
    allowed = {"d3-array.min.js": "d3-array", "d3-geo.min.js": "d3-geo"}
    if f not in allowed:
        abort(404)
    return send_from_directory(os.path.join(ROOT, "node_modules", allowed[f], "dist"), f)


@app.get("/world.json")
def world():
    return send_from_directory(os.path.join(ROOT, "src", "data"), "world.json")


@app.get("/flags/<path:f>")
def flags(f):
    return send_from_directory(os.path.join(ROOT, "public", "flags"), f)


@app.get("/api/job/<jid>")
def api_job(jid):
    j = JOBS.get(jid)
    if not j:
        abort(404)
    return jsonify({k: v for k, v in j.items() if k != "pid"})


@app.get("/media/<name>/<path:f>")
def media(name, f):
    return send_from_directory(proj_dir(name), f)


@app.get("/api/outputs")
def outputs():
    od = out_dir()
    fs = sorted((f for f in os.listdir(od) if f.endswith(".mp4")),
                key=lambda f: os.path.getmtime(os.path.join(od, f)), reverse=True)
    return jsonify(fs)


@app.get("/video/<path:f>")
def video(f):
    return send_from_directory(out_dir(), f)


@app.post("/api/open")
def open_folder():
    what = (request.json or {}).get("what", "outputs")
    if what.startswith("broll"):
        reg = re.sub(r"[^a-z]", "", what.split(":", 1)[1] if ":" in what else "bd") or "bd"
        path = os.path.join(ROOT, "broll", reg)
        os.makedirs(path, exist_ok=True)
    else:
        path = {"outputs": out_dir(), "music": MUSIC, "projects": PROJECTS}.get(what, out_dir())
    if os.name == "nt":
        os.startfile(path)
    return jsonify(ok=True)


@app.post("/api/pick_folder")
def pick_folder():
    """Native Windows folder picker (opens on top of the browser)."""
    ps = ("Add-Type -AssemblyName System.Windows.Forms;"
          "$f=New-Object System.Windows.Forms.Form -Property @{TopMost=$true;ShowInTaskbar=$false};"
          "$d=New-Object System.Windows.Forms.FolderBrowserDialog;$d.ShowNewFolderButton=$true;"
          "$d.Description='Folder for finished videos';"
          f"$d.SelectedPath='{out_dir()}';"
          "if($d.ShowDialog($f) -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;$d.SelectedPath}")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        return jsonify(path=(r.stdout or "").strip())
    except Exception as e:
        return jsonify(path="", error=str(e))


@app.post("/api/quit")
def quit_app():
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return jsonify(ok=True)


if __name__ == "__main__":
    if "--open" in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    app.run(host="127.0.0.1", port=PORT, threaded=True)
