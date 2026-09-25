"""Stock footage/photo search — Pexels & Pixabay (free API keys).

search_pexels(query, key, media="video"|"photo") -> [{id, preview, url, file}]
search_pixabay(query, key, media) -> same
download(url, out) -> path

`file` is the best download URL (for video: hd file; for photo: large).
"""
import json, os, urllib.parse, urllib.request


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _get(url, headers=None):
    h = {"User-Agent": UA}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def search_pexels(query, key, media="video", per_page=8, orientation="landscape"):
    q = urllib.parse.quote(query)
    if media == "video":
        url = f"https://api.pexels.com/videos/search?query={q}&per_page={per_page}&orientation={orientation}"
        data = _get(url, {"Authorization": key})
        out = []
        for v in data.get("videos", []):
            target = 720 if orientation == "portrait" else 1280
            files = sorted([f for f in v.get("video_files", []) if f.get("link")],
                           key=lambda f: abs((f.get("width") or 0) - target))
            best = next((f for f in files if f.get("quality") == "hd"), files[0] if files else None)
            if best:
                out.append({"id": v["id"], "preview": v.get("image", ""),
                            "url": v.get("url", ""), "file": best["link"],
                            "dur": v.get("duration", 0), "kind": "video"})
        return out
    url = f"https://api.pexels.com/v1/search?query={q}&per_page={per_page}&orientation={orientation}"
    data = _get(url, {"Authorization": key})
    return [{"id": p["id"], "preview": p["src"]["medium"],
             "url": p["url"], "file": p["src"]["large2x"], "kind": "photo"}
            for p in data.get("photos", [])]


def search_pixabay(query, key, media="video", per_page=8, orientation="landscape"):
    q = urllib.parse.quote(query)
    if media == "video":
        url = (f"https://pixabay.com/api/videos/?key={key}&q={q}"
               f"&per_page={per_page}")
        data = _get(url)
        out = []
        for v in data.get("hits", []):
            vids = v.get("videos", {})
            best = vids.get("large") or vids.get("medium") or vids.get("small")
            if best:
                prev = v.get("picture_id")
                out.append({"id": v["id"],
                            "preview": (f"https://i.vimeocdn.com/video/{prev}_640x360.jpg"
                                        if prev else ""),
                            "url": v.get("pageURL", ""), "file": best["url"],
                            "dur": v.get("duration", 0), "kind": "video"})
        return out
    url = f"https://pixabay.com/api/?key={key}&q={q}&per_page={per_page}&image_type=photo&orientation=horizontal"
    data = _get(url)
    return [{"id": p["id"], "preview": p["webformatURL"],
             "url": p["pageURL"], "file": p["largeImageURL"], "kind": "photo"}
            for p in data.get("hits", [])]


def download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return out_path
