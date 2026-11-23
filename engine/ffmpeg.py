"""Deteksi FFmpeg, encoder, dan helper eksekusi yang lintas platform.

- Memilih binary FFmpeg yang punya libass (filter `subtitles`/`ass`) agar subtitle bisa dibakar.
  ffmpeg Homebrew terbaru tidak menyertakan libass, jadi binary imageio-ffmpeg dipakai sebagai cadangan.
- Memilih encoder H.264 terbaik yang benar-benar berfungsi di mesin ini
  (VideoToolbox di macOS, NVENC/QSV/AMF di Windows/Linux, fallback libx264).
"""
import functools
import json
import os
import platform
import re
import shutil
import subprocess
import sys

from .paths import BASE_DIR

IS_WINDOWS = os.name == "nt"
_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0  # CREATE_NO_WINDOW: cegah jendela console berkedip di Windows


def run(cmd, timeout=None, cwd=BASE_DIR):
    """Jalankan perintah (list argumen, TANPA shell) dan kembalikan CompletedProcess dengan output teks."""
    return subprocess.run(
        [str(c) for c in cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        cwd=cwd,
        timeout=timeout,
        creationflags=_NO_WINDOW,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )


def _filters_of(exe):
    try:
        out = run([exe, "-hide_banner", "-filters"], timeout=20).stdout
    except Exception:
        return set()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "->" in parts[2]:
            names.add(parts[1])
    return names


def _candidate_ffmpegs():
    seen = []
    env = os.environ.get("FFMPEG_BINARY")
    if env:
        seen.append(env)
    which = shutil.which("ffmpeg")
    if which:
        seen.append(which)
    try:
        import imageio_ffmpeg
        seen.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    out = []
    for c in seen:
        if c and os.path.exists(c) and c not in out:
            out.append(c)
    return out


@functools.lru_cache(maxsize=1)
def ffmpeg_exe():
    """Binary FFmpeg terbaik: utamakan yang mendukung libass (subtitle)."""
    cands = _candidate_ffmpegs()
    if not cands:
        raise RuntimeError(
            "FFmpeg tidak ditemukan. Install FFmpeg (macOS: brew install ffmpeg, "
            "Windows: winget install Gyan.FFmpeg, Linux: apt install ffmpeg) "
            "atau `pip install imageio-ffmpeg`."
        )
    for c in cands:
        if "subtitles" in _filters_of(c):
            return c
    return cands[0]


@functools.lru_cache(maxsize=1)
def decode_ffmpeg_exe():
    """FFmpeg untuk memotong sumber: utamakan yang punya libdav1d (decode AV1 jauh lebih cepat)."""
    for c in _candidate_ffmpegs():
        try:
            out = run([c, "-hide_banner", "-decoders"], timeout=20).stdout
        except Exception:
            continue
        if "libdav1d" in out:
            return c
    return ffmpeg_exe()


@functools.lru_cache(maxsize=1)
def supports_subtitles():
    return "subtitles" in _filters_of(ffmpeg_exe())


@functools.lru_cache(maxsize=1)
def ffprobe_exe():
    env = os.environ.get("FFPROBE_BINARY")
    if env and os.path.exists(env):
        return env
    return shutil.which("ffprobe")


def _try_encoder(args):
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=0.3",
           *args, "-f", "null", "-"]
    try:
        return run(cmd, timeout=40).returncode == 0
    except Exception:
        return False


LIBX264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-profile:v", "high"]


@functools.lru_cache(maxsize=1)
def video_encoder_args():
    """Argumen encoder H.264 untuk render akhir.

    Override via env CLIPPER_ENCODER = auto | libx264 | videotoolbox | nvenc | qsv | amf.
    """
    pref = os.environ.get("CLIPPER_ENCODER", "auto").lower().strip()
    hw = {
        "videotoolbox": ["-c:v", "h264_videotoolbox", "-b:v", "8M", "-maxrate", "10M", "-bufsize", "16M",
                         "-pix_fmt", "yuv420p", "-profile:v", "high", "-allow_sw", "1"],
        "nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "21", "-b:v", "0",
                  "-pix_fmt", "yuv420p", "-profile:v", "high"],
        "qsv": ["-c:v", "h264_qsv", "-global_quality", "21", "-pix_fmt", "nv12", "-profile:v", "high"],
        "amf": ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22",
                "-pix_fmt", "yuv420p"],
    }
    if pref == "libx264":
        return LIBX264
    if pref in hw:
        return hw[pref] if _try_encoder(hw[pref]) else LIBX264

    system = platform.system().lower()
    order = ["videotoolbox"] if system == "darwin" else ["nvenc", "qsv", "amf"]
    for name in order:
        if _try_encoder(hw[name]):
            return hw[name]
    return LIBX264


def encoder_label():
    args = video_encoder_args()
    return args[args.index("-c:v") + 1]


def probe(path):
    """Info dasar video: duration (detik float), width, height, fps."""
    info = {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0}
    fp = ffprobe_exe()
    if fp:
        try:
            r = run([fp, "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height,r_frame_rate:format=duration",
                     "-of", "json", path], timeout=30)
            data = json.loads(r.stdout or "{}")
            st = (data.get("streams") or [{}])[0]
            info["width"] = int(st.get("width") or 0)
            info["height"] = int(st.get("height") or 0)
            num, _, den = str(st.get("r_frame_rate", "0/1")).partition("/")
            info["fps"] = float(num) / float(den or 1) if float(den or 1) else 0.0
            info["duration"] = float((data.get("format") or {}).get("duration") or 0)
            if info["duration"] > 0 and info["width"] > 0:
                return info
        except Exception:
            pass
    # Fallback tanpa ffprobe (mis. hanya imageio-ffmpeg): parse stderr `ffmpeg -i`
    try:
        err = run([ffmpeg_exe(), "-hide_banner", "-i", path], timeout=30).stderr
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        if m:
            info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", err)
        if m:
            info["width"], info["height"] = int(m.group(1)), int(m.group(2))
        m = re.search(r"(\d+(?:\.\d+)?) fps", err)
        if m:
            info["fps"] = float(m.group(1))
    except Exception:
        pass
    return info


def escape_filter_path(p):
    """Escape path untuk dipakai di dalam argumen filter FFmpeg (subtitles=...)."""
    p = p.replace("\\", "/")
    for ch in (":", "'", ",", "[", "]", ";"):
        p = p.replace(ch, "\\" + ch)
    return p


def python_exe():
    return sys.executable
