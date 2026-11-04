# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["audio-separator[cpu]>=0.30", "audioread", "numpy"]
# ///
"""Remove music: keep only the voice (MelBand RoFormer, Kim vocals). Writes voice.wav (16 kHz mono)."""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from common import CACHE, save

MODEL = "vocals_mel_band_roformer.ckpt"

src, out = sys.argv[1], Path(sys.argv[2])
t0 = time.time()
from audio_separator.separator import Separator  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    sep = Separator(output_dir=tmp, output_single_stem="Vocals", model_file_dir=str(CACHE / "separator"),
                    log_level=40, mdxc_params={"segment_size": 256, "batch_size": 1, "overlap": 2,
                                               "override_model_segment_size": False, "pitch_shift": 0})
    sep.load_model(model_filename=MODEL)
    mix = Path(tmp) / "mix.wav"  # the separator can't read video containers
    subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "2", "-ar", "44100", str(mix)], check=True)
    stem = Path(tmp) / Path(sep.separate(str(mix))[0]).name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(stem), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                    str(out / "voice.wav")], check=True)
import torch  # noqa: E402

save(out, "separate", {"model": MODEL}, t0,
     torch.mps.driver_allocated_memory() if torch.backends.mps.is_available() else 0)
