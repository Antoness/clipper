"""Pipeline render klip: potong -> kata (Whisper) -> [hapus jeda] -> crop -> zoom/warna -> subtitle -> encode."""
import os
import time

from . import tracking
from .ffmpeg import (ffmpeg_exe, decode_ffmpeg_exe, probe, run, supports_subtitles, video_encoder_args,
                     escape_filter_path, LIBX264)
from .paths import DOWNLOADS_DIR, rel, ensure_dirs

LAYOUT_AI = "🎯 AI Track Crop (9:16)"
LAYOUT_FACE = "Smart Face Crop (9:16)"
LAYOUT_CENTER = "Center Crop (9:16)"
LAYOUT_BLUR = "Blur Background (9:16)"
LAYOUT_ORIGINAL = "Asli (16:9)"
LAYOUTS = [LAYOUT_AI, LAYOUT_FACE, LAYOUT_CENTER, LAYOUT_BLUR, LAYOUT_ORIGINAL]

OUT_W, OUT_H = 1080, 1920
AUDIO_ARGS = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"
ENHANCE = "eq=contrast=1.05:saturation=1.12:brightness=0.01,unsharp=5:5:0.45:5:5:0"
# Versi pra-scale: diterapkan pada potongan kecil (sebelum diperbesar) -> ±3x lebih ringan
PRE_ENHANCE = "eq=contrast=1.05:saturation=1.12:brightness=0.01,unsharp=5:5:0.6:5:5:0"

DEFAULT_OPTIONS = {
    "subtitles": True,       # subtitle ucapan
    "style": None,           # dict gaya (engine.subtitles.DEFAULT_STYLE)
    "remove_silence": False, # hapus jeda hening (jump cut)
    "zoom": True,            # zoom dinamis halus
    "enhance": True,         # warna & ketajaman
}


class RenderError(Exception):
    pass


def _ok(path):
    return os.path.exists(path) and os.path.getsize(path) > 1000


def cut_raw(source, start, duration, out_path):
    """Potong segmen secara frame-accurate ke intermediate H.264 berkualitas tinggi (CRF 16)."""
    cmd = [decode_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
           "-ss", f"{start:.3f}", "-i", source, "-t", f"{duration:.3f}",
           "-map", "0:v:0", "-map", "0:a:0?", "-r", "30",
           "-c:v", "libx264", "-preset", "superfast", "-crf", "15", "-pix_fmt", "yuv420p",
           *AUDIO_ARGS, "-avoid_negative_ts", "make_zero", "-movflags", "+faststart", out_path]
    r = run(cmd)
    if r.returncode != 0 or not _ok(out_path):
        raise RenderError("Gagal memotong segmen: " + (r.stderr or "")[-400:])
    return out_path


# ----------------------------------------------------------------------------
# Hapus jeda hening (jump cut) — aman untuk tawa/reaksi
# ----------------------------------------------------------------------------
def silence_keep_intervals(words, duration, envelope, max_gap=0.5, pad=0.12):
    """Interval yang dipertahankan. Jeda antar kata > max_gap dibuang HANYA jika audionya benar-benar
    sepi (tawa, musik, reaksi tetap dipertahankan)."""
    if not words:
        return [(0.0, duration)]
    import numpy as np
    env = np.array(envelope) if envelope else None
    if env is None or not len(env):
        return [(0.0, duration)]          # tanpa info audio: jangan ambil risiko memotong
    noise = float(np.percentile(env, 10))
    speech = float(np.percentile(env, 70))
    thresh = noise + 0.3 * max(6.0, speech - noise)
    step = tracking.SAMPLE_STEP

    def quiet(a, b):
        i0, i1 = int(a / step), max(int(a / step) + 1, int(b / step))
        seg = env[i0:i1]
        # benar-benar sepi: rata-rata DAN puncaknya jauh di bawah level bicara
        return len(seg) > 0 and float(np.mean(seg)) < thresh and float(np.max(seg)) < speech - 6

    ivs = []
    cur_s = max(0.0, words[0]["start"] - 0.25)
    prev_end = words[0]["end"]
    for w in words[1:]:
        gap = w["start"] - prev_end
        # jeda > 3 dtk tanpa kata biasanya bagian yang tidak tertranskripsi / reaksi -> pertahankan
        if max_gap < gap <= 3.0 and quiet(prev_end + pad, w["start"] - pad):
            ivs.append((cur_s, prev_end + pad))
            cur_s = w["start"] - pad
        prev_end = max(prev_end, w["end"])
    ivs.append((cur_s, min(duration, prev_end + 0.8)))   # ekor: beri ruang reaksi
    ivs = [(round(a, 3), round(b, 3)) for a, b in ivs if b - a > 0.15]
    kept = sum(b - a for a, b in ivs)
    if kept < duration * 0.85:
        return [(0.0, duration)]          # terlalu banyak terbuang = transkripsi bolong, batalkan
    return ivs


def apply_intervals(raw_path, intervals, out_path):
    parts, labels = [], []
    for i, (a, b) in enumerate(intervals):
        parts.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}];")
        labels.append(f"[v{i}][a{i}]")
    graph = "".join(parts) + "".join(labels) + f"concat=n={len(intervals)}:v=1:a=1[v][a]"
    r = run([ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-i", raw_path,
             "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
             *AUDIO_ARGS, "-movflags", "+faststart", out_path])
    if r.returncode != 0 or not _ok(out_path):
        raise RenderError("Gagal menghapus jeda: " + (r.stderr or "")[-300:])
    return out_path


def remap_words(words, intervals):
    out, offset = [], 0.0
    for a, b in intervals:
        for w in words:
            if a - 0.01 <= w["start"] < b:
                out.append(dict(w, start=w["start"] - a + offset, end=min(w["end"], b) - a + offset))
        offset += b - a
    return out


# ----------------------------------------------------------------------------
# Filter video
# ----------------------------------------------------------------------------
def _even(n):
    return int(n) // 2 * 2


def crop_chain_static(iw, ih, x, enhance=False):
    cw = _even(ih * 9 / 16)
    x = int(max(0, min(iw - cw, x)))
    pre = PRE_ENHANCE + "," if enhance else ""
    return f"crop={cw}:{_even(ih)}:{x}:0,{pre}scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1"


def crop_chain_segments(iw, ih, segments, enhance=False):
    cw = _even(ih * 9 / 16)
    pre = PRE_ENHANCE + "," if enhance else ""
    return (f"crop={cw}:{_even(ih)}:{tracking.crop_x_expr(segments)}:0,{pre}"
            f"scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1")


CENTER_CHAIN = (f"crop=trunc(ih*9/16/2)*2:trunc(ih/2)*2:(iw-trunc(ih*9/16/2)*2)/2:0,"
                f"scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1")
_BLUR_BG = (f"scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=10:2,"
            f"scale={OUT_W}:{OUT_H},setsar=1")
_FIT_FG = f"scale={OUT_W}:-2:flags=lanczos,setsar=1"
BLUR_GRAPH = f"split[a][b];[b]{_BLUR_BG}[bg];[a]{_FIT_FG}[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"


def with_wide_shots(crop_chain, wide_ranges):
    """Crop pembicara, tapi tampilkan frame utuh di atas blur saat shot lebar (banyak orang)."""
    if not wide_ranges:
        return crop_chain
    enable = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in wide_ranges)
    return (f"split=3[c][w1][w2];[c]{crop_chain}[cv];[w1]{_BLUR_BG}[bg];[w2]{_FIT_FG}[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[wv];[cv][wv]overlay=enable='{enable}',setsar=1")


def detect_cuts(path, threshold=0.3):
    """Waktu pergantian kamera (presisi frame) via deteksi scene FFmpeg."""
    import re as _re
    r = run([decode_ffmpeg_exe(), "-hide_banner", "-i", path, "-an", "-vf",
             f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"], timeout=600)
    return sorted(float(m) for m in _re.findall(r"pts_time:([0-9.]+)", r.stderr or ""))


def snap_to_cuts(segments, wide_ranges, cuts, back=0.4, fwd=0.05):
    """Geser batas segmen/rentang ke frame pergantian kamera terdekat sebelumnya, supaya crop
    berganti TEPAT saat kamera berganti (bukan telat beberapa frame)."""
    def snap(t):
        cand = [c for c in cuts if t - back <= c <= t + fwd]
        return min(cand, key=lambda c: abs(c - t)) if cand else t
    segs = [list(sg) for sg in (segments or [])]
    for i in range(1, len(segs)):
        b = snap(segs[i][0])
        if segs[i - 1][0] < b < segs[i][1]:
            segs[i - 1][1] = segs[i][0] = round(b, 3)
    wide = [(round(snap(a), 3) if a > 0 else a, round(snap(b), 3)) for a, b in (wide_ranges or [])]
    return [tuple(sg) for sg in segs], [(a, b) for a, b in wide if b > a]


def build_video_filter(layout, raw_path, on_status=None, enhance=False):
    """Kembalikan (vf_dasar, out_w, out_h, segments, wide_ranges, catatan)."""
    info = probe(raw_path)
    iw, ih = info["width"] or 1920, info["height"] or 1080
    if layout == LAYOUT_ORIGINAL:
        return "setsar=1", _even(iw), _even(ih), None, [], ""
    if iw <= ih * 9 / 16 + 2:   # sumber sudah vertikal
        vf = (f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease:flags=lanczos,"
              f"pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2,setsar=1")
        return vf, OUT_W, OUT_H, None, [], ""
    if layout == LAYOUT_BLUR:
        return BLUR_GRAPH, OUT_W, OUT_H, None, [], ""
    if layout in (LAYOUT_AI, LAYOUT_FACE):
        if on_status:
            on_status("Melacak pembicara (audio + gerak bibir)..." if layout == LAYOUT_AI
                      else "Melacak wajah utama...")
        try:
            cuts = detect_cuts(raw_path)
            fn = tracking.ai_track_segments if layout == LAYOUT_AI else tracking.face_track_segments
            segs, _, _, wide = fn(raw_path, cuts=cuts)
            if segs:
                segs, wide = snap_to_cuts(segs, wide, cuts)
        except Exception as e:  # noqa: BLE001
            return CENTER_CHAIN, OUT_W, OUT_H, None, [], f"Tracking error: {e}. Memakai Center Crop."
        if segs:
            chain = (crop_chain_segments(iw, ih, segs, enhance) if len(segs) > 1
                     else crop_chain_static(iw, ih, segs[0][2], enhance))
            return with_wide_shots(chain, wide), OUT_W, OUT_H, segs, wide, ""
        return CENTER_CHAIN, OUT_W, OUT_H, None, [], "Tidak ada orang terdeteksi, memakai Center Crop."
    return CENTER_CHAIN, OUT_W, OUT_H, None, [], ""


def plan_zooms(segments, wide_ranges, words, duration, strength=0.10):
    """Rencana punch-in halus: zoom pada segmen pembicara bergantian, atau tiap beberapa kalimat."""
    marks = []
    if segments and len(segments) > 1:
        marks = [(a, b) for i, (a, b, _x) in enumerate(segments) if i % 2 == 1 and b - a >= 1.2]
    else:
        # tidak ada pergantian kamera: zoom bergantian setiap ±4 detik di batas kalimat
        bounds = [0.0]
        for w in words or []:
            if w["raw"].rstrip().endswith((".", "?", "!")) and w["end"] - bounds[-1] >= 3.5:
                bounds.append(w["end"])
        if len(bounds) < 3:
            bounds = [i * 4.0 for i in range(int(duration // 4) + 1)]
        bounds.append(duration)
        marks = [(bounds[i], bounds[i + 1]) for i in range(1, len(bounds) - 1, 2)]
    wide = wide_ranges or []
    marks = [(a, b) for a, b in marks if not any(a < wb and b > wa for wa, wb in wide)]
    return [(round(a, 2), round(b, 2), 1 + strength) for a, b in marks]


def zoom_chain(zooms):
    """Punch-in zoom STABIL (crop tetap + overlay pada rentang waktu). Tanpa zoompan yang bergetar."""
    if not zooms:
        return ""
    z = float(zooms[0][2])
    enable = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b, _z in zooms)
    return (f"split[zb][zz];[zz]crop=trunc(iw/{z}/2)*2:trunc(ih/{z}/2)*2:(iw-iw/{z})/2:(ih-ih/{z})*0.38,"
            f"scale={OUT_W}:{OUT_H}:flags=bicubic,setsar=1[zo];[zb][zo]overlay=enable='{enable}'")


def compose_filter(base_vf, zooms=None, enhance=True, out_w=OUT_W):
    vf = base_vf
    if zooms and out_w == OUT_W:
        vf += "," + zoom_chain(zooms)
    if enhance and "unsharp" not in base_vf:   # crop chain sudah membawa pra-enhance
        vf += "," + ENHANCE
    return vf


def render_final(raw_path, vf, out_path, ass_path=None, normalize_audio=True):
    from .subtitles import FONTS_DIR
    if ass_path and supports_subtitles():
        vf = (f"{vf},subtitles=filename={escape_filter_path(rel(ass_path))}"
              f":fontsdir={escape_filter_path(rel(FONTS_DIR))}")
    uses_graph = ";" in vf or "[" in vf
    cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-i", raw_path]
    cmd += (["-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "0:a?"] if uses_graph else ["-vf", vf])
    if normalize_audio:
        cmd += ["-af", LOUDNORM]
    enc = video_encoder_args()
    cmd += [*enc, "-r", "30", *AUDIO_ARGS, "-movflags", "+faststart", out_path]
    r = run(cmd)
    if r.returncode != 0 or not _ok(out_path):
        i = cmd.index(enc[0])
        r2 = run(cmd[:i] + LIBX264 + cmd[i + len(enc):])   # fallback encoder software
        if r2.returncode != 0 or not _ok(out_path):
            raise RenderError("Gagal render: " + ((r2.stderr or r.stderr) or "")[-500:])
    return out_path


def make_preview(final_path):
    """Versi ringan (540x960, ±3-5 MB) khusus untuk diputar di browser agar tidak buffering.
    File download tetap memakai kualitas penuh."""
    out = os.path.splitext(final_path)[0] + "_preview.mp4"
    r = run([ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-i", final_path,
             "-vf", "scale=540:-2:flags=bicubic", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
             "-maxrate", "1500k", "-bufsize", "3000k", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out])
    return out if r.returncode == 0 and _ok(out) else final_path


# ----------------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------------
def process_clip(source, clip, layout, out_name, transcript=None, language=None,
                 initial_prompt=None, options=None, on_status=None):
    """Proses satu klip penuh. Kembalikan dict hasil untuk UI."""
    from .subtitles import transcribe_words, build_ass, make_style

    opts = dict(DEFAULT_OPTIONS, **(options or {}))
    style = make_style(**(opts.get("style") or {}))
    style["sub_enabled"] = bool(opts["subtitles"]) and style.get("sub_enabled", True)
    status = on_status or (lambda *_: None)
    ensure_dirs()
    start, end = float(clip["start"]), float(clip["end"])
    raw_path = os.path.join(DOWNLOADS_DIR, f"raw_{out_name}.mp4")
    final_path = os.path.join(DOWNLOADS_DIR, f"{out_name}.mp4")
    t0 = time.time()
    notes = []

    status("Memotong segmen video...", 10)
    cut_raw(source, start, end - start, raw_path)
    work = raw_path
    dur = probe(work)["duration"] or (end - start)

    words, sub_source = [], "none"
    if opts["subtitles"] or opts["remove_silence"] or opts["zoom"]:
        status("Mentranskripsi kata per kata (Whisper)...", 25)
        words, sub_source, err = transcribe_words(raw_path, dur, language=language,
                                                  transcript_segments=transcript, clip_start=start,
                                                  initial_prompt=initial_prompt)
        if err:
            notes.append(err)

    if opts["remove_silence"] and words:
        env = tracking.audio_envelope(raw_path)
        ivs = silence_keep_intervals(words, dur, env)
        kept = sum(b - a for a, b in ivs)
        if len(ivs) > 1 or kept < dur - 0.6:
            status(f"Menghapus jeda hening ({dur - kept:.1f} dtk)...", 35)
            tight = os.path.join(DOWNLOADS_DIR, f"raw_{out_name}_tight.mp4")
            apply_intervals(raw_path, ivs, tight)
            words = remap_words(words, ivs)
            work = tight
            dur = probe(work)["duration"] or kept
            notes.append(f"Jeda hening dihapus: {len(ivs) - 1} potongan, hemat {max(0, (end - start) - dur):.1f} dtk.")

    status("Menganalisis framing...", 45)
    base_vf, out_w, out_h, segs, wide, note = build_video_filter(layout, work, on_status=lambda m: status(m, 50),
                                                                 enhance=opts["enhance"])
    if note:
        notes.append(note)
    zooms = plan_zooms(segs, wide, words, dur) if (opts["zoom"] and layout != LAYOUT_ORIGINAL) else []

    status("Membuat subtitle...", 75)
    ass_path = build_ass(words if style["sub_enabled"] else [], dur, out_w, out_h,
                         hook=clip.get("hook", ""), style=style)

    status("Render video akhir...", 85)
    render_final(work, compose_filter(base_vf, zooms, opts["enhance"], out_w), final_path, ass_path=ass_path)
    preview_path = make_preview(final_path)

    if not supports_subtitles():
        notes.append("FFmpeg di mesin ini tidak mendukung libass; subtitle tidak dibakar. "
                     "Jalankan `pip install imageio-ffmpeg`.")
    return {
        "out": f"{out_name}.mp4", "path": final_path, "preview_path": preview_path, "raw_path": work,
        "start": start, "end": end, "duration": dur,
        "caption": clip.get("caption", ""), "hook": clip.get("hook", ""),
        "deskripsi": clip.get("deskripsi", ""), "score": clip.get("score", 8.0),
        "reason": clip.get("reason", ""), "layout": layout, "status": "success",
        "ai_segments": segs, "wide_ranges": wide, "base_vf": base_vf, "zooms": zooms,
        "enhance": opts["enhance"], "words": words, "style": style, "ass_path": ass_path,
        "out_w": out_w, "out_h": out_h, "sub_source": sub_source if style["sub_enabled"] else "none",
        "notes": notes, "elapsed": round(time.time() - t0, 1),
    }


def _new_output_path(clip_data, suffix):
    base = os.path.join(DOWNLOADS_DIR, os.path.splitext(clip_data["out"])[0])
    return f"{base}_{suffix}_{int(time.time() * 1000) % 10_000_000}.mp4"


def restyle_clip(clip_data, style, hook=None):
    """Render ulang klip dengan gaya subtitle/hook baru TANPA proses ulang (pakai kata & framing tersimpan)."""
    from .subtitles import build_ass, make_style
    st = make_style(**style)
    if clip_data.get("sub_source") == "none" and not clip_data.get("words"):
        st["sub_enabled"] = False
    hook = clip_data.get("hook", "") if hook is None else hook
    ass = build_ass(clip_data.get("words") or [], clip_data["duration"], clip_data["out_w"], clip_data["out_h"],
                    hook=hook, style=st)
    vf = compose_filter(clip_data["base_vf"], clip_data.get("zooms"), clip_data.get("enhance", True),
                        clip_data["out_w"])
    new_path = _new_output_path(clip_data, "style")
    render_final(clip_data["raw_path"], vf, new_path, ass_path=ass)
    return new_path, ass, st, make_preview(new_path)


def rerender_with_segments(clip_data, segments):
    """Render ulang dengan segmen crop manual (subtitle, zoom & warna dipertahankan)."""
    from .subtitles import build_ass
    raw = clip_data["raw_path"]
    info = probe(raw)
    base = crop_chain_segments(info["width"], info["height"], segments, enhance=clip_data.get("enhance", True))
    zooms = plan_zooms(segments, [], clip_data.get("words"), clip_data["duration"]) if clip_data.get("zooms") else []
    ass = build_ass(clip_data.get("words") or [], clip_data["duration"], OUT_W, OUT_H,
                    hook=clip_data.get("hook", ""), style=clip_data.get("style"))
    new_path = _new_output_path(clip_data, "edit")
    render_final(raw, compose_filter(base, zooms, clip_data.get("enhance", True)), new_path, ass_path=ass)
    return new_path, base, zooms, make_preview(new_path)


def merge_clips(paths, out_path):
    """Gabungkan klip (re-encode agar aman walau resolusi/encoder berbeda)."""
    if not paths:
        raise RenderError("Tidak ada klip untuk digabung.")
    cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error"]
    for p in paths:
        cmd += ["-i", p]
    parts = "".join(
        f"[{i}:v]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease,pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,fps=30[v{i}];[{i}:a]aresample=48000[a{i}];" for i in range(len(paths)))
    concat = "".join(f"[v{i}][a{i}]" for i in range(len(paths))) + f"concat=n={len(paths)}:v=1:a=1[v][a]"
    cmd += ["-filter_complex", parts + concat, "-map", "[v]", "-map", "[a]",
            *video_encoder_args(), *AUDIO_ARGS, "-movflags", "+faststart", out_path]
    r = run(cmd)
    if r.returncode != 0 or not _ok(out_path):
        raise RenderError("Gagal menggabungkan: " + (r.stderr or "")[-500:])
    return out_path
