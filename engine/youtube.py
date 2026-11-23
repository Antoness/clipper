"""Interaksi YouTube via yt-dlp: metadata, pencarian, unduh sumber/audio.

Semua perintah dibangun sebagai list argumen (tanpa shell) sehingga:
- aman dari shell injection lewat URL,
- berjalan sama di Windows (cmd.exe), macOS dan Linux.
"""
import io
import json
import os
import platform
import re
import shutil
import ssl
import stat
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile

from .ffmpeg import ffmpeg_exe, probe, run, IS_WINDOWS
from .paths import DOWNLOADS_DIR, LEGACY_DOWNLOADS_DIR

_COOKIES_TEXT = None
_RUNTIME_READY = False

YOUTUBE_ID_RE = re.compile(r"(?:v=|/shorts/|/live/|/embed/|youtu\.be/|/v/)([0-9A-Za-z_-]{11})")


def set_cookies(text):
    """Set isi cookies (format Netscape) dari secrets. None = pakai cookies.txt lokal jika ada."""
    global _COOKIES_TEXT
    _COOKIES_TEXT = text.strip() if text else None


def extract_video_id(url):
    url = (url or "").strip()
    m = YOUTUBE_ID_RE.search(url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
        return url
    return None


def watch_url(video_id):
    return f"https://www.youtube.com/watch?v={video_id}"


# ----------------------------------------------------------------------------
# JS runtime (Deno/Node) untuk n-sig challenge solver yt-dlp
# ----------------------------------------------------------------------------
def _deno_paths():
    deno_dir = os.path.join(os.path.expanduser("~"), ".deno", "bin")
    return deno_dir, os.path.join(deno_dir, "deno.exe" if IS_WINDOWS else "deno")


def _deno_asset():
    system = platform.system().lower()
    arch = platform.machine().lower()
    is_arm = arch in ("arm64", "aarch64")
    if system == "darwin":
        return "deno-aarch64-apple-darwin.zip" if is_arm else "deno-x86_64-apple-darwin.zip"
    if system == "windows":
        return "deno-x86_64-pc-windows-msvc.zip"
    return "deno-aarch64-unknown-linux-gnu.zip" if is_arm else "deno-x86_64-unknown-linux-gnu.zip"


def _prepend_path(d):
    if d and d not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def ensure_runtime():
    """Pastikan yt-dlp-ejs dan JS runtime (deno, fallback node) tersedia. Aman dipanggil berkali-kali."""
    global _RUNTIME_READY
    if _RUNTIME_READY:
        return
    try:
        import yt_dlp_ejs  # noqa: F401
    except ImportError:
        try:
            run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "yt-dlp[default]", "yt-dlp-ejs"],
                timeout=180)
        except Exception:
            pass

    deno_dir, deno_bin = _deno_paths()
    if not shutil.which("deno"):
        if os.path.exists(deno_bin):
            _prepend_path(deno_dir)
        elif not os.environ.get("CLIPPER_SKIP_DENO"):
            try:
                url = f"https://github.com/denoland/deno/releases/latest/download/{_deno_asset()}"
                req = urllib.request.Request(url, headers={"User-Agent": "YouClip"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = resp.read()
                if len(data) > 1_000_000:
                    os.makedirs(deno_dir, exist_ok=True)
                    with zipfile.ZipFile(io.BytesIO(data)) as zf:
                        zf.extractall(deno_dir)
                    if not IS_WINDOWS and os.path.exists(deno_bin):
                        os.chmod(deno_bin, os.stat(deno_bin).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                    _prepend_path(deno_dir)
            except Exception:
                pass

    # Debian/Ubuntu menamai binary node sebagai "nodejs"
    if not shutil.which("node") and shutil.which("nodejs") and not IS_WINDOWS:
        try:
            local_bin = os.path.join(os.path.expanduser("~"), ".local", "bin")
            os.makedirs(local_bin, exist_ok=True)
            link = os.path.join(local_bin, "node")
            if not os.path.exists(link):
                os.symlink(shutil.which("nodejs"), link)
            _prepend_path(local_bin)
        except Exception:
            pass
    _RUNTIME_READY = True


def _ytdlp_exe():
    exe_dir = os.path.dirname(sys.executable)
    for name in ("yt-dlp.exe", "yt-dlp") if IS_WINDOWS else ("yt-dlp",):
        for d in (exe_dir, os.path.join(exe_dir, "Scripts")):
            p = os.path.join(d, name)
            if os.path.exists(p) and os.access(p, os.X_OK):
                return [p]
    w = shutil.which("yt-dlp")
    if w:
        return [w]
    return [sys.executable, "-m", "yt_dlp"]


def _cookie_args():
    if _COOKIES_TEXT:
        raw = _COOKIES_TEXT.replace("\r\n", "\n").replace("\r", "\n")
        if not raw.startswith("# Netscape HTTP Cookie File"):
            raw = "# Netscape HTTP Cookie File\n# This is a generated file! Do not edit.\n\n" + raw
        path = os.path.join(tempfile.gettempdir(), "youclip_yt_cookies.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw + "\n")
        return ["--cookies", path]
    for p in ("cookies.txt", os.path.join(os.path.dirname(DOWNLOADS_DIR), "cookies.txt")):
        if os.path.exists(p):
            return ["--cookies", os.path.abspath(p)]
    return []


def ytdlp_cmd(client="default", use_cookies=True):
    """Perintah dasar yt-dlp (list) dengan semua flag anti-bot."""
    ensure_runtime()
    cmd = list(_ytdlp_exe())
    if use_cookies:
        cmd += _cookie_args()
    try:
        import curl_cffi  # noqa: F401
        cmd += ["--impersonate", "chrome"]
    except ImportError:
        pass
    cmd += ["--remote-components", "ejs:github"]
    _, deno_bin = _deno_paths()
    if os.path.exists(deno_bin):
        cmd += ["--js-runtimes", f"deno:{deno_bin}"]
    cmd += ["--js-runtimes", "node",
            "--no-check-certificates", "--geo-bypass", "--no-playlist",
            "--ffmpeg-location", ffmpeg_exe(),
            "--extractor-args", f"youtube:player_client={client}"]
    return cmd


# ----------------------------------------------------------------------------
# Metadata
# ----------------------------------------------------------------------------
def fetch_metadata(url):
    """Kembalikan dict {id, url, title, duration} atau raise ValueError."""
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Link YouTube tidak valid. Contoh: https://www.youtube.com/watch?v=XXXXXXXXXXX")
    clean = watch_url(video_id)
    title, duration = "", 0

    local = source_path(video_id)
    if os.path.exists(local) and os.path.getsize(local) > 10000:
        duration = int(probe(local)["duration"])

    try:
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            pass
        oembed = f"https://www.youtube.com/oembed?url={urllib.parse.quote(clean)}&format=json"
        req = urllib.request.Request(oembed, headers={"User-Agent": "Mozilla/5.0"})
        try:
            resp = urllib.request.urlopen(req, timeout=8, context=ctx)
        except ssl.SSLError:
            resp = urllib.request.urlopen(req, timeout=8, context=ssl._create_unverified_context())
        with resp:
            title = json.loads(resp.read().decode()).get("title", "").strip()
    except Exception:
        pass

    if not duration:
        for cl in ("default", "mweb", "web"):
            try:
                r = run(ytdlp_cmd(cl) + ["--skip-download", "--print", "%(title)s\n%(duration)s", clean], timeout=60)
                lines = [l.strip() for l in r.stdout.strip().splitlines()]
                if r.returncode == 0 and lines:
                    if not title and lines[0] != "NA":
                        title = lines[0]
                    if len(lines) > 1 and lines[1].replace(".", "", 1).isdigit():
                        duration = int(float(lines[1]))
                        break
            except Exception:
                pass

    return {
        "id": video_id,
        "url": clean,
        "title": title or f"YouTube Video ({video_id})",
        "duration": duration or 600,
        "duration_known": bool(duration),
    }


def search(query, num=10):
    """Cari video; kembalikan list 'judul|url'."""
    r = run(ytdlp_cmd("default") + [f"ytsearch{int(num)}:{query}", "--flat-playlist",
                                     "--print", "%(title)s|https://youtube.com/watch?v=%(id)s"], timeout=120)
    if r.returncode != 0:
        return []
    return [l for l in r.stdout.strip().splitlines() if l.count("|") >= 1]


# ----------------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------------
def source_path(video_id):
    """Path cache video sumber (pakai cache lama di folder downloads/ jika ada)."""
    p = os.path.join(DOWNLOADS_DIR, f"source_{video_id}.mp4")
    legacy = os.path.join(LEGACY_DOWNLOADS_DIR, f"source_{video_id}.mp4")
    if not os.path.exists(p) and os.path.exists(legacy) and os.path.getsize(legacy) > 10000:
        return legacy
    return p


# Utamakan H.264 (avc1): decode cepat, terbaca OpenCV di semua OS (AV1 sering gagal dibaca cv2).
FORMAT_SELECTORS = [
    "bv*[vcodec^=avc1][height<=1080]+ba[ext=m4a]/bv*[vcodec^=avc1][height<=1080]+ba",
    "bv*[height<=1080]+ba/b[height<=1080]",
    "bv*+ba/b",
    "18/b",
]
CLIENTS = ["default", "mweb", "tv_embedded", "web_embedded", "android", "web_creator"]


def download_source(video_id, on_status=None):
    """Unduh video sumber sekali (cache). Kembalikan (path, error_text)."""
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    path = source_path(video_id)
    if os.path.dirname(path) != DOWNLOADS_DIR and not (os.path.exists(path) and os.path.getsize(path) > 10000):
        path = os.path.join(DOWNLOADS_DIR, f"source_{video_id}.mp4")
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return path, ""
    url = watch_url(video_id)
    last_err = ""
    for cl in CLIENTS:
        for fmt in FORMAT_SELECTORS:
            if on_status:
                on_status(f"Mengunduh video sumber (client: {cl})...")
            tmp = path + ".part.mp4"
            r = run(ytdlp_cmd(cl) + ["-f", fmt, "--merge-output-format", "mp4", "--force-overwrites",
                                     "-o", tmp, url])
            if os.path.exists(tmp) and os.path.getsize(tmp) > 10000:
                os.replace(tmp, path)
                return path, ""
            err = r.stderr or ""
            last_err = err
            low = err.lower()
            if "sign in" in low or "not a bot" in low or "private video" in low:
                break  # error autentikasi -> coba client lain, bukan format lain
        time.sleep(0.5)
    return None, last_err[-1500:]


def download_audio(video_id, out_dir):
    """Unduh audio saja (m4a/mp3). Kembalikan path atau None."""
    url = watch_url(video_id)
    for cl in ("default", "mweb", "android"):
        run(ytdlp_cmd(cl) + ["-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", "5",
                             "--force-overwrites", "-o", os.path.join(out_dir, "audio.%(ext)s"), url])
        files = [os.path.join(out_dir, f) for f in os.listdir(out_dir)]
        files = [f for f in files if os.path.getsize(f) > 1000 and not f.endswith(".part")]
        if files:
            return files[0]
    return None
