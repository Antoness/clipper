# 🎬 LOCAL VIDEO CLIPPER SYSTEM (TERIMA JADI)

Dokumentasi dan kode sumber lengkap untuk menjalankan **Video Clipper Dashboard** secara lokal di komputer Anda. Sistem ini menggunakan **Streamlit** untuk UI, **yt-dlp** untuk ekstraksi URL, dan **FFmpeg** untuk pemotongan instan berkecepatan tinggi tanpa proses *re-encoding* ulang (hanya butuh waktu 1–3 detik saja).

---

## 1. Alur Kerja Sistem (System Workflow)
+-----------------------------------------------------------------------+
|                           FRONTEND UI (Streamlit)                     |
|  1. Input URL YouTube  -->  2. Tampilkan Metadata  --> 3. Set Waktu   |
+---------------------------------------------------+-------------------+
|
v (Kirim Parameter Clip)
+---------------------------------------------------+-------------------+
|                        BACKEND WORKER & ENGINE PROCESSING             |
|  4. yt-dlp: Ekstrak Direct Stream URL (Video & Audio Terpisah)        |
|  5. FFmpeg: Fast-seeking (-ss sebelum -i) & Stream Copying (-c copy)  |
+---------------------------------------------------+-------------------+
|
v (Output Instan)
+---------------------------------------------------+-------------------+
|                            LOKAL STORAGE / UI PLAYBACK                |
|  6. File .mp4 Siap di Folder Downloads & Tersedia di UI Player        |
+-----------------------------------------------------------------------+

### Rahasia Kecepatan Engine:
* **Fast Seeking:** Parameter `-ss` diletakkan **sebelum** `-i` sehingga FFmpeg langsung melompat ke timestamp tujuan tanpa membaca video dari awal.
* **Stream Copy (`-c:v copy`):** Bitstream video dan audio langsung disalin mentah-mentah (*demuxing & remuxing*) tanpa proses rendering ulang, menghemat 100% resource CPU.

---

## 2. Langkah Instalasi (Khusus macOS / M1 Architecture)

Buka Terminal Anda dan jalankan perintah berikut secara berurutan untuk menyiapkan environment proyek[cite: 1]:

```bash
# 1. Install dependencies utama via Homebrew
brew install python ffmpeg

# 2. Buat folder project dan siapkan Virtual Environment
mkdir video-clipper-local && cd video-clipper-local
python3 -m venv venv
source venv/bin/activate

# 3. Install Python libraries yang dibutuhkan
pip install --upgrade pip
pip install streamlit yt-dlp