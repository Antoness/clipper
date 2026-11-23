"""Pencarian momen viral dengan Gemini + perapian batas klip berbasis transkrip.

Perbaikan utama dibanding versi lama:
- Transkrip TIDAK lagi dipotong 60.000 karakter (dulu bagian akhir video 1-2 jam tak pernah dilihat AI).
- Setiap baris transkrip punya waktu mulai & selesai, sehingga AI bisa memilih titik akhir yang tepat.
- Batas klip di-"snap" ke awal/akhir kalimat terdekat (tidak memotong di tengah kata/kalimat).
- Klip yang tumpang tindih dibuang, durasi dijaga dengan toleransi agar tidak dipotong paksa.
"""
import json
import re
import time

DURATION_PRESETS = [
    ("15-30", 15, 30),
    ("30-60", 30, 60),
    ("1-3", 60, 180),
    ("3-5", 180, 300),
    ("Bawah 15", 8, 15),
]

# Urutan model: kuota gratis & beban server dihitung PER MODEL, jadi jika satu model penuh/limit,
# model lain biasanya masih bisa dipakai.
DEFAULT_MODELS = ["gemini-3.8-flash", "gemini-flash-latest", "gemini-2.5-flash", "gemini-3.5-flash",
                  "gemini-2.5-flash-lite", "gemini-flash-lite-latest"]


def duration_bounds(label):
    for key, lo, hi in DURATION_PRESETS:
        if key in label:
            return lo, hi
    return 15, 60


def parse_time(val, default=0.0):
    """'HH:MM:SS(.ms)', 'MM:SS', angka, '75s' -> detik (float)."""
    if val is None:
        return float(default)
    if isinstance(val, (int, float)):
        return max(0.0, float(val))
    s = str(val).strip().replace(",", ".")
    if not s:
        return float(default)
    if ":" in s:
        try:
            parts = [float(p) for p in s.split(":")]
            total = 0.0
            for p in parts:
                total = total * 60 + p
            return max(0.0, total)
        except ValueError:
            pass
    m = re.search(r"\d+(?:\.\d+)?", s)
    return max(0.0, float(m.group())) if m else float(default)


def fmt_time(sec, decimals=1):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec - h * 3600 - m * 60
    if decimals and abs(s - round(s)) > 0.04:
        return f"{h:02d}:{m:02d}:{s:0{3 + decimals}.{decimals}f}"
    return f"{h:02d}:{m:02d}:{int(round(s)):02d}"


# ----------------------------------------------------------------------------
# Prompt
# ----------------------------------------------------------------------------
def build_prompt(fokus, min_sec, max_sec, content_kind, transcript_text="", video_title="", video_duration=0):
    if "Makan" in fokus:
        task = (
            "KHUSUS MUKBANG/EATING: fokus pada aktivitas makan nyata (menyuap, menggigit, mengunyah, menelan). "
            "Klip dimulai tepat sebelum makanan masuk mulut dan berakhir setelah selesai mengunyah. "
            "Kata seperti 'mari makan', 'bismillah', 'enak banget', atau jeda panjang saat membahas makanan "
            "biasanya menandai adegan makan. Keluarkan 3-8 klip."
        )
    elif "Cut Video" in fokus:
        task = (
            "KHUSUS CUT VIDEO: bagi SELURUH pembahasan yang berbobot menjadi klip-klip utuh berurutan. "
            "Keluarkan sebanyak mungkin klip (10-30) yang mencakup awal sampai akhir video. "
            "Setiap klip harus satu topik yang utuh."
        )
    else:
        task = (
            "Temukan 3 sampai 6 KLIP TERBAIK yang berpotensi viral, tersebar di berbagai bagian video "
            "(awal, tengah, akhir), bukan semuanya dari awal."
        )

    source_note = {
        "text": "Di bawah ini transkrip lengkap dengan format [MULAI - SELESAI] teks. Gunakan stempel waktu itu PERSIS.",
        "audio": "Konten diberikan sebagai file audio. Dengarkan dengan teliti dan berikan stempel waktu seakurat mungkin.",
        "title": "TRANSKRIP TIDAK TERSEDIA. Hanya judul & durasi yang diketahui; sebar klip merata dan beri skor rendah.",
    }[content_kind]

    prompt = f"""
[PERAN]
Anda adalah editor short-form video profesional (TikTok/Reels/Shorts), copywriter viral, dan auditor kebijakan Meta/TikTok.

[VIDEO]
Judul: {video_title}
Durasi total: {fmt_time(video_duration, 0)}
Fokus konten: {fokus}
{source_note}

[TUGAS]
{task}

[ATURAN MEMILIH POTONGAN — PALING PENTING]
Setiap klip harus berupa CERITA UTUH dengan alur: PEMBUKA (konteks/pertanyaan) -> PEMBANGUN -> KLIMAKS
(punchline, jawaban mengejutkan, momen lucu/dramatis) -> REAKSI/PENUTUP singkat (tawa, tanggapan, kesimpulan).
1. Target durasi {min_sec}-{max_sec} detik. KLIMAKS LEBIH PENTING DARI DURASI: jika klimaks + reaksinya butuh
   sedikit lebih panjang (sampai +30%), ambil lebih panjang. JANGAN PERNAH memotong sebelum klimaks selesai.
2. "start" = awal kalimat/pertanyaan yang memulai cerita, sehingga penonton langsung paham konteks.
   Jangan mulai di tengah kalimat atau dengan kata sambung ("dan", "terus", "jadi", "nah") yang kehilangan konteks.
3. "climax" = waktu punchline/momen puncak diucapkan.
4. "end" = SETELAH klimaks DAN reaksinya selesai (tawa/tanggapan/kalimat penutup), minimal 2-3 detik setelah
   klimaks. Gunakan waktu SELESAI dari baris transkrip. Jangan berhenti di tengah kalimat.
5. Klip bisa dipahami tanpa menonton video aslinya. Klip tidak boleh saling tumpang tindih.
6. Hindari intro/outro, iklan/sponsor, salam pembuka, dan basa-basi.
7. Format waktu "HH:MM:SS.s" (contoh "00:12:05.4").

[ATURAN TEKS]
- hook: 3-6 kata, HURUF KAPITAL, tanpa emoji (emoji tidak bisa dirender di video). Ini teks overlay di atas video.
- deskripsi: 1-2 kalimat yang menceritakan isi klip.
- caption: maksimal 100 karakter untuk postingan, boleh emoji, maksimal 6 hashtag.
- Samarkan kata sensitif pada hook/caption (Mati->M4t1, Bunuh->Bvnvh, Darah->D4r4h, Pembunuhan->Tr4g3d1,
  Judi->Jvd1, Pinjol->P1nj0l, Korupsi->K0rvps1, Dukun->Dvkvn, Penipuan->P3n1pv4n, Pesugihan->P3su91h4n,
  COVID/Vaksin->Pandemi masa lalu).
- Semua teks dalam Bahasa Indonesia.

[OUTPUT]
Kembalikan HANYA JSON array valid, urut berdasarkan virality_score tertinggi:
[{{"start": "00:01:20.0", "climax": "00:01:41.2", "end": "00:01:47.5",
  "first_words": "5-8 kata pertama yang diucapkan di klip",
  "climax_words": "kata-kata kunci punchline/klimaks",
  "last_words": "5-8 kata terakhir yang diucapkan di klip", "hook": "BONGKAR TAKTIK KUNC3N",
  "deskripsi": "...", "caption": "... #podcast", "virality_score": 9.1,
  "viral_reason": "alasan singkat", "name": "nama_file_singkat"}}]
"""
    if content_kind == "text" and transcript_text:
        prompt += "\n[TRANSKRIP]\n" + transcript_text + "\n"
    return prompt


# ----------------------------------------------------------------------------
# Gemini
# ----------------------------------------------------------------------------
class AllKeysFailed(Exception):
    pass


def _generate_new_sdk(key, model_name, prompt, audio_path, status, key_no):
    """SDK resmi terbaru: google-genai."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key, http_options=types.HttpOptions(api_version="v1beta"))
    contents = [prompt]
    if audio_path:
        status(f"Mengunggah audio ke Gemini (key #{key_no})...")
        f = client.files.upload(file=audio_path)
        while getattr(f.state, "name", str(f.state)) == "PROCESSING":
            time.sleep(2)
            f = client.files.get(name=f.name)
        contents.append(f)
    resp = client.models.generate_content(
        model=model_name, contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4))
    return resp.text


def _generate_old_sdk(key, model_name, prompt, audio_path, status, key_no):
    """SDK lama: google-generativeai (sudah deprecated, dipakai jika google-genai tidak ada)."""
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", message=".*google.generativeai.*")
    import google.generativeai as genai
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        model_name, generation_config={"response_mime_type": "application/json", "temperature": 0.4})
    if audio_path:
        status(f"Mengunggah audio ke Gemini (key #{key_no})...")
        f = genai.upload_file(path=audio_path)
        while f.state.name == "PROCESSING":
            time.sleep(2)
            f = genai.get_file(f.name)
        return model.generate_content([prompt, f], request_options={"timeout": 600}).text
    return model.generate_content(prompt, request_options={"timeout": 600}).text


def _sdk():
    try:
        from google import genai  # noqa: F401
        from google.genai import types  # noqa: F401
        return _generate_new_sdk
    except Exception:
        return _generate_old_sdk


def _err_kind(e):
    msg = str(e).lower()
    if "404" in msg or "not found" in msg or "not supported" in msg or "no longer available" in msg:
        return "no_model"
    if "429" in msg or "quota" in msg or "exhausted" in msg or "rate" in msg:
        return "limit"
    if "503" in msg or "unavailable" in msg or "overloaded" in msg or "high demand" in msg or "500" in msg:
        return "busy"
    if "403" in msg or "permission" in msg or "api key not valid" in msg or "401" in msg:
        return "denied"
    return "other"


def call_gemini(api_keys, prompt, audio_path=None, models=None, on_status=None, rounds=2):
    """Panggil Gemini: coba setiap MODEL dengan semua key. Model yang penuh/limit dilewati ke model lain.
    Jika semua sibuk, tunggu lalu ulangi (maks `rounds` putaran)."""
    generate = _sdk()
    models = list(dict.fromkeys(models or DEFAULT_MODELS))
    status = on_status or (lambda *_: None)
    last_err = None
    dead_models, dead_keys = set(), set()
    for rnd in range(rounds):
        any_busy = False
        for model_name in models:
            if model_name in dead_models:
                continue
            busy_count = 0
            for k_i, key in enumerate(api_keys, 1):
                if k_i in dead_keys:
                    continue
                try:
                    text = generate(key, model_name, prompt, audio_path, status, k_i)
                    if text and text.strip():
                        if model_name != models[0] or rnd:
                            status(f"Berhasil memakai model {model_name} (key #{k_i}).")
                        return text
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    kind = _err_kind(e)
                    if kind == "no_model":
                        dead_models.add(model_name)
                        break
                    if kind == "denied":
                        dead_keys.add(k_i)
                    elif kind in ("limit", "busy"):
                        busy_count += 1
                        any_busy = True
                    time.sleep(0.5)
            if model_name not in dead_models:
                status(f"Model {model_name} sedang penuh/kuota habis di semua key, mencoba model lain...")
        if any_busy and rnd + 1 < rounds:
            status("Semua model sedang sibuk. Menunggu 30 detik lalu mencoba lagi...")
            time.sleep(30)
    raise AllKeysFailed(
        "Server Gemini sedang penuh atau kuota gratis semua key sudah habis untuk hari ini. "
        "Coba lagi beberapa menit lagi, atau tambahkan API key baru. "
        f"(Error terakhir: {str(last_err)[:160]})")


def parse_clips(text):
    clean = text.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", clean, re.DOTALL)
        if not m:
            raise
        data = json.loads(m.group())
    if isinstance(data, dict):
        for k in ("clips", "klip", "results", "data"):
            if isinstance(data.get(k), list):
                data = data[k]
                break
        else:
            data = [data]
    return [c for c in data if isinstance(c, dict)]


# ----------------------------------------------------------------------------
# Perapian batas klip
# ----------------------------------------------------------------------------
def _norm_words(t):
    return re.findall(r"[a-z0-9]+", (t or "").lower())


def _is_sentence_end(text):
    return text.rstrip().endswith((".", "?", "!", "…"))


def word_stream(segments):
    """Daftar kata bertimestamp dari segmen (pakai timing kata asli jika ada, jika tidak dibagi rata)."""
    out = []
    for s in segments:
        if s.get("words"):
            for w in s["words"]:
                for tok in _norm_words(w["word"]):
                    out.append((tok, float(w["start"]), float(w["end"])))
            continue
        toks = _norm_words(s["text"])
        if not toks:
            continue
        d = (s["end"] - s["start"]) / len(toks)
        for i, tok in enumerate(toks):
            out.append((tok, s["start"] + i * d, s["start"] + (i + 1) * d))
    return out


def find_phrase_time(words, phrase, around, window=30.0, want="start"):
    """Cari frasa (fuzzy, tingkat kata) dekat waktu `around`. Kembalikan waktu mulai/akhir frasa atau None."""
    from difflib import SequenceMatcher
    toks = _norm_words(phrase)[:8]
    if len(toks) < 3 or not words:
        return None
    n = len(toks)
    best = (0.0, None)
    for i in range(len(words) - n + 1):
        t0 = words[i][1]
        if abs(t0 - around) > window:
            continue
        cand = [w[0] for w in words[i:i + n]]
        r = SequenceMatcher(None, toks, cand).ratio()
        if r > best[0] or (r == best[0] and best[1] is not None and abs(t0 - around) < abs(best[1][1] - around)):
            best = (r, (i, t0))
    if best[1] is None or best[0] < 0.6:
        return None
    i = best[1][0]
    return words[i][1] if want == "start" else words[min(len(words) - 1, i + n - 1)][2]


def _sentence_start_near(segments, t, back=5.0, fwd=2.5):
    best = None
    for i, s in enumerate(segments):
        d = s["start"] - t
        if d < -back or d > fwd:
            continue
        prev = segments[i - 1] if i > 0 else None
        score = abs(d)
        if prev is None or s["start"] - prev["end"] >= 0.5:
            score -= 1.5
        if prev is not None and _is_sentence_end(prev["text"]):
            score -= 1.5
        if best is None or score < best[0]:
            best = (score, s["start"])
    return best[1] if best else None


def _sentence_end_after(segments, t_min, t_target, t_max):
    """Akhir kalimat terbaik dalam [t_min, t_max], dekat t_target, utamakan akhir kalimat + jeda."""
    best = None
    for i, s in enumerate(segments):
        if s["end"] < t_min or s["end"] > t_max:
            continue
        nxt = segments[i + 1] if i + 1 < len(segments) else None
        score = abs(s["end"] - t_target) * 0.5
        if _is_sentence_end(s["text"]):
            score -= 2.5
        if nxt is None or nxt["start"] - s["end"] >= 0.5:
            score -= 2.0
        if best is None or score < best[0]:
            best = (score, s["end"])
    return best[1] if best else None


def snap_clip(start, end, segments, min_d, max_d, video_dur, first_words=None, last_words=None,
              climax=None, climax_words=None, words=None):
    """Rapikan (start, end): mulai di awal kalimat, berakhir setelah klimaks + reaksi di akhir kalimat."""
    hard_max = max_d * 1.35
    if not segments:
        e = min(max(end, start + min_d), start + hard_max)
        return max(0.0, start), min(video_dur, e) if video_dur else e
    words = words if words is not None else word_stream(segments)

    # --- START ---
    t = find_phrase_time(words, first_words, start, want="start") if first_words else None
    if t is None:
        t = _sentence_start_near(segments, start)
    new_start = t if t is not None else start

    # --- KLIMAKS ---
    cl = None
    if climax_words:
        cl = find_phrase_time(words, climax_words, climax if climax else end, want="end")
    if cl is None and climax is not None and new_start < climax < new_start + hard_max:
        cl = climax

    # --- END ---
    e = find_phrase_time(words, last_words, end, want="end") if last_words else None
    target = e if e is not None else end
    lo = new_start + min_d * 0.8
    if cl is not None:
        lo = max(lo, cl + 2.0)            # klimaks + reaksi wajib masuk
    hi = new_start + hard_max
    if lo > hi:
        hi = lo + 4.0
    target = min(max(target, lo), hi)
    snapped = _sentence_end_after(segments, lo, target, hi)
    new_end = snapped if snapped is not None else target

    new_start = max(0.0, new_start - 0.2)
    new_end = new_end + 0.5                # ekor singkat untuk reaksi/tawa
    if video_dur:
        new_end = min(video_dur, new_end)
    if new_end - new_start < 1:
        new_end = new_start + min_d
    return round(new_start, 2), round(new_end, 2), (round(cl, 2) if cl is not None else None)


def build_refine_prompt(clips, segments, min_d, max_d):
    """Putaran kedua: AI memeriksa ulang tiap klip dengan transkrip detail di sekitarnya."""
    from .transcript import fmt_ts
    blocks = []
    for i, c in enumerate(clips):
        a, b = c["start"] - 35, c["end"] + 35
        lines = [f"[{fmt_ts(s['start'])} - {fmt_ts(s['end'])}] {s['text']}"
                 for s in segments if s["end"] > a and s["start"] < b]
        blocks.append(f"### KLIP {i}\nUsulan awal: start={fmt_ts(c['start'])} end={fmt_ts(c['end'])}"
                      f" | hook: {c.get('hook', '')}\nTranskrip sekitar:\n" + "\n".join(lines))
    return f"""Anda editor video pendek profesional. Untuk SETIAP klip di bawah, tentukan ulang batas waktu paling tepat
berdasarkan transkrip di sekitarnya agar klip menjadi cerita utuh: konteks pembuka -> klimaks -> reaksi/penutup.

Aturan:
- start: tepat di awal kalimat/pertanyaan yang memulai cerita (boleh digeser lebih awal agar konteks jelas).
- climax: waktu punchline/momen puncak.
- end: SETELAH klimaks dan reaksinya selesai (tawa/tanggapan/kesimpulan), di akhir kalimat. Jangan pernah memotong
  klimaks atau kalimat yang belum selesai.
- Durasi ideal {min_d}-{max_d} detik; boleh sampai {int(max_d * 1.3)} detik bila diperlukan agar klimaks utuh.
- Gunakan stempel waktu dari transkrip, format "HH:MM:SS.s".

Kembalikan HANYA JSON array: [{{"id": 0, "start": "...", "climax": "...", "end": "...",
"first_words": "5-8 kata pertama", "climax_words": "kata kunci klimaks", "last_words": "5-8 kata terakhir"}}]

""" + "\n\n".join(blocks)


def refine_clips(raw_clips, segments, min_d, max_d, video_dur, many=False):
    """Validasi + snap + buang duplikat. Kembalikan list dict siap pakai."""
    words = word_stream(segments) if segments else []
    out = []
    n = max(1, len(raw_clips))
    for i, c in enumerate(raw_clips):
        raw_s = c.get("start") or c.get("start_time") or c.get("startTime") or c.get("waktu_mulai")
        raw_e = c.get("end") or c.get("end_time") or c.get("endTime") or c.get("waktu_selesai")
        default_s = (video_dur / (n + 1)) * (i + 1) if video_dur else i * 60
        s = parse_time(raw_s, default=default_s)
        e = parse_time(raw_e, default=s + min_d)
        cl = parse_time(c.get("climax"), default=-1) if c.get("climax") else None
        if cl is not None and cl < 0:
            cl = None
        if video_dur and s >= video_dur - 2:
            continue
        if e <= s:
            e = s + (min_d + max_d) / 2
        s, e, cl = snap_clip(s, e, segments, min_d, max_d, video_dur, c.get("first_words"), c.get("last_words"),
                             climax=cl, climax_words=c.get("climax_words"), words=words)
        try:
            score = float(str(c.get("virality_score", 8.0)).replace(",", "."))
        except ValueError:
            score = 8.0
        hook = re.sub(r"[^\w\s!?.,'\"-]", "", str(c.get("hook", "")), flags=re.UNICODE).strip()
        out.append({
            "start": s, "end": e, "climax": cl,
            "name": c.get("name") or f"clip_{i + 1}",
            "hook": hook.upper(),
            "deskripsi": c.get("deskripsi", ""),
            "caption": c.get("caption", ""),
            "score": round(score, 1),
            "reason": c.get("viral_reason", c.get("reason", "")),
        })

    out.sort(key=lambda x: -x["score"])
    kept = []
    for c in out:
        clash = any(min(c["end"], k["end"]) - max(c["start"], k["start"])
                    > 0.4 * min(c["end"] - c["start"], k["end"] - k["start"]) for k in kept)
        if not clash:
            kept.append(c)
    if many:
        kept.sort(key=lambda x: x["start"])
    return kept[:30]


def second_pass(api_keys, clips, segments, min_d, max_d, video_dur, models=None, on_status=None):
    """Perbaiki batas klip dengan putaran AI kedua. Jika gagal, kembalikan klip apa adanya."""
    if not clips or not segments:
        return clips
    try:
        text = call_gemini(api_keys, build_refine_prompt(clips, segments, min_d, max_d), models=models,
                           on_status=on_status)
        fixes = {int(f.get("id", -1)): f for f in parse_clips(text)}
    except Exception:  # noqa: BLE001
        return clips
    words = word_stream(segments)
    out = []
    for i, c in enumerate(clips):
        f = fixes.get(i)
        if not f:
            out.append(c)
            continue
        s = parse_time(f.get("start"), default=c["start"])
        e = parse_time(f.get("end"), default=c["end"])
        cl = parse_time(f.get("climax"), default=-1) if f.get("climax") else None
        if cl is not None and cl < 0:
            cl = None
        if e <= s or abs(s - c["start"]) > 60:
            out.append(c)
            continue
        s, e, cl = snap_clip(s, e, segments, min_d, max_d, video_dur, f.get("first_words"), f.get("last_words"),
                             climax=cl, climax_words=f.get("climax_words"), words=words)
        out.append(dict(c, start=s, end=e, climax=cl))
    return out
