"""Subtitle & hook ber-gaya (ASS) — font, warna, ukuran, posisi, mode & animasi bisa diatur.

Mode subtitle:
- karaoke : 1 baris 2-4 kata, kata yang sedang diucapkan disorot (warna + pop)
- kotak   : seperti karaoke, kata aktif diberi latar kotak berwarna
- kata    : satu kata besar per waktu (gaya "word-by-word")
- baris   : satu baris statis tanpa sorotan (gaya minimalis)
"""
import os
import re
import uuid

from .paths import SUBS_DIR, asset

FONTS_DIR = asset("fonts")

# Nama family font (sesuai metadata TTF di folder fonts/)
FONTS = {
    "Titan One": "TitanOne-Regular.ttf",
    "Anton": "Anton-Regular.ttf",
    "Bebas Neue": "BebasNeue-Regular.ttf",
    "Poppins Black": "Poppins-Black.ttf",
    "Poppins ExtraBold": "Poppins-ExtraBold.ttf",
    "Archivo Black": "ArchivoBlack-Regular.ttf",
    "Bangers": "Bangers-Regular.ttf",
    "Permanent Marker": "PermanentMarker-Regular.ttf",
}

DEFAULT_STYLE = {
    # Subtitle
    "sub_enabled": True,
    "sub_mode": "karaoke",
    "sub_font": "Titan One",
    "sub_size": 76,
    "sub_color": "#FFFFFF",
    "sub_highlight": "#FFE500",
    "sub_outline_color": "#000000",
    "sub_outline": 7,
    "sub_shadow": 3,
    "sub_box": False,
    "sub_box_color": "#000000",
    "sub_box_opacity": 55,
    "sub_position": 24,          # % dari bawah layar
    "sub_words": 3,
    "sub_uppercase": True,
    "sub_animation": "pop",       # pop | none
    # Hook
    "hook_enabled": True,
    "hook_font": "Titan One",
    "hook_size": 80,
    "hook_color": "#FFFFFF",
    "hook_outline_color": "#000000",
    "hook_glow_color": "#FFE500",
    "hook_box": False,
    "hook_box_color": "#FFFFFF",
    "hook_text_on_box": "#000000",
    "hook_position": 12,          # % dari atas layar
    "hook_duration": 0,           # 0 = sepanjang klip, >0 = N detik pertama
    "hook_uppercase": True,
    "hook_animation": "pop",      # pop | none
    # Progress bar
    "progress_bar": False,
    "progress_color": "#FFE500",
}

PRESETS = {
    "🟡 Karaoke Kuning (Default)": {},
    "🟢 Hormozi Hijau": {
        "sub_font": "Anton", "sub_size": 92, "sub_highlight": "#22E55E", "sub_outline": 8, "sub_words": 2,
        "hook_font": "Anton", "hook_size": 88, "hook_glow_color": "#22E55E"},
    "🟥 Kotak Highlight": {
        "sub_mode": "kotak", "sub_font": "Poppins Black", "sub_size": 82, "sub_highlight": "#FF2D55",
        "sub_outline": 5, "hook_font": "Poppins Black", "hook_box": True, "hook_box_color": "#FFFFFF",
        "hook_text_on_box": "#000000", "hook_size": 70},
    "⚡ Kata per Kata (Bebas)": {
        "sub_mode": "kata", "sub_font": "Bebas Neue", "sub_size": 130, "sub_highlight": "#00E5FF",
        "sub_outline": 8, "sub_position": 30, "hook_font": "Bebas Neue", "hook_size": 104,
        "hook_glow_color": "#00E5FF"},
    "⚪ Minimal Putih": {
        "sub_mode": "baris", "sub_font": "Poppins ExtraBold", "sub_size": 60, "sub_uppercase": False,
        "sub_outline": 0, "sub_shadow": 0, "sub_box": True, "sub_box_opacity": 55, "sub_words": 5,
        "sub_animation": "none", "hook_font": "Poppins ExtraBold", "hook_size": 62, "hook_box": True,
        "hook_box_color": "#000000", "hook_text_on_box": "#FFFFFF", "hook_uppercase": False},
    "💥 Komik": {
        "sub_font": "Bangers", "sub_size": 96, "sub_highlight": "#FF9F1C", "sub_outline": 9,
        "hook_font": "Bangers", "hook_size": 96, "hook_glow_color": "#FF9F1C"},
}

SUB_MODES = {"karaoke": "Karaoke (kata aktif disorot)", "kotak": "Kotak highlight",
             "kata": "Satu kata per waktu", "baris": "Baris statis"}

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF\U00002B00-\U00002BFF️‍]+"
)


def make_style(preset=None, **overrides):
    st = dict(DEFAULT_STYLE)
    if preset and preset in PRESETS:
        st.update(PRESETS[preset])
    st.update({k: v for k, v in overrides.items() if k in DEFAULT_STYLE})
    return st


# ----------------------------------------------------------------------------
# Util ASS
# ----------------------------------------------------------------------------
def ass_color(hex_color, opacity=100):
    """'#RRGGBB' -> '&HAABBGGRR' (opacity 0..100)."""
    h = str(hex_color or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    alpha = int(round(255 * (1 - max(0, min(100, opacity)) / 100.0)))
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _inline_color(hex_color):
    h = str(hex_color or "#FFFFFF").lstrip("#")
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def ass_time(sec):
    cs = int(round(max(0.0, float(sec)) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_escape(text):
    text = _EMOJI_RE.sub("", str(text or ""))
    text = text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")
    return re.sub(r"\s{2,}", " ", text).strip()


def _display_word(w, upper=True):
    w = ass_escape(w).strip()
    if w.startswith("[") or w.endswith("]"):  # tag non-ucapan: [musik], [berdehem], ...
        return ""
    w = re.sub(r"^[\"'“”‘’(\[]+|[\"'“”‘’)\],;:]+$", "", w)
    w = re.sub(r"\.+$", "", w)
    return w.upper() if upper else w


# ----------------------------------------------------------------------------
# Sumber kata (disimpan apa adanya; huruf besar diterapkan saat menulis ASS)
# ----------------------------------------------------------------------------
def words_from_whisper(segments, duration):
    words = []
    for s in segments:
        for w in s.get("words") or []:
            st, en = float(w["start"]), float(w["end"])
            raw = w["word"].strip()
            if not _display_word(raw) or st >= duration:
                continue
            en = min(max(en, st + 0.08), st + 1.6, duration)
            words.append({"start": st, "end": en, "raw": raw})
    return words


def words_from_transcript(segments, clip_start, clip_end):
    """Fallback tanpa Whisper: pakai timing kata dari caption YouTube (json3) atau bagi rata per segmen."""
    out = []
    span_clip = clip_end - clip_start
    for s in segments:
        if s["end"] <= clip_start or s["start"] >= clip_end:
            continue
        if s.get("words"):
            for w in s["words"]:
                st, en = w["start"] - clip_start, w["end"] - clip_start
                if _display_word(w["word"]) and en > 0 and st < span_clip:
                    out.append({"start": max(0.0, st), "end": en, "raw": w["word"]})
            continue
        toks = s["text"].split()
        if not toks:
            continue
        span = s["end"] - s["start"]
        total = sum(len(t) + 1 for t in toks)
        t = s["start"]
        for tok in toks:
            d = span * (len(tok) + 1) / total
            st, en = t - clip_start, t + d - clip_start
            t += d
            if en > 0 and st < span_clip and _display_word(tok):
                out.append({"start": max(0.0, st), "end": en, "raw": tok})
    return out


def chunk_words(words, max_words=3):
    max_chars = max(8, max_words * 7)
    chunks, cur = [], []
    for w in words:
        disp = _display_word(w["raw"])
        if cur:
            gap = w["start"] - cur[-1]["end"]
            chars = sum(len(_display_word(x["raw"])) + 1 for x in cur) + len(disp)
            if len(cur) >= max_words or chars > max_chars or gap > 0.6:
                chunks.append(cur)
                cur = []
        cur.append(w)
        raw = w["raw"].rstrip()
        if raw.endswith((".", "?", "!")) or (raw.endswith(",") and len(cur) >= 2):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


# ----------------------------------------------------------------------------
# Penulisan ASS
# ----------------------------------------------------------------------------
def _styles(st, out_w, out_h):
    vertical = out_h > out_w
    base = out_w / 1080.0 if vertical else out_h / 1080.0 * 0.8
    side = int(out_w * 0.07)
    sub_mv = int(out_h * max(2, min(90, st["sub_position"])) / 100)
    hook_mv = int(out_h * max(1, min(90, st["hook_position"])) / 100)
    sub_size = int(st["sub_size"] * base)
    hook_size = int(st["hook_size"] * base)
    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
           "Alignment, MarginL, MarginR, MarginV, Encoding")
    lines = [fmt]
    # Subtitle
    if st["sub_box"]:
        lines.append(f"Style: Sub,{st['sub_font']},{sub_size},{ass_color(st['sub_color'])},&H00FFFFFF,"
                     f"{ass_color(st['sub_box_color'], st['sub_box_opacity'])},&H00000000,0,0,0,0,100,100,1,0,3,"
                     f"{max(6, int(14 * base))},0,2,{side},{side},{sub_mv},1")
    else:
        lines.append(f"Style: Sub,{st['sub_font']},{sub_size},{ass_color(st['sub_color'])},&H00FFFFFF,"
                     f"{ass_color(st['sub_outline_color'])},&H96000000,0,0,0,0,100,100,1,0,1,"
                     f"{int(st['sub_outline'] * base)},{int(st['sub_shadow'] * base)},2,{side},{side},{sub_mv},1")
    # Hook
    if st["hook_box"]:
        lines.append(f"Style: Hook,{st['hook_font']},{hook_size},{ass_color(st['hook_text_on_box'])},&H00FFFFFF,"
                     f"{ass_color(st['hook_box_color'])},&H00000000,0,0,0,0,100,100,1,0,3,"
                     f"{max(8, int(18 * base))},0,8,{side},{side},{hook_mv},1")
    else:
        lines.append(f"Style: HookGlow,{st['hook_font']},{hook_size},{ass_color(st['hook_color'])},&H00FFFFFF,"
                     f"{ass_color(st['hook_glow_color'])},&H00000000,0,0,0,0,100,100,1,0,1,"
                     f"{max(6, int(16 * base))},0,8,{side},{side},{hook_mv},1")
        lines.append(f"Style: Hook,{st['hook_font']},{hook_size},{ass_color(st['hook_color'])},&H00FFFFFF,"
                     f"{ass_color(st['hook_outline_color'])},&H00000000,0,0,0,0,100,100,1,0,1,"
                     f"{max(3, int(7 * base))},0,8,{side},{side},{hook_mv},1")
    lines.append(f"Style: Bar,Arial,10,{ass_color(st['progress_color'])},&H00FFFFFF,&H00000000,&H00000000,"
                 f"0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1")
    lines.append("Style: BarBg,Arial,10,&H99FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
                 "0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1")
    return "\n".join(lines)


def _word_tag(st, active):
    if not active:
        return ""
    hl = _inline_color(st["sub_highlight"])
    if st["sub_mode"] == "kotak":
        # kata aktif: teks putih di atas "kotak" warna (outline tebal warna highlight)
        tag = f"\\3c{hl}\\bord{max(10, int(st['sub_outline']) + 9)}\\shad0"
    else:
        tag = f"\\c{hl}"
    if st["sub_animation"] == "pop":
        tag += "\\fscx112\\fscy112"
    return "{" + tag + "}"


def _sub_events(words, duration, st):
    upper = st["sub_uppercase"]
    ev = []
    if st["sub_mode"] == "kata":
        for i, w in enumerate(words):
            nxt = words[i + 1]["start"] if i + 1 < len(words) else duration
            st_t, en_t = w["start"], min(max(w["end"] + 0.15, w["end"]), nxt, duration)
            if en_t - st_t < 0.04:
                continue
            anim = "{\\fscx80\\fscy80\\t(0,90,\\fscx108\\fscy108)\\t(90,160,\\fscx100\\fscy100)}" \
                if st["sub_animation"] == "pop" else ""
            ev.append((st_t, en_t, f"{anim}{{\\c{_inline_color(st['sub_highlight'])}}}"
                                   f"{_display_word(w['raw'], upper)}"))
        return ev

    chunks = chunk_words(words, int(st["sub_words"]))
    for ci, chunk in enumerate(chunks):
        next_start = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else duration
        chunk_end = min(chunk[-1]["end"] + 0.3, next_start, duration)
        texts = [_display_word(x["raw"], upper) for x in chunk]
        if st["sub_mode"] == "baris":
            if chunk_end - chunk[0]["start"] >= 0.04:
                ev.append((chunk[0]["start"], chunk_end, " ".join(texts)))
            continue
        for wi, w in enumerate(chunk):
            st_t = chunk[0]["start"] if wi == 0 else w["start"]
            en_t = chunk[wi + 1]["start"] if wi + 1 < len(chunk) else chunk_end
            if en_t - st_t < 0.04:
                continue
            parts = [(_word_tag(st, True) + t + "{\\r}") if j == wi else t for j, t in enumerate(texts)]
            ev.append((st_t, en_t, " ".join(parts)))
    return ev


def build_ass(words, duration, out_w, out_h, hook="", style=None, path=None):
    """Tulis file ASS dan kembalikan path-nya."""
    st = make_style(**(style or {}))
    os.makedirs(SUBS_DIR, exist_ok=True)
    path = path or os.path.join(SUBS_DIR, f"sub_{uuid.uuid4().hex[:12]}.ass")
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {out_w}", f"PlayResY: {out_h}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]", _styles(st, out_w, out_h), "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    hook_txt = ass_escape(hook)
    if st["hook_uppercase"]:
        hook_txt = hook_txt.upper()
    if st["hook_enabled"] and hook_txt:
        h_end = min(duration, st["hook_duration"]) if st["hook_duration"] else duration
        anim = "{\\fscx70\\fscy70\\t(0,180,\\fscx106\\fscy106)\\t(180,260,\\fscx100\\fscy100)}" \
            if st["hook_animation"] == "pop" else ""
        fade = "{\\fad(0,250)}" if st["hook_duration"] else ""
        if st["hook_box"]:
            lines.append(f"Dialogue: 0,0:00:00.00,{ass_time(h_end)},Hook,,0,0,0,,{anim}{fade}{hook_txt}")
        else:
            lines.append(f"Dialogue: 0,0:00:00.00,{ass_time(h_end)},HookGlow,,0,0,0,,{anim}{fade}{hook_txt}")
            lines.append(f"Dialogue: 1,0:00:00.00,{ass_time(h_end)},Hook,,0,0,0,,{anim}{fade}{hook_txt}")

    if st["sub_enabled"]:
        for a, b, text in _sub_events(words, duration, st):
            lines.append(f"Dialogue: 2,{ass_time(a)},{ass_time(b)},Sub,,0,0,0,,{text}")

    if st["progress_bar"]:
        bh = max(6, int(out_h * 0.006))
        y0 = out_h - bh
        d_ms = int(duration * 1000)
        shape = f"m 0 0 l {out_w} 0 l {out_w} {bh} l 0 {bh}"
        lines.append(f"Dialogue: 3,0:00:00.00,{ass_time(duration)},BarBg,,0,0,0,,{{\\pos(0,{y0})\\p1}}{shape}{{\\p0}}")
        lines.append(f"Dialogue: 4,0:00:00.00,{ass_time(duration)},Bar,,0,0,0,,"
                     f"{{\\pos(0,{y0})\\clip(0,{y0},0,{out_h})\\t(0,{d_ms},\\clip(0,{y0},{out_w},{out_h}))\\p1}}"
                     f"{shape}{{\\p0}}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _fill_gaps(primary, backup, tol=1.0):
    """Tambahkan kata dari `backup` di bagian yang tidak tercakup `primary` (mis. bagian yang dilewati Whisper)."""
    if not backup:
        return primary
    if not primary:
        return backup
    starts = sorted(w["start"] for w in primary)
    import bisect

    def covered(t):
        i = bisect.bisect_left(starts, t)
        near = [starts[j] for j in (i - 1, i) if 0 <= j < len(starts)]
        return any(abs(x - t) <= tol for x in near)
    extra = [w for w in backup if not covered(w["start"])]
    return sorted(primary + extra, key=lambda w: w["start"])


def _coverage_ok(words, duration):
    """Caption dianggap lengkap jika rapat (>=0.8 kata/dtk) dan tidak ada celah panjang tanpa kata."""
    if len(words) < max(3, duration * 0.8):
        return False
    times = [0.0] + [w["start"] for w in words] + [duration]
    return max(b - a for a, b in zip(times, times[1:])) < 8.0


def transcribe_words(media_path, duration, language=None, transcript_segments=None, clip_start=0.0,
                     initial_prompt=None, use_whisper=True):
    """Ambil kata bertimestamp untuk satu klip. Kembalikan (words, sumber, pesan_error).

    Prioritas: caption YouTube dengan timing per kata (cepat & akurat) -> Whisper (+ isi celah dari caption).
    Catatan: `initial_prompt` sengaja TIDAK dipakai — Whisper cenderung melompati teks yang ada di prompt.
    Set env SUBTITLE_SOURCE=whisper untuk selalu memakai Whisper.
    """
    from .transcript import whisper_available, whisper_transcribe
    err = ""
    prefer_whisper = os.environ.get("SUBTITLE_SOURCE", "auto").lower() == "whisper"
    yt_words = words_from_transcript(transcript_segments, clip_start, clip_start + duration) \
        if transcript_segments else []
    has_word_timing = bool(transcript_segments) and any(s.get("words") for s in transcript_segments)
    if has_word_timing and not prefer_whisper and _coverage_ok(yt_words, duration):
        return yt_words, "youtube", ""

    words = []
    if use_whisper and whisper_available():
        try:
            segs, _ = whisper_transcribe(media_path, language=language, word_timestamps=True)
            words = words_from_whisper(segs, duration)
        except Exception as e:  # noqa: BLE001
            err = f"Whisper gagal: {e}"
    if words:
        merged = _fill_gaps(words, yt_words)
        return merged, ("whisper" if len(merged) == len(words) else "whisper+youtube"), err
    if yt_words:
        return yt_words, "youtube", err
    return [], "none", err


# ----------------------------------------------------------------------------
# Preview gaya
# ----------------------------------------------------------------------------
SAMPLE_WORDS = ["Ternyata", "rahasianya", "ada", "di", "sini", "semua", "orang", "kaget!"]


def render_preview(style, out_png, background=None, hook="RAHASIA YANG JARANG DIKETAHUI"):
    """Render 1 gambar preview 1080x1920 untuk gaya tertentu. background: path gambar/video (opsional)."""
    from .ffmpeg import ffmpeg_exe, run, escape_filter_path, supports_subtitles
    from .paths import rel
    st = make_style(**style)
    t0 = 0.0
    words = []
    for w in SAMPLE_WORDS:
        words.append({"start": t0, "end": t0 + 0.35, "raw": w})
        t0 += 0.4
    st_preview = dict(st, hook_animation="none", sub_animation=st["sub_animation"])
    ass = build_ass(words, 4.0, 1080, 1920, hook=hook, style=st_preview)
    vf_sub = f"subtitles=filename={escape_filter_path(rel(ass))}:fontsdir={escape_filter_path(rel(FONTS_DIR))}"
    if background and os.path.exists(background):
        inp = ["-ss", "1", "-i", background]
        vf = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,"
              "loop=loop=-1:size=1:start=0,trim=duration=2,setpts=N/30/TB")
    else:
        inp = ["-f", "lavfi", "-i", "gradients=s=1080x1920:c0=0x3a4a5c:c1=0x1b2430:duration=2:speed=0.01"]
        vf = "setsar=1"
    if supports_subtitles():
        vf += "," + vf_sub
    r = run([ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", *inp, "-vf", vf,
             "-ss", "0.45", "-frames:v", "1", out_png])
    try:
        os.remove(ass)
    except OSError:
        pass
    if r.returncode != 0 or not os.path.exists(out_png):
        raise RuntimeError(r.stderr[-400:])
    return out_png
