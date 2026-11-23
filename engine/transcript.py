"""Transkrip: ambil dari YouTube, fallback Whisper lokal. Juga loader Whisper bersama."""
import os
import re
import threading

_WHISPER_LOCK = threading.Lock()
_WHISPER_MODELS = {}

PREFERRED_LANGS = ["id", "en", "ms", "jv", "su"]
_NOISE_RE = re.compile(r"\[(?:musik|music|tepuk tangan|applause|tertawa|laughter|__)\]", re.I)


def _clean_text(t):
    t = (t or "").replace("\n", " ")
    t = _NOISE_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _normalize(items):
    """items: list of (start, duration, text) -> list of {start, end, text} tanpa overlap."""
    items = sorted([(float(s), float(d), _clean_text(t)) for s, d, t in items], key=lambda x: x[0])
    segs = []
    for i, (s, d, t) in enumerate(items):
        if not t:
            continue
        end = s + max(d, 0.3)
        if i + 1 < len(items) and items[i + 1][0] > s:
            end = min(end, items[i + 1][0])
        segs.append({"start": round(s, 2), "end": round(max(end, s + 0.2), 2), "text": t})
    return segs


def fetch_youtube_transcript(video_id):
    """Kembalikan {segments, language, is_generated, source} atau None."""
    from youtube_transcript_api import YouTubeTranscriptApi

    def _items(fetched):
        out = []
        for sn in fetched:
            if isinstance(sn, dict):
                out.append((sn.get("start", 0), sn.get("duration", 0), sn.get("text", "")))
            else:
                out.append((getattr(sn, "start", 0), getattr(sn, "duration", 0), getattr(sn, "text", "")))
        return out

    # API baru (>=1.0)
    try:
        api = YouTubeTranscriptApi()
        tlist = api.list(video_id)
        chosen = None
        for finder in ("find_manually_created_transcript", "find_generated_transcript"):
            try:
                chosen = getattr(tlist, finder)(PREFERRED_LANGS)
                break
            except Exception:
                continue
        if chosen is None:
            chosen = next(iter(tlist))
        fetched = chosen.fetch()
        segs = _normalize(_items(fetched))
        if segs:
            return {"segments": segs, "language": chosen.language_code.split("-")[0],
                    "is_generated": bool(getattr(chosen, "is_generated", True)), "source": "youtube"}
    except Exception:
        pass

    # API lama (<1.0)
    try:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=PREFERRED_LANGS)
        segs = _normalize([(d["start"], d["duration"], d["text"]) for d in data])
        if segs:
            return {"segments": segs, "language": "id", "is_generated": True, "source": "youtube"}
    except Exception:
        pass
    return None


def _parse_json3(path):
    """Parse caption YouTube format json3 (punya timing per kata) -> segmen per frasa."""
    import json
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    words = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        t0 = ev.get("tStartMs", 0) / 1000.0
        ev_end = t0 + ev.get("dDurationMs", 0) / 1000.0
        for sg in segs:
            txt = (sg.get("utf8") or "").replace("\n", " ").strip()
            if not txt or _NOISE_RE.fullmatch(txt):
                continue
            words.append({"start": t0 + sg.get("tOffsetMs", 0) / 1000.0, "end": ev_end, "word": txt})
    words.sort(key=lambda w: w["start"])
    for i in range(len(words) - 1):
        nxt = words[i + 1]["start"]
        if nxt > words[i]["start"]:
            words[i]["end"] = min(words[i]["end"], nxt, words[i]["start"] + 1.5)
    if words:
        words[-1]["end"] = min(words[-1]["end"], words[-1]["start"] + 1.5)

    segs, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > 0.6 or len(cur) >= 14):
            segs.append(cur)
            cur = []
        cur.append(w)
        if w["word"].endswith((".", "?", "!")):
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    out = []
    for c in segs:
        text = _clean_text(" ".join(w["word"] for w in c))
        if text:
            out.append({"start": round(c[0]["start"], 2), "end": round(c[-1]["end"], 2), "text": text,
                        "words": [{"start": w["start"], "end": w["end"], "word": w["word"]} for w in c]})
    return out


def fetch_ytdlp_transcript(video_id, langs=("id", "en")):
    """Ambil caption lewat yt-dlp (pakai cookies/impersonate yang sama dengan download).
    Lebih tahan blokir dibanding youtube-transcript-api. Satu bahasa per request (hindari HTTP 429)."""
    import glob
    import shutil
    import tempfile
    from .ffmpeg import run
    from .youtube import watch_url, ytdlp_cmd

    tmp = tempfile.mkdtemp(prefix="youclip_subs_")
    try:
        for lang in langs:
            for attempt_langs in (f"{lang}-orig,{lang}", f"{lang}.*"):
                run(ytdlp_cmd("default") + ["--skip-download", "--write-subs", "--write-auto-subs",
                                            "--sub-langs", attempt_langs, "--sub-format", "json3",
                                            "-o", os.path.join(tmp, "s.%(ext)s"), watch_url(video_id)],
                    timeout=180)
                files = sorted(glob.glob(os.path.join(tmp, "*.json3")), key=lambda p: ("orig" not in p, p))
                for fp in files:
                    try:
                        segs = _parse_json3(fp)
                    except Exception:
                        continue
                    if segs:
                        return {"segments": segs, "language": lang, "is_generated": True, "source": "yt-dlp"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return None


def get_transcript(video_id):
    """Coba semua sumber transkrip online: youtube-transcript-api lalu yt-dlp."""
    # yt-dlp dulu: punya timing PER KATA (subtitle lebih akurat & tidak perlu Whisper)
    return fetch_ytdlp_transcript(video_id) or fetch_youtube_transcript(video_id)


# ----------------------------------------------------------------------------
# Whisper
# ----------------------------------------------------------------------------
def whisper_available():
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def get_whisper(size=None):
    """Model faster-whisper (di-cache, thread-safe). Ukuran via env WHISPER_MODEL (default: small)."""
    size = size or os.environ.get("WHISPER_MODEL", "small")
    with _WHISPER_LOCK:
        if size not in _WHISPER_MODELS:
            from faster_whisper import WhisperModel
            try:
                _WHISPER_MODELS[size] = WhisperModel(size, device="auto", compute_type="int8")
            except Exception:
                _WHISPER_MODELS[size] = WhisperModel(size, device="cpu", compute_type="int8")
        return _WHISPER_MODELS[size]


# Inferensi Whisper berat; serialisasi agar render paralel tidak kehabisan RAM.
WHISPER_RUN_LOCK = threading.Lock()


def whisper_transcribe(path, language=None, size=None, word_timestamps=False, initial_prompt=None,
                       on_progress=None, total_duration=None):
    """Transkripsi file audio/video. Kembalikan (segments, language).

    segments: [{start, end, text, words:[{start,end,word}]}]
    """
    model = get_whisper(size)
    with WHISPER_RUN_LOCK:
        seg_iter, info = model.transcribe(
            path,
            language=language,
            beam_size=5,
            word_timestamps=word_timestamps,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            condition_on_previous_text=False,
            initial_prompt=initial_prompt,
        )
        segs = []
        for s in seg_iter:
            text = _clean_text(s.text)
            if not text:
                continue
            item = {"start": round(s.start, 2), "end": round(s.end, 2), "text": text}
            if word_timestamps and s.words:
                item["words"] = [{"start": w.start, "end": w.end, "word": w.word} for w in s.words]
            segs.append(item)
            if on_progress and total_duration:
                on_progress(min(1.0, s.end / total_duration))
    return segs, info.language


# ----------------------------------------------------------------------------
# Format untuk prompt AI
# ----------------------------------------------------------------------------
def fmt_ts(sec):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:04.1f}"


def to_prompt_lines(segments, max_block_sec=12.0, max_chars=220):
    """Gabungkan segmen pendek menjadi baris '[mulai - selesai] teks' agar hemat token
    tapi tetap memberi AI batas waktu akhir yang jelas."""
    lines = []
    cur = None
    for s in segments:
        if cur is None:
            cur = dict(s)
            continue
        gap = s["start"] - cur["end"]
        too_long = (s["end"] - cur["start"]) > max_block_sec or len(cur["text"]) + len(s["text"]) > max_chars
        sentence_end = cur["text"].rstrip().endswith((".", "?", "!"))
        if too_long or gap > 0.8 or (sentence_end and s["end"] - cur["start"] > 5):
            lines.append(cur)
            cur = dict(s)
        else:
            cur["end"] = s["end"]
            cur["text"] = cur["text"] + " " + s["text"]
    if cur:
        lines.append(cur)
    return "\n".join(f"[{fmt_ts(l['start'])} - {fmt_ts(l['end'])}] {l['text']}" for l in lines)


def text_between(segments, start, end):
    return " ".join(s["text"] for s in segments if s["end"] > start and s["start"] < end)
