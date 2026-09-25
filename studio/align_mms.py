"""Forced alignment of a KNOWN script to speech (torchaudio MMS_FA + uroman).
Works for Bangla, where Whisper small cannot transcribe reliably.
usage (envs/wav2lip python): align_mms.py voice16k.wav words.json out.json
words.json: ["word", ...] in spoken order.  out.json: {"times": [[s, e] or null, ...]}
"""
import glob, json, os, re, site, sys


def add_nvidia_dlls():
    for sp in site.getsitepackages():
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(d)
            except Exception:
                pass
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def main():
    wav_path, words_path, out_path = sys.argv[1:4]
    add_nvidia_dlls()
    import torch, torchaudio
    import uroman as ur
    words = json.load(open(words_path, encoding="utf-8"))
    u = ur.Uroman()
    rom = []
    for w in words:
        r = u.romanize_string(w).lower()
        r = re.sub(r"[^a-z']", "", r)
        rom.append(r)
    keep = [i for i, r in enumerate(rom) if r]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model(with_star=False).to(dev)
    tokenizer, aligner = bundle.get_tokenizer(), bundle.get_aligner()
    wav, sr = torchaudio.load(wav_path)
    wav = wav.mean(0, keepdim=True)
    if sr != bundle.sample_rate:
        wav = torchaudio.functional.resample(wav, sr, bundle.sample_rate)
    # emissions in 20 s chunks keeps an 8 GB card safe on long narrations
    chunk = bundle.sample_rate * 20
    ems = []
    with torch.inference_mode():
        for a in range(0, wav.size(1), chunk):
            e, _ = model(wav[:, a:a + chunk].to(dev))
            ems.append(e.cpu())
    emission = torch.cat(ems, dim=1)
    tokens = tokenizer([rom[i] for i in keep])
    spans = aligner(emission[0], tokens)
    ratio = wav.size(1) / emission.size(1) / bundle.sample_rate
    times = [None] * len(words)
    for i, sp in zip(keep, spans):
        times[i] = [round(sp[0].start * ratio, 3), round(sp[-1].end * ratio, 3)]
    json.dump({"device": dev, "times": times}, open(out_path, "w", encoding="utf-8"))
    print(dev, sum(t is not None for t in times), "/", len(words))


if __name__ == "__main__":
    main()