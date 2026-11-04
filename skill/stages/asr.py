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
    prob = None
    if not language:  # how sure is the detection? (Bengali speech comes out as Gujarati at ~0.45: the report must say so)
        from mlx_whisper.audio import log_mel_spectrogram, pad_or_trim
        from mlx_whisper.decoding import detect_language
        from mlx_whisper.transcribe import ModelHolder
        m = ModelHolder.get_model(model, mx.float16)  # the same cached copy transcribe() uses
        _, probs = detect_language(m, pad_or_trim(log_mel_spectrogram(mx.array(y[:16000 * 30]), n_mels=m.dims.n_mels), 3000, axis=-2).astype(mx.float16))
        probs = probs[0] if isinstance(probs, list) else probs
        language, prob = max(probs, key=probs.get), round(float(max(probs.values())), 2)
    r = mlx_whisper.transcribe(y, path_or_hf_repo=model, word_timestamps=True, language=language)
    segments = [{"start": s["start"], "end": s["end"],
                 "words": [{k: w[k] for k in ("word", "start", "end", "probability")} for w in s.get("words", [])]}
                for s in r["segments"]]
    return r.get("language"), prob, segments, mx.get_peak_memory()


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
            return info.language, (None if language else round(info.language_probability, 2)), segments, 0
        except RuntimeError as e:  # CUDA libraries missing (common on Windows): fall back to CPU
            if device == "cpu":
                raise
            print(f"GPU failed ({e}); using CPU", file=sys.stderr)


LONG = 10.0  # Whisper sometimes returns one 20-30 s "segment" (often in Bengali); cut it at its widest word gaps


def split_long(segments):
    """Segments over LONG seconds are cut at their widest word gap, repeatedly, so one line = one phrase.
    Even a pause-free wall of words is cut: the widest gap is the most phrase-like place available."""
    out = []
    for s in segments:
        stack = [s["words"]]
        while stack:
            ws = stack.pop()
            if len(ws) < 2 or ws[-1]["end"] - ws[0]["start"] <= LONG:
                out.append(ws)
                continue
            gaps = [(ws[i + 1]["start"] - ws[i]["end"], i) for i in range(len(ws) - 1)]
            g, i = max(gaps)
            stack += [ws[i + 1:], ws[:i + 1]]
    return [{"start": ws[0]["start"], "end": ws[-1]["end"], "words": ws} for ws in out]


if __name__ == "__main__":
    out, language, model = Path(sys.argv[1]), sys.argv[2] or None, sys.argv[3]
    t0 = time.time()
    lang, prob, segments, gpu = (transcribe_mlx if APPLE else transcribe_fw)(load(out), model, language)
    segments = split_long([s for s in segments if s["words"]])
    save(out, "asr", {"language": lang, "language_prob": prob, "segments": segments}, t0, gpu)
