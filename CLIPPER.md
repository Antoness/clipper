# 🎬 YouClip — AI Video Clipper (macOS • Windows • Linux)

Mengubah video YouTube panjang (podcast, talkshow, vlog) menjadi klip vertikal 9:16 siap upload
ke TikTok/Reels/Shorts, lengkap dengan hook, subtitle karaoke, caption, dan skor viralitas.

---

## 1. Alur Kerja

```
URL YouTube
   │
   ├─ Metadata (oEmbed / yt-dlp)
   ├─ Transkrip: youtube-transcript-api → caption yt-dlp (json3, timing per kata) → Whisper lokal → audio ke Gemini
   │
   ├─ Gemini memilih momen viral dari TRANSKRIP LENGKAP (tidak dipotong)
   ├─ Batas klip di-snap ke awal/akhir kalimat terdekat, klip tumpang tindih dibuang
   │
   ├─ yt-dlp: unduh sumber SEKALI (utamakan H.264), di-cache
   ├─ FFmpeg: potong frame-accurate → intermediate H.264 CRF 16
   ├─ Crop 9:16: AI Track (YOLOv8-pose + deteksi pembicara via gerak bibir + deteksi pergantian kamera)
   ├─ Subtitle: Whisper (word timestamps, VAD) → file ASS karaoke; fallback caption YouTube
   └─ Encode akhir: encoder terbaik yang tersedia + normalisasi loudness (-14 LUFS)
```

Struktur kode:

| File | Isi |
|---|---|
| `app.py` | UI Streamlit (halaman Beranda, AI, Pengaturan Klip, Render, Bantuan) |
| `engine/youtube.py` | yt-dlp (metadata, search, download), runtime Deno/Node, cookies |
| `engine/transcript.py` | Transkrip YouTube/yt-dlp/Whisper + format prompt |
| `engine/highlights.py` | Prompt & panggilan Gemini, parsing, snapping batas klip |
| `engine/tracking.py` | AI Track Crop & Smart Face Crop |
| `engine/subtitles.py` | Pembuat subtitle ASS karaoke |
| `engine/render.py` | Pipeline potong → crop → subtitle → encode, merge, re-render manual |
| `engine/ffmpeg.py` | Deteksi FFmpeg (libass), encoder hardware, probe |

## 2. Instalasi

Butuh **Python 3.10+**. FFmpeg sistem opsional: paket `imageio-ffmpeg` sudah membawa FFmpeg
lengkap dengan libass (dibutuhkan untuk membakar subtitle).

### macOS
```bash
brew install python ffmpeg
python3 -m venv venv.nosync          # .nosync: jangan disinkronkan iCloud
source venv.nosync/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Windows (PowerShell)
```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg            # opsional
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### Linux (Debian/Ubuntu) / Streamlit Cloud
```bash
sudo apt install python3-venv ffmpeg libgl1 libglib2.0-0 nodejs
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Di Streamlit Cloud, paket sistem dibaca dari `packages.txt`.

## 3. Konfigurasi — `.streamlit/secrets.toml` (atau environment variable)

```toml
GEMINI_API_KEYS = ["key1", "key2"]   # wajib, beberapa key dirotasi saat kena limit
YOUTUBE_COOKIES = """..."""           # opsional: isi cookies.txt (Netscape) bila YouTube memblokir
GEMINI_MODEL = "gemini-2.5-flash"     # opsional
WHISPER_MODEL = "small"               # small (default) | base (cepat) | medium (akurat, berat)
CLIPPER_ENCODER = "auto"              # auto | libx264 | videotoolbox | nvenc | qsv | amf
```

Environment variable tambahan: `CLIPPER_WORKERS` (klip paralel, default 2),
`CLIPPER_WORK_DIR` (folder kerja), `FFMPEG_BINARY` (paksa binary FFmpeg tertentu).

## 4. Catatan Penting

- **iCloud Drive (macOS):** jika project ada di Desktop/Documents yang disinkronkan iCloud, iCloud bisa
  menimpa/menghapus file video yang sedang ditulis. Karena itu folder kerja di macOS adalah
  `downloads.nosync/` (diabaikan iCloud). Cache lama di `downloads/` tetap terbaca.
- Menu **Bantuan** di aplikasi menampilkan diagnostik: FFmpeg yang dipakai, dukungan subtitle, encoder, Whisper.
- Proses pertama kali akan mengunduh model Whisper (±500 MB untuk `small`).
