"""Word timestamps for an uploaded narration, on the GPU when available.
Run with envs/wav2lip python:  python align_whisper.py in.wav lang out.json
Output: {"device": "...", "words": [{"s": start, "e": end, "w": "word"}]}
"""
import glob, json, os, sys, site


def add_nvidia_dlls():
    # pip wheels nvidia-cublas-cu12 / nvidia-cudnn-cu12 put DLLs in site-packages/nvidia/*/bin
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(d)
            except Exception:
                pass
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def main():
    wav, lang, out = sys.argv[1], sys.argv[2], sys.argv[3]
    model_name = sys.argv[4] if len(sys.argv) > 4 else "small"  # already downloaded; accurate enough for timing
    add_nvidia_dlls()
    from faster_whisper import WhisperModel
    device = "cuda"
    try:
        m = WhisperModel(model_name, device="cuda", compute_type="float16")
        segs, info = m.transcribe(wav, language=lang, word_timestamps=True, vad_filter=False, beam_size=5)
        segs = list(segs)
    except Exception as e:
        sys.stderr.write(f"GPU failed ({e}); using CPU\n")
        device = "cpu"
        m = WhisperModel(model_name, device="cpu", compute_type="int8")
        segs, info = m.transcribe(wav, language=lang, word_timestamps=True, vad_filter=False, beam_size=5)
        segs = list(segs)
    words = [{"s": round(w.start, 3), "e": round(w.end, 3), "w": w.word} for s in segs for w in (s.words or [])]
    json.dump({"device": device, "model": model_name, "words": words}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(device, len(words))


if __name__ == "__main__":
    main()
