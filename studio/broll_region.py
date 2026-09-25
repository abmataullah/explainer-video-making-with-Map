"""Region-true B-roll: footage must come from the country the scene is about.

Order for each B-roll scene:
  1. your own clips in  broll/<region>/  whose file name matches the search words
  2. Pexels / Pixabay clips whose page description names the region (dhaka, bangladesh, riyadh, arab ...)
  3. any unused clip from your own broll/<region>/ folder
  4. nothing verified: the caller shows the map instead (strict mode)
"""
import os, re, random

REGIONS = {
    "bd": {"name": "Bangladesh", "bn": "বাংলাদেশ", "isos": ["BGD"],
           "prefix": ["Bangladesh", "Dhaka", "Bangladeshi"],
           "rx": r"bangladesh|dhaka|chittagong|chattogram|sylhet|bengali|bangla|cox.?s.?bazar|sundarban|khulna|rajshahi|"
                 r"rohingya|buriganga|padma|jamuna|meghna|sandwip|kishoreganj|rangpur|barisal|mymensingh|comilla|narayanganj|gazipur|bogra|srimangal"},
    "arab": {"name": "Arab world", "bn": "আরব বিশ্ব",
             "isos": ["SAU", "ARE", "QAT", "OMN", "KWT", "BHR", "JOR", "EGY", "IRQ", "SYR", "LBN", "PSE", "YEM", "LBY", "TUN", "DZA", "MAR", "SDN"],
             "prefix": ["Arab", "Saudi Arabia", "Middle East"],
             "rx": r"arab|saudi|dubai|emirat|uae|qatar|doha|oman|muscat|kuwait|bahrain|jordan|amman|egypt|cairo|riyadh|jeddah|mecca|makkah|"
                   r"medina|madina|abu.?dhabi|yemen|iraq|baghdad|syria|damascus|lebanon|beirut|palestin|gaza|morocco|marrakech|tunisia|algeria|libya|sudan"},
    "india": {"name": "India", "bn": "ভারত", "isos": ["IND"], "prefix": ["India", "Indian"],
              "rx": r"india|delhi|mumbai|kolkata|calcutta|bengaluru|bangalore|chennai|varanasi|jaipur|agra|kerala|goa|hyderabad|assam|punjab|rajasthan"},
    "pakistan": {"name": "Pakistan", "bn": "পাকিস্তান", "isos": ["PAK"], "prefix": ["Pakistan", "Pakistani"],
                 "rx": r"pakistan|karachi|lahore|islamabad|peshawar|quetta|punjab|sindh|balochistan"},
    "myanmar": {"name": "Myanmar", "bn": "মিয়ানমার", "isos": ["MMR"], "prefix": ["Myanmar", "Burma"],
                "rx": r"myanmar|burma|burmese|yangon|rangoon|mandalay|bagan|rakhine|naypyidaw|rohingya"},
    "china": {"name": "China", "bn": "চীন", "isos": ["CHN", "HKG", "TWN"], "prefix": ["China", "Chinese"],
              "rx": r"china|chinese|beijing|shanghai|shenzhen|guangzhou|hong.?kong|taiwan|taipei|chongqing|wuhan|xinjiang|tibet"},
    "iran": {"name": "Iran", "bn": "ইরান", "isos": ["IRN"], "prefix": ["Iran", "Tehran"], "rx": r"iran|tehran|persian|isfahan|shiraz|tabriz|mashhad"},
    "turkey": {"name": "Turkey", "bn": "তুরস্ক", "isos": ["TUR"], "prefix": ["Turkey", "Istanbul"], "rx": r"turkey|turkiye|turkish|istanbul|ankara|izmir|cappadocia"},
    "afghanistan": {"name": "Afghanistan", "bn": "আফগানিস্তান", "isos": ["AFG"], "prefix": ["Afghanistan", "Kabul"], "rx": r"afghan|afghanistan|kabul|kandahar|herat"},
    "nepal": {"name": "Nepal", "bn": "নেপাল", "isos": ["NPL"], "prefix": ["Nepal", "Kathmandu"], "rx": r"nepal|kathmandu|pokhara|himalaya"},
    "srilanka": {"name": "Sri Lanka", "bn": "শ্রীলঙ্কা", "isos": ["LKA"], "prefix": ["Sri Lanka", "Colombo"], "rx": r"sri.?lanka|colombo|kandy|galle"},
    "russia": {"name": "Russia", "bn": "রাশিয়া", "isos": ["RUS"], "prefix": ["Russia", "Moscow"], "rx": r"russia|moscow|kremlin|st.?petersburg|siberia"},
    "ukraine": {"name": "Ukraine", "bn": "ইউক্রেন", "isos": ["UKR"], "prefix": ["Ukraine", "Kyiv"], "rx": r"ukrain|kyiv|kiev|kharkiv|odesa|odessa|lviv"},
    "usa": {"name": "United States", "bn": "যুক্তরাষ্ট্র", "isos": ["USA"], "prefix": ["United States", "Washington"],
            "rx": r"usa|united.?states|america|new.?york|washington|white.?house|capitol|los.?angeles|chicago|texas|california"},
    "global": {"name": "Anywhere", "bn": "যেকোনো", "isos": [], "prefix": [], "rx": ""},
}
ISO_REGION = {iso: k for k, r in REGIONS.items() for iso in r["isos"]}
STOP = {"a", "an", "the", "of", "in", "on", "at", "and", "with", "for", "to", "from", "by", "shot", "footage", "stock",
        "cinematic", "wide", "close", "view", "scene", "aerial", "4k", "hd", "video", "clip"}
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv")


def detect_region(scenes, lang="bn"):
    """Region of the whole video: the most-shown country; a Bangla video about Bangladesh stays Bangladeshi."""
    count = {}
    for sc in scenes or []:
        for iso in (sc.get("focus") or []) + list((sc.get("highlight") or {}).keys()):
            r = ISO_REGION.get(str(iso).upper())
            if r:
                count[r] = count.get(r, 0) + 1
    if lang == "bn" and count.get("bd"):
        count["bd"] += 2          # home country wins ties in Bangla videos
    if count:
        return max(count, key=count.get)
    return "bd" if lang == "bn" else "global"


def scene_region(sc, video_region):
    """A B-roll scene follows its own first country when that country has a region (Saudi scene -> Arab footage)."""
    for iso in sc.get("focus") or []:
        r = ISO_REGION.get(str(iso).upper())
        if r:
            return r
    return video_region


def _words(text):
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]+", text or "") if w.lower() not in STOP]


def verified(item, region):
    rx = REGIONS.get(region, {}).get("rx")
    if not rx:
        return True
    text = ((item.get("url") or "").rstrip("/").split("/")[-1] + " " + (item.get("tags") or "")).lower()
    # whole words only (a small suffix allowed: bangladeshi, arabic, egyptian); "woman" must not count as "oman"
    return bool(re.search(r"(?<![a-z])(?:" + rx + r")[a-z]{0,4}(?![a-z])", text))


def local_library(root, region):
    d = os.path.join(root, "broll", region)
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(VIDEO_EXT)]


def find_broll(query, region, *, root, stock, pexels_key="", pixabay_key="", used=None, need=6.0,
               orientation="landscape", strict=True, log=print, cache_dir=None):
    """Returns (path_or_url, source_label, is_remote) or None."""
    used = used if used is not None else set()
    words = _words(query)
    R = REGIONS.get(region) or REGIONS["global"]
    lib = [p for p in local_library(root, region) if p not in used]
    # 1. own clips whose file name shares a word with the search
    scored = sorted(((sum(w in os.path.basename(p).lower() for w in words), p) for p in lib), reverse=True)
    if scored and scored[0][0] > 0:
        used.add(scored[0][1])
        return scored[0][1], f"your {R['name']} clip {os.path.basename(scored[0][1])}", False
    # 2. stock footage that names the region
    base = " ".join(words[:3]) or "city"
    qs = []
    for pre in R["prefix"][:2]:
        qs.append(f"{pre} {base}")
    if words:
        qs += [f"{R['prefix'][0]} {max(words, key=len)}"] if R["prefix"] else []
    qs += [base] + ([R["prefix"][0]] if R["prefix"] else [])
    qs = list(dict.fromkeys(q.strip() for q in qs if q.strip()))
    for q in qs:
        for prov, key in (("pexels", pexels_key), ("pixabay", pixabay_key)):
            if not key:
                continue
            try:
                fn = stock.search_pexels if prov == "pexels" else stock.search_pixabay
                res = [r for r in fn(q, key, "video", 40, orientation) if f"{prov}_{r['id']}" not in used]
            except Exception as e:
                log(f"  {prov} search failed for '{q}': {str(e)[:80]}")
                continue
            good = [r for r in res if verified(r, region)] if (strict and region != "global") else res
            if not good:
                continue
            long_ = [r for r in good if (r.get("dur") or 0) >= need]
            r = (long_ or sorted(good, key=lambda r: -(r.get("dur") or 0)))[0]
            used.add(f"{prov}_{r['id']}")
            slug = (r.get("url") or "").rstrip("/").split("/")[-1][:60]
            return (prov, r), f"{prov} '{slug}'", True
    # 3. any unused own clip for the region
    if lib:
        p = random.Random(query).choice(lib)
        used.add(p)
        return p, f"your {R['name']} clip {os.path.basename(p)}", False
    return None