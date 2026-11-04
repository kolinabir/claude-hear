# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["mlx-whisper>=0.4", "numpy"]
# ///
"""Speech to text with word timings (mlx-whisper)."""
import sys
import time
from pathlib import Path

from common import load, save

out, language, model = Path(sys.argv[1]), sys.argv[2] or None, sys.argv[3]
t0 = time.time()
import mlx.core as mx  # noqa: E402
import mlx_whisper  # noqa: E402

mx.set_cache_limit(0)  # measured on a 40 s clip: peak 3.19 -> 2.43 GB for ~2-3 s more

r = mlx_whisper.transcribe(load(out), path_or_hf_repo=model, word_timestamps=True, language=language)
segments = [{
    "start": s["start"], "end": s["end"],
    "words": [{k: w[k] for k in ("word", "start", "end", "probability")} for w in s.get("words", [])],
} for s in r["segments"]]
save(out, "asr", {"language": r.get("language"), "segments": [s for s in segments if s["words"]]}, t0, mx.get_peak_memory())
