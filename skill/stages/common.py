"""Shared helpers for hear stages. Each stage is its own process so its memory is freed when it exits."""
import json
import sys
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np

SR = 16000
CACHE = Path.home() / ".cache" / "hear"


def load(out: Path, voice=True):
    """16 kHz mono float32. Uses the separated voice when it exists."""
    p = out / "voice.wav" if voice and (out / "voice.wav").exists() else out / "audio.wav"
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def read(out: Path, name):
    p = out / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def save(out: Path, name, data, t0, gpu_bytes=0):
    (out / f"{name}.json").write_text(json.dumps(data))
    (out / "stats").mkdir(exist_ok=True)
    (out / "stats" / f"{name}.json").write_text(json.dumps({
        "seconds": round(time.time() - t0, 1),
        "ram_gb": round(peak_ram() / 1e9, 2),
        "gpu_gb": round(gpu_bytes / 1e9, 2),
    }))


def peak_ram():
    """Peak resident memory in bytes, this process and its largest finished child."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                               "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                               "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        c = Counters(cb=ctypes.sizeof(Counters))
        k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.PeakWorkingSetSize  # shortcut: worker processes aren't counted on Windows
    import resource
    peak = max(resource.getrusage(r).ru_maxrss for r in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN))
    return peak if sys.platform == "darwin" else peak * 1024  # Linux reports KiB, macOS bytes


def fetch(url, name):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / name
    if not p.exists():
        tmp = p.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(p)
    return p


def words(asr):
    return [w for s in asr["segments"] for w in s["words"]]
