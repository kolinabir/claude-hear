# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["onnxruntime>=1.18", "sherpa-onnx>=1.10", "huggingface_hub", "numpy"]
# ///
"""Name non-speech sounds per second: CLAP zero-shot for the music share, CED (AudioSet, 527 labels) for events.

Reads the original file at 48 kHz for CLAP and 16 kHz for CED. CED (sherpa-onnx, 10 MB) catches short events CLAP
misses (a beep, a noise burst) and tells speech from singing better; CLAP keeps the music/singing share.

The audio encoder is the ONNX export of the same weights (Xenova/clap-htsat-unfused; embeddings match torch
to cosine 1.000). The label embeddings were computed once from the text model and ship in clap_labels.npz,
so this stage needs neither torch nor the 500 MB text model. Regenerate the file if LABELS or PROMPT change.
The log-mel input is computed here in numpy, matching transformers' ClapFeatureExtractor (which now requires torch).
"""
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import numpy as np

from common import CACHE, SR, fetch, save

SR48 = 48000
WIN, HOP = 2.0, 1.0  # 2 s windows every 1 s
PROMPT = "This is a sound of {}."
LABELS = [
    "speech", "silence", "music", "singing", "laughter", "applause", "cheering crowd", "crowd talking",
    "whoosh sound effect", "riser sound effect", "beep", "ding notification", "camera shutter", "typing on a keyboard",
    "footsteps", "door", "car traffic", "wind noise", "dog barking", "phone ringing", "explosion",
    "breathing", "coughing", "crying", "screaming",
]
MUSIC = {"music", "singing"}
CED = "sherpa-onnx-ced-mini-audio-tagging-2024-04-19"
CED_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/audio-tagging-models/{CED}.tar.bz2"
N_FFT, MEL_HOP, N_MEL, MAX_LEN = 1024, 480, 64, 10 * SR48  # ClapFeatureExtractor settings for clap-htsat-unfused


def mel_filters():
    """Slaney-scale, area-normalised triangular filters (513 bins x 64), as in transformers' mel_filter_bank."""
    def hz_to_mel(f):
        f = np.asarray(f, dtype=np.float64)
        m = 3.0 * f / 200.0
        log = f >= 1000.0
        m[log] = 15.0 + np.log(f[log] / 1000.0) * 27.0 / np.log(6.4)
        return m

    def mel_to_hz(m):
        f = 200.0 * m / 3.0
        log = m >= 15.0
        f[log] = 1000.0 * np.exp(np.log(6.4) / 27.0 * (m[log] - 15.0))
        return f

    edges = mel_to_hz(np.linspace(*hz_to_mel([50.0, 14000.0]), N_MEL + 2))
    fft_freqs = np.linspace(0, SR48 // 2, N_FFT // 2 + 1)
    slopes = edges[None, :] - fft_freqs[:, None]
    fb = np.maximum(0, np.minimum(-slopes[:, :-2] / np.diff(edges)[:-1], slopes[:, 2:] / np.diff(edges)[1:]))
    return fb * (2.0 / (edges[2:] - edges[:-2]))[None, :]


def log_mel(clip, fb):
    """(1000 x 64) dB log-mel of a clip repeated and zero-padded to 10 s, as ClapFeatureExtractor does for short audio."""
    w = np.tile(clip, MAX_LEN // len(clip))
    w = np.pad(w, (0, MAX_LEN - len(w))).astype(np.float64)
    w = np.pad(w, N_FFT // 2, mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(w, N_FFT)[::MEL_HOP]
    win = np.hanning(N_FFT + 1)[:-1]
    power = np.abs(np.fft.rfft(frames * win, axis=1)) ** 2
    mel = np.maximum(1e-10, power @ fb)
    return (10.0 * np.log10(mel)).astype(np.float32)


def ced_tagger():
    import sherpa_onnx
    d = CACHE / CED
    if not d.exists():
        with tarfile.open(fetch(CED_URL, f"{CED}.tar.bz2")) as t:
            t.extractall(CACHE, filter="data")
    return sherpa_onnx.AudioTagging(sherpa_onnx.AudioTaggingConfig(
        model=sherpa_onnx.AudioTaggingModelConfig(ced=str(d / "model.int8.onnx"), num_threads=2, provider="cpu"),
        labels=str(d / "class_labels_indices.csv"), top_k=3))

if __name__ == "__main__":
    src, out = sys.argv[1], Path(sys.argv[2])
    t0 = time.time()
    import onnxruntime as ort  # noqa: E402
    from huggingface_hub import hf_hub_download  # noqa: E402

    lab = np.load(Path(__file__).with_name("clap_labels.npz"))
    assert list(lab["labels"]) == LABELS, "LABELS changed: regenerate clap_labels.npz"
    t, scale = lab["text"], float(lab["scale"])

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(SR48), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.float32)
    starts = np.arange(0, max(len(y) / SR48 - WIN, 0) + 1e-6, HOP)
    clips = [y[int(s * SR48):int((s + WIN) * SR48)] for s in starts]

    fb = mel_filters()
    mel = np.stack([log_mel(c, fb) for c in clips])[:, None]   # (n, 1, 1000, 64)
    sess = ort.InferenceSession(hf_hub_download("Xenova/clap-htsat-unfused", "onnx/audio_model.onnx"),
                                providers=["CPUExecutionProvider"])
    a = np.concatenate([sess.run(None, {"input_features": mel[i:i + 1]})[0] for i in range(len(clips))])
    a /= np.linalg.norm(a, axis=-1, keepdims=True)
    logits = scale * a @ t.T
    probs = np.exp(logits - logits.max(-1, keepdims=True))
    probs /= probs.sum(-1, keepdims=True)

    tagger = ced_tagger()
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    y16 = np.frombuffer(raw, np.float32)

    windows = []
    for s, p in zip(starts, probs):
        st = tagger.create_stream()
        st.accept_waveform(SR, y16[int(s * SR):int((s + WIN) * SR)])
        top = np.argsort(p)[::-1][:3]
        windows.append({"t": float(s), "top": [[LABELS[k], round(float(p[k]), 2)] for k in top],
                        "events": [[e.name, round(float(e.prob), 2)] for e in tagger.compute(st, 3)],
                        "music": round(float(sum(p[LABELS.index(m)] for m in MUSIC)), 2)})
    save(out, "sounds", {"windows": windows, "win": WIN}, t0)
