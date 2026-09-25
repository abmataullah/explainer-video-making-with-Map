"""Download the music library (Kevin MacLeod / incompetech, CC BY 4.0) and the sound effects
(Mixkit free licence, BigSoundBank CC0). Run once after cloning:  python tools/get_audio.py
These files are not stored in the repository."""
import json, os, re, subprocess, urllib.parse, urllib.request
G = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC = os.path.join(G, "music")
SFX = os.path.join(G, "public", "sfx", "lib")
os.makedirs(SFX, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
pieces = {p["title"]: p for p in json.load(urllib.request.urlopen(urllib.request.Request(
    "https://incompetech.com/music/royalty-free/pieces.json", headers=UA), timeout=60))}

TRACKS = {  # title: (group, pools)
 "Hitman": ("orchestra", "war power-games tension"), "Clash Defiant": ("orchestra", "war power-games"),
 "Five Armies": ("orchestra", "war"), "Colossus": ("orchestra", "war"), "Crusade": ("orchestra", "sombre history"),
 "Gloom Horizon": ("orchestra", "tension environment power-games"), "Enter the Maze": ("orchestra", "tension spy mystery"),
 "Darkness is Coming": ("orchestra", "tension war"), "Death of Kings": ("orchestra", "sombre humanitarian"),
 "Big Drumming": ("drums", "war trade-strategy"), "Firebrand": ("drums", "war trade-strategy"),
 "Drums of the Deep": ("drums", "tension environment"), "Asian Drums": ("drums", "tension mystery"),
 "Controlled Chaos": ("drums", "tension mystery"), "Darkening Developments": ("drums", "tension spy"),
 "Killers": ("guitar", "war tension"), "I Can Feel it Coming": ("guitar", "spy tension trade-strategy"),
 "Bet You Can ver 2": ("guitar", "power-games tension"), "Night of Chaos": ("guitar", "mystery tension"),
 "At Launch": ("orchestra", "hopeful victory"), "Dhaka": ("other", "history"),
}
cred_path = os.path.join(MUSIC, "credits.json")
cred = json.load(open(cred_path, encoding="utf-8")) if os.path.exists(cred_path) else {}
# tracks already listed in credits.json (the original library)
for fn, c in list(cred.items()):
    if fn.startswith("_") or not isinstance(c, dict) or c.get("user") or os.path.exists(os.path.join(MUSIC, fn)):
        continue
    try:
        data = urllib.request.urlopen(urllib.request.Request(
            "https://incompetech.com/music/royalty-free/mp3-royaltyfree/" + urllib.parse.quote(fn), headers=UA), timeout=120).read()
        if len(data) > 200000:
            open(os.path.join(MUSIC, fn), "wb").write(data); print("ok", fn)
    except Exception as e:
        print("FAIL", fn, str(e)[:60])
for title, (grp, pools) in TRACKS.items():
    p = pieces.get(title)
    if not p:
        print("not in catalogue:", title); continue
    fn = p["filename"]
    dst = os.path.join(MUSIC, fn)
    if not os.path.exists(dst) or os.path.getsize(dst) < 200000:
        url = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/" + urllib.parse.quote(fn)
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
            if len(data) < 200000:
                raise RuntimeError("too small")
            open(dst, "wb").write(data)
        except Exception as e:
            print("FAIL", title, str(e)[:60]); continue
    feel = (p.get("feel") or "").strip()
    cred[fn] = {"title": title, "mood": feel.lower(), "group": grp, "pools": pools.split(),
                "instruments": (p.get("instruments") or "").strip(), "tension": "hopeful" not in pools,
                "keywords": cred.get(fn, {}).get("keywords", [])}
    print("ok", title, "|", feel, "|", grp)
json.dump(cred, open(cred_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ---- SFX
def mixkit(slug):
    t = urllib.request.urlopen(urllib.request.Request(f"https://mixkit.co/free-sound-effects/{slug}/", headers=UA), timeout=40).read().decode("utf-8", "replace")
    toks = [(m.start(), "t", m.group(1).strip()) for m in re.finditer(r"<h2[^>]*>\s*([^<]{3,80}?)\s*</h2>", t)]
    toks += [(m.start(), "u", m.group(0)) for m in re.finditer(r"https://assets\.mixkit\.co/active_storage/sfx/\d+/\d+-preview\.mp3", t)]
    toks.sort(); out, cur = {}, None
    for _, k, v in toks:
        if k == "t": cur = v
        elif cur and cur not in out: out[cur] = v; cur = None
    return out
SFX_LIST = {  # key: (source, category or id, title, kind, default volume)
 "rain": ("mk", "rain", "Long rain ambience", "amb", 0.35), "storm": ("mk", "rain", "Rain and thunder storm", "amb", 0.35),
 "thunder": ("mk", "rain", "Thunder rumble during a storm", "hit", 0.6), "water": ("mk", "water", "River water flowing", "amb", 0.35),
 "flood": ("mk", "water", "Waterfall ambience", "amb", 0.3), "waves": ("mk", "water", "Sea waves ambience", "amb", 0.3),
 "wind": ("mk", "wind", "Wind blowing ambience", "amb", 0.35), "explosion": ("mk", "explosion", "Explosion in battle", "hit", 0.55),
 "explosions_far": ("mk", "war", "Far away war explosions", "amb", 0.35), "bomb": ("mk", "war", "Bomb explosion in battle", "hit", 0.55),
 "war": ("mk", "war", "War explosions", "amb", 0.3), "fire": ("mk", "fire", "Campfire crackles", "amb", 0.35),
 "protest": ("mk", "crowd", "Rioting Crowd", "amb", 0.3), "crowd_angry": ("mk", "crowd", "Angry male crowd ambience", "amb", 0.3),
 "cheer": ("mk", "crowd", "Huge crowd cheering victory", "hit", 0.45), "press": ("mk", "crowd", "Reporters crowd and camera flashes", "amb", 0.3),
 "march": ("mk", "war", "Big army crowd marching", "amb", 0.3), "war_drums": ("mk", "gun", "Drums of war call", "hit", 0.45),
 "war_horn": ("mk", "war", "War horn ambience", "hit", 0.4), "fanfare": ("mk", "cinematic", "Trumpet fanfare", "hit", 0.45),
 "siren": ("mk", "siren", "Ambulance siren UK", "amb", 0.25), "police": ("mk", "siren", "Police siren US", "amb", 0.25),
 "alarm": ("mk", "alarm", "Facility alarm sound", "hit", 0.3), "helicopter": ("mk", "helicopter", "Helicopter flying in the sky", "amb", 0.35),
 "heartbeat": ("mk", "cinematic", "Cinematic heartbeat ambience", "amb", 0.4), "drumroll": ("mk", "suspense", "Tension and suspense drum roll", "hit", 0.45),
 "riser": ("mk", "cinematic", "Cinematic trailer riser", "hit", 0.4), "impact": ("mk", "cinematic", "Big cinematic impact", "hit", 0.5),
 "clock": ("mk", "suspense", "Tick tock clock close up", "amb", 0.3), "drone": ("mk", "suspense", "Tactical drone ambience", "amb", 0.3),
 "gunshot": ("bsb", "2853", "Rifle: Shot", "hit", 0.5), "gunshot2": ("bsb", "0397", "Shot of Winchester Magnum XTR", "hit", 0.5),
 "gunfire": ("bsb", "0437", "Shot Beretta M12 9mm", "hit", 0.5),
}
cache = {}
lib = {}
for key, (src, cat, title, kind, vol) in SFX_LIST.items():
    dst = os.path.join(SFX, key + ".mp3")
    try:
        if src == "mk":
            if cat not in cache:
                cache[cat] = mixkit(cat)
            url = cache[cat].get(title)
            if not url:
                print("SFX missing on page:", key, title); continue
            lic = "Mixkit Sound Effects Free License (mixkit.co)"
        else:
            url = f"https://bigsoundbank.com/UPLOAD/mp3/{cat}.mp3"
            lic = "BigSoundBank.com, CC0 (Joseph Sardin)"
        raw = dst + ".raw.mp3"
        if not os.path.exists(dst):
            open(raw, "wb").write(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            # even loudness, max 30 s, short fades
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-t", "30", "-af",
                            "loudnorm=I=-18:TP=-2,afade=t=in:d=0.05", "-ar", "44100", "-b:a", "160k", dst], check=True)
            os.remove(raw)
        lib[key] = {"title": title, "kind": kind, "vol": vol, "license": lic}
        print("sfx ok", key)
    except Exception as e:
        print("SFX FAIL", key, str(e)[:80])
json.dump(lib, open(os.path.join(SFX, "library.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE")