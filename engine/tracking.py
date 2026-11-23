"""Pelacakan subjek untuk crop 9:16 — deteksi PEMBICARA AKTIF berbasis audio + visual.

Cara kerja (mode "speaker", dipakai AI Track Crop):
1. Frame dibaca berurutan, disampling 5x per detik.
2. YOLOv8-pose mendeteksi orang (benda mati ditolak lewat keypoint wajah/bahu).
3. Orang dilacak antar-frame (ID tetap) dan direset saat pergantian kamera.
4. Untuk tiap orang: wajah di-crop dari keypoint lalu MediaPipe FaceLandmarker
   mengukur bukaan mulut (blendshape jawOpen + jarak bibir).
5. Energi audio diekstrak dari klip. Skor bicara = gerakan mulut x korelasi dengan suara.
   Orang yang mulutnya bergerak SAAT ada suara = pembicara.
6. Keputusan pakai histeresis (tidak pindah-pindah karena noise) + durasi tampil minimum.
7. Dua orang berdekatan -> dibingkai berdua. Tidak ada manusia -> ikuti area yang bergerak.

Mode "face" (Smart Face Crop): mengikuti wajah/orang paling dominan dengan histeresis.

Output: segmen [(t_mulai, t_selesai, crop_x_px)].
"""
import os
import subprocess
import threading

from .paths import asset

_YOLO_LOCK = threading.Lock()       # serialisasi inferensi (model YOLO tidak thread-safe)
_YOLO_INIT_LOCK = threading.Lock()
_YOLO = None

SAMPLE_STEP = 0.25
SPEAK_MIN = 0.004        # skor bicara minimum (dikalibrasi)
MOUTH_STEP = 1 / 10.0     # ukur mulut 12x/dtk agar ritme suku kata tertangkap


def _yolo():
    global _YOLO
    with _YOLO_INIT_LOCK:
        if _YOLO is None:
            from ultralytics import YOLO
            _YOLO = YOLO(asset("yolov8n-pose.pt"))
        return _YOLO


# ----------------------------------------------------------------------------
# Audio
# ----------------------------------------------------------------------------
def audio_envelope(path, step=SAMPLE_STEP):
    """Energi audio (dB) per `step` detik. Kembalikan list float (kosong jika tak ada audio)."""
    import numpy as np
    from .ffmpeg import decode_ffmpeg_exe, _NO_WINDOW
    try:
        p = subprocess.run([decode_ffmpeg_exe(), "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000",
                            "-f", "s16le", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, timeout=300, creationflags=_NO_WINDOW)
        pcm = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return []
    hop = int(16000 * step)
    if len(pcm) < hop:
        return []
    n = len(pcm) // hop
    frames = pcm[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-10)
    return list(20 * np.log10(rms))


# ----------------------------------------------------------------------------
# Deteksi
# ----------------------------------------------------------------------------
def _people(frame_rgb, iw, ih):
    """Deteksi orang valid. Kembalikan list dict {cx, area, box, head}."""
    import cv2
    small_w = 640
    small_h = max(2, int(small_w * ih / iw))
    small = cv2.resize(frame_rgb, (small_w, small_h))
    with _YOLO_LOCK:
        res = _yolo().predict(small, classes=[0], conf=0.25, verbose=False)
    out = []
    if not res or res[0].boxes is None or len(res[0].boxes) == 0 or res[0].keypoints is None:
        return out
    boxes = res[0].boxes.xyxy.cpu().numpy()
    kpts = res[0].keypoints.data.cpu().numpy()
    sx, sy = iw / small_w, ih / small_h
    for i in range(len(boxes)):
        x1, y1, x2, y2 = boxes[i]
        if (y2 - y1) < small_h * 0.12:
            continue
        k = kpts[i]
        face_pts = [(k[j, 0], k[j, 1]) for j in range(5) if k[j, 2] > 0.3]      # hidung, mata, telinga
        upper = [k[j, 0] for j in range(7) if k[j, 2] > 0.15]                  # + bahu
        strong = sum(1 for j in range(7) if k[j, 2] > 0.3)
        if len(upper) < 2 or strong < 2:
            continue  # bukan manusia (toples/bantal/sepeda) atau terlalu terpotong
        if face_pts:
            fx = sum(p[0] for p in face_pts) / len(face_pts)
            fy = sum(p[1] for p in face_pts) / len(face_pts)
            xs = [p[0] for p in face_pts]
            fsize = max(max(xs) - min(xs) * 1.0, (x2 - x1) * 0.28, 12)
            fsize = max(fsize * 1.6, (x2 - x1) * 0.3)
            cx = fx
        else:
            fx, fy = (x1 + x2) / 2, y1 + (y2 - y1) * 0.15
            fsize = (x2 - x1) * 0.45
            cx = sum(upper) / len(upper)
        half = fsize * 1.1
        head = (int((fx - half) * sx), int((fy - half) * sy), int((fx + half) * sx), int((fy + half) * sy))
        out.append({"cx": cx * sx, "area": (x2 - x1) * (y2 - y1) * sx * sy,
                    "box": (x1 * sx, y1 * sy, x2 * sx, y2 * sy), "head": head, "has_face": bool(face_pts)})
    return out


def _mouth(frame_rgb, head, iw, ih, landmarker):
    """Bukaan mulut 0..1 (jawOpen + jarak bibir ternormalisasi). None jika wajah tak terbaca."""
    import cv2
    import numpy as np
    import mediapipe as mp
    x1, y1, x2, y2 = head
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(iw, x2), min(ih, y2)
    if x2 - x1 < 24 or y2 - y1 < 24:
        return None
    crop = frame_rgb[y1:y2, x1:x2]
    if crop.shape[0] < 192:
        scale = 192.0 / crop.shape[0]
        crop = cv2.resize(crop, (int(crop.shape[1] * scale), 192))
    r = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(crop)))
    if not r.face_landmarks:
        return None
    lm = r.face_landmarks[0]
    face_h = abs(lm[152].y - lm[10].y) or 1e-3
    gap = abs(lm[14].y - lm[13].y) / face_h
    jaw = 0.0
    if getattr(r, "face_blendshapes", None):
        for b in r.face_blendshapes[0]:
            if b.category_name == "jawOpen":
                jaw = b.score
                break
    return float(min(1.0, gap * 3.0 + jaw))


def _shot_change(prev, cur):
    import cv2
    if prev is None or cur is None:
        return False

    def hist(f):
        hsv = cv2.cvtColor(cv2.resize(f, (160, 90)), cv2.COLOR_RGB2HSV)
        h = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        return cv2.normalize(h, h).flatten()
    return cv2.compareHist(hist(prev), hist(cur), cv2.HISTCMP_BHATTACHARYYA) > 0.45


def _motion_center(prev, cur, iw):
    """Pusat X area yang bergerak (untuk video tanpa manusia)."""
    import cv2
    import numpy as np
    if prev is None or cur is None:
        return None
    a = cv2.cvtColor(cv2.resize(prev, (320, 180)), cv2.COLOR_RGB2GRAY)
    b = cv2.cvtColor(cv2.resize(cur, (320, 180)), cv2.COLOR_RGB2GRAY)
    diff = cv2.GaussianBlur(cv2.absdiff(a, b), (9, 9), 0)
    _, th = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
    m = cv2.moments(th)
    if m["m00"] < 255 * 150:
        return None
    return float(m["m10"] / m["m00"] * iw / 320)


def _landmarker():
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    opts = mp_vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=asset("face_landmarker.task")),
        num_faces=1, min_face_detection_confidence=0.3, min_face_presence_confidence=0.3,
        output_face_blendshapes=True)
    return mp_vision.FaceLandmarker.create_from_options(opts)


# ----------------------------------------------------------------------------
# Analisis utama
# ----------------------------------------------------------------------------
def analyze(path, mode="speaker", on_progress=None, cuts=None):
    """Kembalikan (segments, iw, ih, wide_ranges). mode: 'speaker' | 'face'.

    wide_ranges: rentang waktu shot lebar (banyak orang kecil) yang sebaiknya ditampilkan
    utuh di atas background blur daripada di-crop (crop akan memotong orang)."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(os.path.abspath(path))
    if not cap.isOpened():
        return [], 0, 0, []
    iw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ih = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = n_frames / fps if n_frames > 0 else 0
    crop_w = int(ih * 9 / 16)
    if iw <= crop_w + 2 or duration <= 0:
        cap.release()
        return [], iw, ih, []

    landmarker = None
    if mode == "speaker":
        try:
            landmarker = _landmarker()
        except Exception:
            landmarker = None
    env = audio_envelope(path, step=MOUTH_STEP) if mode == "speaker" else []

    # --- Pass 1: deteksi orang (4x/dtk) + ukur mulut (12x/dtk) ---
    samples = []          # per sampel kasar: {t, cut, people:[{id,cx,area,...}], motion}
    mouth_fine = {}       # pid -> list (t, bukaan_mulut)
    tracks = {}           # id -> cx terakhir
    next_id = 0
    prev_rgb = None
    current_people = []
    coarse = {int(round(i * SAMPLE_STEP * fps)): i * SAMPLE_STEP for i in range(int(duration / SAMPLE_STEP))}
    fine = {}
    if landmarker is not None:
        fine = {int(round(i * MOUTH_STEP * fps)): i * MOUTH_STEP for i in range(int(duration / MOUTH_STEP))}
    last_frame = max(list(coarse) + list(fine) + [0])
    fidx = 0
    while fidx <= last_frame:
        if not cap.grab():
            break
        is_coarse, is_fine = fidx in coarse, fidx in fine
        if is_coarse or is_fine:
            ok, frame = cap.retrieve()
            if ok:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if is_coarse:
                    t = coarse[fidx]
                    if cuts is not None:   # pergantian kamera presisi dari FFmpeg
                        prev_t = samples[-1]["t"] if samples else -1.0
                        cut = any(prev_t < c <= t + 1e-3 for c in cuts) and bool(samples)
                    else:
                        cut = _shot_change(prev_rgb, rgb)
                    if cut:
                        tracks = {}
                    people = _people(rgb, iw, ih)
                    used = set()
                    for p in sorted(people, key=lambda q: -q["area"]):
                        best, best_d = None, iw * 0.12
                        for tid, tcx in tracks.items():
                            d = abs(tcx - p["cx"])
                            if tid not in used and d < best_d:
                                best, best_d = tid, d
                        if best is None:
                            best = next_id
                            next_id += 1
                        used.add(best)
                        p["id"] = best
                        tracks[best] = p["cx"]
                    motion = _motion_center(prev_rgb, rgb, iw) if not people else None
                    samples.append({"t": t, "cut": cut, "people": people, "motion": motion})
                    current_people = people
                    prev_rgb = rgb
                    if on_progress and len(samples) % 25 == 0:
                        on_progress(len(samples) / max(1, len(coarse)))
                if is_fine and len(current_people) >= 2:
                    # mulut hanya relevan saat ada >=2 orang; cukup 3 orang terbesar yang cukup besar di layar
                    t = fine[fidx]
                    big = [p for p in current_people if p["has_face"] and (p["box"][3] - p["box"][1]) >= ih * 0.3]
                    for p in sorted(big, key=lambda q: -q["area"])[:3]:
                        if True:
                            mouth_fine.setdefault(p["id"], []).append((t, _mouth(rgb, p["head"], iw, ih, landmarker)))
        fidx += 1
    cap.release()
    if landmarker is not None:
        landmarker.close()
    if not samples:
        return [], iw, ih, []

    # --- Pass 2: skor bicara = gerak mulut yang SINKRON dengan energi suara ---
    n = len(samples)
    env_f = np.array(env) if env else np.array([])
    if len(env_f):
        noise, loud = np.percentile(env_f, 15), np.percentile(env_f, 90)
        env_n = np.clip((env_f - noise) / max(6.0, loud - noise), 0, 1)
    else:
        env_n = env_f

    def audio_at(ts):
        if not len(env_n):
            return np.ones(len(ts))
        idx = np.clip((np.asarray(ts) / MOUTH_STEP).astype(int), 0, len(env_n) - 1)
        return env_n[idx]

    speak = {}
    corr_map = {}
    for pid, series in mouth_fine.items():
        ts = np.array([s[0] for s in series])
        ms = np.array([np.nan if s[1] is None else s[1] for s in series])
        score = np.full(n, np.nan)
        corrs = np.zeros(n)
        for i, s in enumerate(samples):
            sel = (ts >= s["t"] - 1.0) & (ts <= s["t"] + 1.0)
            m = ms[sel]
            ok = ~np.isnan(m)
            if ok.sum() < 8:
                continue                      # wajah tidak terbaca -> tidak diketahui
            m_ok, a_ok = m[ok], audio_at(ts[sel][ok])
            dm = np.abs(np.diff(m_ok))
            da = np.abs(np.diff(a_ok))
            movement = float(np.mean(dm)) + 0.3 * float(np.std(m_ok))
            voiced = float(np.mean(a_ok > 0.3))
            c1 = c2 = 0.0
            if np.std(m_ok) > 1e-4 and np.std(a_ok) > 1e-4:
                c1 = float(np.corrcoef(m_ok, a_ok)[0, 1])
            if len(dm) > 3 and np.std(dm) > 1e-4 and np.std(da) > 1e-4:
                c2 = float(np.corrcoef(dm, da)[0, 1])
            corr = max(0.0, c1, c2)
            corrs[i] = corr
            score[i] = movement * (0.25 + voiced) * (0.4 + 2.5 * corr)
        speak[pid] = score
        corr_map[pid] = corrs

    # --- Pass 3: keputusan target per sampel ---
    xs = []
    cur_id, cur_since, challenger, chall_count = None, 0.0, None, 0
    last_x = (iw - crop_w) / 2
    for i, s in enumerate(samples):
        people = s["people"]
        if s["cut"]:
            cur_id, challenger, chall_count = None, None, 0
        target_x = None
        wide = False
        if people:
            cxs = [p["cx"] for p in people]
            heights = sorted(p["box"][3] - p["box"][1] for p in people)
            wide = (len(people) >= 3 and max(cxs) - min(cxs) > crop_w * 1.1
                    and heights[len(heights) // 2] < ih * 0.45)
            by_id = {p["id"]: p for p in people}
            if len(people) == 1:
                cur_id = people[0]["id"]
                target_x = people[0]["cx"]
            elif max(cxs) - min(cxs) <= crop_w * 0.55:
                target_x = (max(cxs) + min(cxs)) / 2       # muat berdua dalam frame
            else:
                if mode == "speaker":
                    scores = {}
                    for pid in by_id:
                        v = speak.get(pid, None)
                        if v is not None and not np.isnan(v[i]):
                            scores[pid] = float(v[i])
                    corr_i = {pid: float(corr_map[pid][i]) for pid in scores}
                    best = max(scores, key=scores.get) if scores else None
                    if cur_id not in by_id:
                        # belum ada / hilang: pembicara terkuat yang sinkron dengan suara, atau orang terbesar
                        # yang wajahnya terlihat (orang yang membelakangi kamera bukan subjek yang baik)
                        if best is not None and scores[best] > SPEAK_MIN * 3 and corr_i[best] > 0.08:
                            cur_id = best
                        else:
                            cur_id = max(by_id, key=lambda k: by_id[k]["area"])
                        cur_since = s["t"]
                        challenger, chall_count = None, 0
                    elif best is not None and best != cur_id:
                        cur_score = scores.get(cur_id)
                        if cur_score is None:
                            # wajah orang yang sedang dibingkai tak terbaca: pindah ke yang jelas bicara
                            strong = scores[best] > SPEAK_MIN * 3 and corr_i[best] > 0.1
                            need_n = 2
                        else:
                            cur_corr = corr_i.get(cur_id, 0.0)
                            strong = ((scores[best] > max(SPEAK_MIN, 1.5 * cur_score) and corr_i[best] > 0.15)
                                      or (scores[best] > 1.1 * cur_score and corr_i[best] > cur_corr + 0.2))
                            need_n = 3
                        if strong:
                            chall_count = chall_count + 1 if challenger == best else 1
                            challenger = best
                            if chall_count >= need_n and s["t"] - cur_since >= 1.5:
                                cur_id, cur_since, challenger, chall_count = best, s["t"], None, 0
                        else:
                            challenger, chall_count = None, 0
                    else:
                        challenger, chall_count = None, 0
                else:  # mode face: orang paling dominan dengan histeresis
                    biggest = max(by_id, key=lambda k: by_id[k]["area"])
                    if cur_id not in by_id or by_id[biggest]["area"] > 1.5 * by_id[cur_id]["area"]:
                        cur_id = biggest
                target_x = by_id[cur_id]["cx"]
        elif s["motion"] is not None:
            target_x = s["motion"]
        if target_x is None:
            x = last_x
        else:
            x = max(0, min(iw - crop_w, target_x - crop_w / 2))
        last_x = x
        xs.append((s["t"], x, s["cut"], cur_id, wide))

    # --- Pass 4: segmentasi + stabilisasi ---
    tol = iw * 0.07
    segs = []
    # Rentang shot lebar (mayoritas sampel dalam satu shot lebar, minimal 1 dtk)
    wide_ranges = []
    shot_start = 0
    for i in range(1, len(xs) + 1):
        if i == len(xs) or xs[i][2]:
            chunk = xs[shot_start:i]
            if chunk and sum(1 for c in chunk if c[4]) >= 0.6 * len(chunk):
                a = chunk[0][0]
                b = xs[i][0] if i < len(xs) else duration
                if b - a >= 1.0:
                    wide_ranges.append((round(a, 2), round(b, 2)))
            shot_start = i

    start, vals, sid = xs[0][0], [xs[0][1]], xs[0][3]
    for t, x, cut, pid, _w in xs[1:]:
        avg = float(np.median(vals))
        if cut or (pid != sid and abs(x - avg) > tol * 0.5) or abs(x - avg) > tol:
            segs.append([start, t, vals])
            start, vals, sid = t, [x], pid
        else:
            vals.append(x)
    segs.append([start, duration, vals])

    merged = []
    for sg in segs:
        if merged and sg[1] - sg[0] < 1.4:
            merged[-1][1] = sg[1]
            merged[-1][2].extend(sg[2])
        else:
            merged.append(sg)
    if len(merged) > 1 and merged[0][1] - merged[0][0] < 1.4:
        merged[1][0] = merged[0][0]
        merged.pop(0)
    out = [(round(a, 2), round(b, 2), int(np.median(v))) for a, b, v in merged]
    # gabungkan segmen bertetangga yang posisinya hampir sama
    final = [out[0]]
    for a, b, x in out[1:]:
        if abs(x - final[-1][2]) < iw * 0.025:
            final[-1] = (final[-1][0], b, final[-1][2])
        else:
            final.append((a, b, x))
    analyze.debug = {"samples": samples, "speak": speak, "corr": corr_map, "xs": xs}
    return final, iw, ih, wide_ranges


def ai_track_segments(path, on_progress=None, cuts=None):
    return analyze(path, mode="speaker", on_progress=on_progress, cuts=cuts)


def face_track_segments(path, on_progress=None, cuts=None):
    return analyze(path, mode="face", on_progress=on_progress, cuts=cuts)


def crop_x_expr(segments):
    """Ekspresi FFmpeg piecewise untuk posisi x crop (dibungkus kutip tunggal di filter)."""
    expr = str(int(segments[-1][2]))
    for s_start, s_end, x in reversed(segments[:-1]):
        expr = f"if(lt(t,{s_end:.2f}),{int(x)},{expr})"
    return f"'{expr}'"
