"""Lokasi file & helper nama file yang aman di semua OS."""
import os
import re
import sys
import unicodedata

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_work_dir():
    """Folder kerja untuk video sumber, potongan, subtitle & hasil.

    Di macOS dipakai nama berakhiran `.nosync` supaya iCloud Drive (Desktop & Documents sync)
    TIDAK ikut menyinkronkan/menimpa file video yang sedang ditulis FFmpeg — iCloud terbukti
    bisa memotong file menjadi beberapa byte atau menghapusnya di tengah proses.
    Bisa dioverride dengan env CLIPPER_WORK_DIR.
    """
    env = os.environ.get("CLIPPER_WORK_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    if sys.platform == "darwin":
        return os.path.join(BASE_DIR, "downloads.nosync")
    return os.path.join(BASE_DIR, "downloads")


DOWNLOADS_DIR = _default_work_dir()
LEGACY_DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
SUBS_DIR = os.path.join(DOWNLOADS_DIR, "subs")

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def asset(name):
    """Path absolut ke file aset di root project (model, font)."""
    return os.path.join(BASE_DIR, name)


def ensure_dirs():
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(SUBS_DIR, exist_ok=True)


def rel(path):
    """Path relatif terhadap BASE_DIR dengan '/' (aman untuk filter FFmpeg di Windows).
    Jika beda drive (Windows) dikembalikan path absolut dengan '/'."""
    try:
        return os.path.relpath(path, BASE_DIR).replace(os.sep, "/")
    except ValueError:
        return os.path.abspath(path).replace(os.sep, "/")


def safe_filename(name, default="clip", max_len=80):
    """Ubah teks bebas (judul/hook AI) menjadi nama file yang valid di Windows/macOS/Linux."""
    name = str(name or "").strip()
    if name.lower().endswith(".mp4"):
        name = name[:-4]
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("._-")
    name = name[:max_len].rstrip("._-")
    if not name or name.upper() in _WINDOWS_RESERVED:
        name = default
    return name
