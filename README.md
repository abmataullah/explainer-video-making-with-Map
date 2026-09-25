# GeoExplainer: map-based explainer videos (Bangla and English)

A local studio that turns a topic, or your own recorded narration, into a geopolitics explainer video with
animated maps, charts, B-roll, captions, music and sound effects. It runs on your PC in the browser at
`http://localhost:7870`.

## What it does

- **Script and voice:** Gemini writes the scene plan and reads it with its TTS voices, or you upload your own recording and script.
- **Own-audio sync:** your script is matched to the recording word by word (MMS forced alignment), so scene cuts and captions follow the voice.
- **Map scenes**
  - `map`: flat map with a moving camera, coloured countries, arrows and points
  - `globe`: rotating 3D globe
  - `choropleth`: countries shaded by a number, with legend
  - `spread`: something spreading **inside** a country (flood, conflict, protest, fire, drought, disease, control, cyclone path), district by district or as a flowing patch, with a live counter
- **Charts drawn in R and animated frame by frame:** bar, hbar, lollipop, line, area, stacked, donut, pie, waffle, treemap. Bangla digits and your chosen font.
- **Cards:** title, count-up stat with percentage ring, bullets, quote, timeline, compare.
- **B-roll:** stock footage from Pexels.
- **Looks:** Classic, HUD (dark grid, red accent, corner labels), Light editorial.
- **Branding:** channel list with add/remove, and separate fonts for titles and captions (every installed Bangla font is listed).
- **Music:** tension-first library chosen by mood without repeats, your own uploads, a volume slider with preview, and a lift in the intro and outro.
- **Sound effects:** 33 of them (rain, flood, storm, gunfire, explosions, crowd, fanfare, sirens, heartbeat and more), chosen automatically from the narration or set per scene.
- **Extra files per video:** `.srt` captions, `_YOUTUBE.txt` (chapters, sources, credits) and `_thumbnail.jpg`.

## Requirements

- Windows 10/11 (other systems should work with small path changes)
- Node.js 18+ and FFmpeg on PATH
- Python 3.10+ with `pip install -r requirements.txt`
- R 4.x with `ggplot2 ragg systemfonts textshaping scales jsonlite treemapify` (for charts)
- A Gemini API key from aistudio.google.com (optional if you always use your own audio)
- A free Pexels API key for B-roll (optional)
- An NVIDIA GPU makes speech alignment fast (it also runs on the CPU)

## Setup

```bat
git clone https://github.com/abmataullah/explainer-video-making-with-Map
cd explainer-video-making-with-Map
npm install
pip install -r requirements.txt
python tools\get_audio.py          :: downloads the music and sound effects (not stored in this repo)
python tools\build_world.py        :: only if src/data/world.json is missing
cd studio
python server.py --open
```

Open **Settings** in the studio and paste your Gemini key and, if you want B-roll, your Pexels key.
They are saved in `settings.json`, which is ignored by git.

If the speech-alignment packages live in a different Python, point to it before starting:
`set GEO_ALIGN_PY=C:\path\to\python.exe`

Extra Bangla fonts: copy the `.ttf` into `fonts/` and restart.

## Using it

1. Type a topic and press **Make the whole video**, or choose **I have my own audio** and upload the recording with its script.
2. Check the scenes. Every scene type has its own editor (spread districts, chart data, B-roll search, sound effects...).
3. Pick the channel, look, fonts and music, then **Render video**. Files land in `outputs/`.

More detail: `HOW TO USE.txt`.

## Credits and licences

- Music: Kevin MacLeod (incompetech.com), CC BY 4.0. The credit is written to `_CREDITS.txt` / `_YOUTUBE.txt` for each video.
- Sound effects: Mixkit (Mixkit Sound Effects Free License) and BigSoundBank.com (CC0). They are downloaded by `tools/get_audio.py`, not redistributed here.
- District and province boundaries: geoBoundaries (for Bangladesh: BBS and OCHA ROAP), CC BY 3.0 IGO. The credit is added to `_YOUTUBE.txt` automatically.
- World map: Natural Earth via world-atlas. Flags: flag-icons (MIT).
- Rendering: Remotion. Charts: R, ggplot2 and ragg. Alignment: torchaudio MMS forced aligner and faster-whisper.

Check Remotion's licence terms if you use this commercially as a company.