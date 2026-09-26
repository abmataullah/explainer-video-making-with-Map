"""IndicF5 Bangla voice worker. Runs inside envs\\indicf5 (called by make_video.py).

Reads a JSON job file: {"ref_audio": ..., "ref_text": ..., "items": [{"text": ..., "out": ...}]}
and writes one 24 kHz wav per item. The model is loaded once for the whole batch.
"""
import json
import sys

import numpy as np
import soundfile as sf
import torch
from transformers import AutoModel


def main(job_path):
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    print("Loading IndicF5 ...", flush=True)
    # The model's own code picks the GPU; low_cpu_mem_usage=False stops newer
    # transformers from building it on the empty "meta" device first.
    model = AutoModel.from_pretrained("ai4bharat/IndicF5", trust_remote_code=True,
                                      low_cpu_mem_usage=False)
    # The weights load onto the CPU; move them to the GPU (minutes -> seconds per sentence).
    if torch.cuda.is_available():
        model = model.to("cuda")
    print("GPU:", model.device, flush=True)
    for n, item in enumerate(job["items"], 1):
        print(f"  voice {n}/{len(job['items'])}", flush=True)
        audio = model(item["text"], ref_audio_path=job["ref_audio"], ref_text=job["ref_text"])
        audio = np.asarray(audio)
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        sf.write(item["out"], audio.astype(np.float32), samplerate=24000)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main(sys.argv[1])
