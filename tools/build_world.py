"""Natural Earth 50m countries -> src/data/world.json (geometry) + studio/countries.json (names for the UI)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "assets", "geo", "ne_50m_admin_0_countries.geojson")
OUT = os.path.join(HERE, "..", "src", "data", "world.json")
OUT_UI = os.path.join(HERE, "..", "studio", "countries.json")

# Common names people actually type (English + Bangla), beyond Natural Earth's own.
EXTRA = {
    "USA": ["USA", "US", "America", "United States", "আমেরিকা", "যুক্তরাষ্ট্র"],
    "GBR": ["UK", "Britain", "England", "ব্রিটেন", "ইংল্যান্ড"],
    "CHN": ["চীন", "PRC"], "MMR": ["Burma", "বার্মা", "মায়ানমার"],
    "IND": ["Bharat", "ইন্ডিয়া"], "BGD": ["Bangladesh", "বাংলাদেশ"],
    "RUS": ["Russian Federation", "রুশ"], "KOR": ["Korea", "কোরিয়া"],
    "PRK": ["DPRK"], "ARE": ["UAE", "আমিরাত", "দুবাই"], "IRN": ["Persia"],
    "SAU": ["KSA", "সৌদি"], "PSE": ["Palestine", "ফিলিস্তিন", "গাজা", "Gaza"],
    "ISR": ["ইসরাইল"], "TUR": ["Turkiye", "Türkiye", "তুর্কি"],
    "LKA": ["Ceylon"], "COD": ["DR Congo", "DRC"], "CZE": ["Czech Republic"],
    "MDV": ["মালদ্বীপ"], "MYS": ["মালয়শিয়া"], "PAK": ["পাকিস্থান"],
}

def rnd(c):
    if isinstance(c[0], (int, float)):
        return [round(c[0], 3), round(c[1], 3)]
    return [rnd(x) for x in c]

d = json.load(open(SRC, encoding="utf-8"))
feats, ui = [], []
for f in d["features"]:
    p = f["properties"]
    if p.get("ADMIN") == "Antarctica":
        continue
    iso = p.get("ISO_A3_EH") if p.get("ISO_A3_EH") not in (None, "-99") else p.get("ADM0_A3")
    iso2 = p.get("ISO_A2_EH") if p.get("ISO_A2_EH") not in (None, "-99") else ""
    names = {p.get(k) for k in ("NAME", "NAME_LONG", "ADMIN", "NAME_EN", "NAME_SORT", "BRK_NAME", "FORMAL_EN", "NAME_BN", "ABBREV") if p.get(k)}
    names |= set(EXTRA.get(iso, []))
    aliases = sorted(n for n in names if n)
    bn = p.get("NAME_BN") or p.get("NAME")
    if iso == "CHN":
        bn = "চীন"  # NE uses গণচীন; চীন is what viewers expect
    feats.append({"type": "Feature",
                  "properties": {"iso": iso, "iso2": iso2.lower(), "name": p.get("NAME"), "bn": bn,
                                 "aliases": aliases, "lx": p.get("LABEL_X"), "ly": p.get("LABEL_Y"),
                                 "rank": p.get("LABELRANK")},
                  "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"])}})
    ui.append({"iso": iso, "iso2": iso2.lower(), "name": p.get("NAME"), "bn": bn, "aliases": aliases,
               "lx": p.get("LABEL_X"), "ly": p.get("LABEL_Y")})
json.dump({"type": "FeatureCollection", "features": feats}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump(sorted(ui, key=lambda x: x["name"]), open(OUT_UI, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(feats), os.path.getsize(OUT), os.path.getsize(OUT_UI))
