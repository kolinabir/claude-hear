# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = [
#   "mlx-whisper>=0.4; sys_platform == 'darwin' and platform_machine == 'arm64'",
#   "faster-whisper>=1.1; sys_platform != 'darwin' or platform_machine != 'arm64'",
#   "numpy",
# ]
# ///
"""Speech to text with word timings.

Apple Silicon: mlx-whisper on the GPU. Windows, Linux, Intel Macs: faster-whisper,
on an NVIDIA GPU when CUDA works, otherwise on the CPU (int8).
"""
import os
import platform
import sys
import time
from pathlib import Path

from common import load, save

APPLE = sys.platform == "darwin" and platform.machine() == "arm64"


def transcribe_mlx(y, model, language):
    import mlx.core as mx
    import mlx_whisper

    mx.set_cache_limit(0)  # measured on a 40 s clip: peak 3.19 -> 2.43 GB for ~2-3 s more
    r = mlx_whisper.transcribe(y, path_or_hf_repo=model, word_timestamps=True, language=language)
    segments = [{"start": s["start"], "end": s["end"],
                 "words": [{k: w[k] for k in ("word", "start", "end", "probability")} for w in s.get("words", [])]}
                for s in r["segments"]]
    return r.get("language"), segments, mx.get_peak_memory()


def transcribe_fw(y, model, language):
    import ctranslate2
    from faster_whisper import WhisperModel

    name = "turbo" if "turbo" in model else model.split("/")[-1].removeprefix("whisper-")
    attempts = [("cuda", "float16")] if ctranslate2.get_cuda_device_count() > 0 else []
    for device, compute in attempts + [("cpu", "int8")]:
        try:
            # all cores: measured 72 s -> 34 s on a 40 s clip (the default uses only a few)
            m = WhisperModel(name, device=device, compute_type=compute, cpu_threads=os.cpu_count() or 4)
            segs, info = m.transcribe(y, word_timestamps=True, language=language)
            segments = [{"start": s.start, "end": s.end,
                         "words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                                   for w in (s.words or [])]}
                        for s in segs]  # the generator runs the model here, so CUDA errors surface inside the try
            return info.language, segments, 0
        except RuntimeError as e:  # CUDA libraries missing (common on Windows): fall back to CPU
            if device == "cpu":
                raise
            print(f"GPU failed ({e}); using CPU", file=sys.stderr)


if __name__ == "__main__":
    out, language, model = Path(sys.argv[1]), sys.argv[2] or None, sys.argv[3]
    t0 = time.time()
    lang, segments, gpu = (transcribe_mlx if APPLE else transcribe_fw)(load(out), model, language)
    save(out, "asr", {"language": lang, "segments": [s for s in segments if s["words"]]}, t0, gpu)
