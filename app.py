import streamlit as st
import subprocess
import os
import datetime
import json
import re
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
import urllib.parse
import time

# Konfigurasi Halaman Utama UI
st.set_page_config(
    page_title="YouClip Dashboard",
    page_icon="✂️",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Kustomisasi Gaya Tampilan (CSS UI Modern - Terang)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    /* Gunakan Inter untuk elemen dasar, tapi JANGAN pada div/span bawaan Streamlit agar tidak merusak komponen internal */
    html, body, p, h1, h2, h3, h4, h5, h6, input, button, select, textarea, label, li { 
        font-family: 'Inter', sans-serif; 
        color: #1e293b;
    }
    
    /* Perlindungan khusus untuk Material Icons bawaan Streamlit agar tidak berubah jadi teks */
    .material-symbols-rounded, .material-symbols-outlined, [class*="icon"], [class*="stIcon"] {
        font-family: 'Material Symbols Rounded' !important;
    }
    
    .stApp { background-color: #f8f9fa !important; }
    
    /* Hide Default Streamlit Deploy Button only */
    .stDeployButton { display: none !important; }
    
    /* Menu Item Custom CSS (For any remaining HTML menus) */
    .menu-item {
        display: flex; align-items: center; gap: 12px; padding: 12px 20px; 
        border-radius: 8px; margin: 4px 16px; cursor: pointer;
        color: #475569; font-weight: 500; font-size: 0.95rem; text-decoration: none;
        transition: all 0.2s ease;
    }
    .menu-item.active { background-color: #f1f5f9; color: #0f172a; font-weight: 600; }
    .menu-item:hover:not(.active) { background-color: #f8fafc; }
    
    /* Buttons */
    div[data-testid="stButton"] > button { 
        width: 100% !important; 
        border-radius: 8px !important; 
        font-weight: 600 !important; 
        height: auto !important;
        min-height: 42px !important;
    }
    
    /* Primary Buttons */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #6366f1 !important; 
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 6px -1px rgba(99, 102, 241, 0.2) !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background-color: #4f46e5 !important;
        box-shadow: 0 6px 8px -1px rgba(99, 102, 241, 0.3) !important;
    }
    
    /* Secondary/Ghost Buttons */
    div[data-testid="stButton"] > button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background-color: #f8fafc !important;
        border-color: #94a3b8 !important;
    }
    
    /* Tertiary (Sidebar Menu) Buttons */
    div[data-testid="stSidebar"] {
        width: 260px !important;
    }
    div[data-testid="stSidebar"] div.row-widget.stButton {
        padding-bottom: 0px !important;
    }
    div[data-testid="stButton"] > button[kind="tertiary"] {
        background-color: transparent !important;
        color: #475569 !important;
        border: none !important;
        box-shadow: none !important;
        justify-content: flex-start !important;
        padding: 8px 16px !important;
        margin-bottom: 2px !important;
    }
    div[data-testid="stButton"] > button[kind="tertiary"]:hover {
        background-color: #f1f5f9 !important;
        color: #0f172a !important;
    }
    div[data-testid="stButton"] > button[kind="tertiary"] p {
        font-size: 0.95rem !important;
        font-weight: 500 !important;
    }
    
    /* Inputs */
    div[data-testid="stTextInput"] input, div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        border-radius: 8px !important;
        border: 1px solid #cbd5e1 !important;
        background-color: #ffffff !important;
        color: #0f172a !important;
        padding: 4px 12px !important;
        font-size: 0.95rem !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
        min-height: 42px !important;
    }
    
    /* Custom Card Style (Containers) */
    [data-testid="stVerticalBlockBorderWrapper"], .st-emotion-cache-1jicfl2, div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important;
        background-color: #ffffff !important; 
        border: 1px solid #cbd5e1 !important;
        padding: 1.5rem !important;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.08) !important;
        margin-bottom: 20px !important;
    }
    
    /* Top Header Profile Box */
    .header-box {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 15px;
        padding: 10px 0 20px 0;
        margin-bottom: 20px;
    }
    .kredit-badge {
        background-color: #ffffff;
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        color: #475569;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .profile-box {
        display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 0.9rem; cursor: pointer; color: #0f172a;
    }
    
    /* Perbaikan Expander */
    .streamlit-expanderHeader {
        font-weight: 600 !important;
        color: #334155 !important;
    }
    </style>
""", unsafe_allow_html=True)

# INISIALISASI STATE
if 'current_page' not in st.session_state: st.session_state.current_page = 1
if 'video_info' not in st.session_state: st.session_state.video_info = None
if 'video_url' not in st.session_state: st.session_state.video_url = ""
if 'ai_clips' not in st.session_state: st.session_state.ai_clips = None
if 'ai_updated' not in st.session_state: st.session_state.ai_updated = False
if 'processed_clips' not in st.session_state: st.session_state.processed_clips = []
if 'ui_version' not in st.session_state: st.session_state.ui_version = 0
if 'clip_configs_saved' not in st.session_state: st.session_state.clip_configs_saved = []

def go_to_page(page):
    st.session_state.current_page = page

# ==========================================================
# UI COMPONENTS: SIDEBAR & HEADER
# ==========================================================
with st.sidebar:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 30px; padding: 0 16px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><line x1="20" y1="4" x2="8.12" y2="15.88"></line><line x1="14.47" y1="14.48" x2="20" y2="20"></line><line x1="8.12" y1="8.12" x2="12" y2="12"></line></svg>
            <span style="font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px;">YouClip</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Custom Sidebar Navigation (Clickable)
    if st.button("🏠 Beranda", type="tertiary", use_container_width=True):
        go_to_page(1)
        st.rerun()
        
    if st.button("💳 Pembayaran", type="tertiary", use_container_width=True):
        go_to_page(2)
        st.rerun()
        
    if st.button("🛟 Bantuan", type="tertiary", use_container_width=True):
        go_to_page(3)
        st.rerun()

# Top Header Profile
st.markdown("""
    <div class="header-box">
        <div class="kredit-badge">Kredit 0</div>
        <div class="profile-box">
            <img src="https://ui-avatars.com/api/?name=Anton&background=4f46e5&color=fff&rounded=true&size=32" width="32" height="32" style="border-radius:50%;">
            <span>Anton</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
        </div>
    </div>
""", unsafe_allow_html=True)


def get_ytdlp_base_cmd(client="tv_embedded,ios,android,web"):
    cookie_flag = ""
    try:
        if "YOUTUBE_COOKIES" in st.secrets and st.secrets["YOUTUBE_COOKIES"]:
            import tempfile
            cookie_path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
            with open(cookie_path, "w", encoding="utf-8") as f:
                f.write(st.secrets["YOUTUBE_COOKIES"].strip())
            cookie_flag = f'--cookies "{cookie_path}" '
        elif os.path.exists("cookies.txt"):
            cookie_flag = '--cookies "cookies.txt" '
    except Exception:
        pass
    return f'yt-dlp {cookie_flag}--js-runtimes nodejs --extractor-args "youtube:player_client={client}" --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" '


def load_metadata(url):
    clients = ["ios,android,web", "android,web", "web_creator,android", "mweb"]
    last_err = ""
    for cl in clients:
        try:
            base = get_ytdlp_base_cmd(cl)
            cmd_meta = f'{base}--print "title,duration" "{url}"'
            proc = subprocess.Popen(cmd_meta, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            
            if proc.returncode == 0:
                meta_output = stdout.decode('utf-8', errors='ignore').strip().split('\n')
                if len(meta_output) >= 2:
                    st.session_state.video_info = {
                        'url': url,
                        'title': meta_output[0],
                        'duration': int(meta_output[1])
                    }
                    return True, ""
            last_err = stderr.decode('utf-8', errors='ignore')
        except Exception as e:
            last_err = str(e)
    return False, last_err


@st.dialog("✂️ Editor Segmen Crop Dinamis")
def manual_crop_dialog(idx, _clip_data):
    # Selalu ambil data terbaru dari session_state agar st.video ter-update setelah render
    clip_data = st.session_state.processed_clips[idx]
    
    st.write(f"Edit manual posisi video untuk **{clip_data['out']}**")
    
    target_raw = clip_data.get('raw_path', '')
    if not target_raw or not os.path.exists(target_raw):
        st.error("File mentah tidak ditemukan. Edit manual gagal.")
        return

    # Calculate duration
    import cv2
    import cv2
    vcap = cv2.VideoCapture(os.path.abspath(target_raw))
    fps = vcap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(vcap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = max(1, int(total_frames / fps))
    iw = 1920
    ih = 1080
    if vcap.isOpened():
        iw = int(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ih = int(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    state_key = f"fixes_{idx}"
    if state_key not in st.session_state:
        st.session_state[state_key] = []
        
    fixes = st.session_state[state_key]
    
    st.markdown("### 🛠️ Alat Penambal")
    st.caption("Samakan detik di bawah dengan posisi video di atas, lalu atur posisi kotak siluetnya.")
    
    st.markdown("<div style='font-size: 0.8rem; margin-bottom: 5px; color:#8b949e;'>Titik Detik Kebocoran (Samakan dengan garis waktu video)</div>", unsafe_allow_html=True)
    t_start = st.slider("Titik Waktu", 0, duration, 0, key=f"ts_{idx}", label_visibility="collapsed")
    
    # Hitung posisi aktual video pada t_start agar slider sinkron
    current_pos = 50
    target_w = int(ih * 9 / 16)
    max_x = max(0, iw - target_w)
    
    if clip_data.get('ai_segments'):
        for s_start, s_end, crop_px in clip_data['ai_segments']:
            if s_start <= t_start <= s_end:
                pos_pct = int((crop_px / max_x) * 100) if max_x > 0 else 50
                current_pos = max(0, min(100, pos_pct))
                
    for f in fixes:
        if f['start'] <= t_start <= f['end']:
            current_pos = f['pos']
    
    col1, col2 = st.columns([1.5, 2.5])
    with col1:
        t_dur = st.number_input("Terapkan Tambalan Selama (Detik):", min_value=1, max_value=duration, value=1, key=f"tdur_{idx}")
        t_end = min(duration, t_start + t_dur - 1)
    with col2:
        st.markdown("<div style='font-size: 0.8rem; margin-bottom: 5px; color:#8b949e;'>Geser Posisi Kotak (0=Kiri, 100=Kanan)</div>", unsafe_allow_html=True)
        t_pos = st.slider("Posisi", 0, 100, value=current_pos, label_visibility="collapsed")
        
    # Mini Preview (Gunakan POS_MSEC agar lebih akurat dengan potongan FFmpeg)
    vcap.set(cv2.CAP_PROP_POS_MSEC, int(t_start * 1000))
    ret, frame = vcap.read()
    if ret:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        target_w = int(ih * 9 / 16)
        max_x = max(0, iw - target_w)
        crop_x = int((t_pos / 100.0) * max_x)
        
        preview_img = frame_rgb.copy()
        overlay = preview_img.copy()
        cv2.rectangle(overlay, (0, 0), (crop_x, ih), (0, 0, 0), -1)
        cv2.rectangle(overlay, (crop_x + target_w, 0), (iw, ih), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, preview_img, 0.3, 0, preview_img)
        cv2.rectangle(preview_img, (crop_x, 0), (crop_x + target_w, ih), (255, 255, 255), 4)
        st.image(preview_img, caption=f"Panduan kotak di detik awal ({t_start})", use_container_width=True)
    vcap.release()
    
    if st.button("🚀 Terapkan Penambalan Ini ke Video", type="primary", use_container_width=True):
        if t_start > t_end:
            st.error("Waktu mulai harus lebih kecil atau sama dengan waktu akhir.")
        else:
            fixes.append({'start': t_start, 'end': t_end, 'pos': t_pos})
            # st.rerun() dihapus agar tidak langsung close form

    st.markdown("---")
    st.markdown("### 📜 Riwayat Penambalan")
    st.caption("Daftar tambalan yang sudah Anda terapkan. Di luar detik-detik ini, kamera kembali mengikuti AI.")
    
    if not fixes:
        st.info("Belum ada penambalan manual yang diterapkan.")
    else:
        for i, f in enumerate(fixes):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**Tambalan {i+1}:** Detik {f['start']} s/d {f['end']} ➡️ **Posisi {f['pos']}%**")
            with c2:
                if st.button("Hapus", key=f"del_{idx}_{i}"):
                    fixes.pop(i)
                    
        if st.button("🗑️ Hapus Semua Penambalan", use_container_width=True):
            st.session_state[state_key] = []

    st.markdown("---")
    if st.button("💾 Simpan Perubahan", type="primary", use_container_width=True):
        with st.spinner("Merender ulang video dengan penambalan terbaru... Mohon tunggu..."):
            try:
                target_w = int(ih * 9 / 16)
                max_x = max(0, iw - target_w)
                positions = [50] * (duration + 1)
                
                if clip_data.get('ai_segments'):
                    for s_start, s_end, crop_px in clip_data['ai_segments']:
                        pos_pct = int((crop_px / max_x) * 100) if max_x > 0 else 50
                        pos_pct = max(0, min(100, pos_pct))
                        for t in range(s_start, min(s_end + 1, duration + 1)):
                            positions[t] = pos_pct
                            
                for f in fixes:
                    for t in range(f['start'], min(f['end'] + 1, duration + 1)):
                        positions[t] = f['pos']
                
                blocks = []
                curr_start = 0
                curr_pos = positions[0]
                for t in range(1, duration + 1):
                    if positions[t] != curr_pos:
                        blocks.append({'start': curr_start, 'end': t - 1, 'pos': curr_pos})
                        curr_start = t
                        curr_pos = positions[t]
                blocks.append({'start': curr_start, 'end': duration, 'pos': curr_pos})
                
                expr = str(int((blocks[-1]['pos'] / 100.0) * max_x))
                for b in reversed(blocks[:-1]):
                    px = int((b['pos'] / 100.0) * max_x)
                    expr = f"if(lt(t,{b['end']+1}),{px},{expr})"
                    
                filter_complex = f"[0:v]crop={target_w}:ih:'{expr}':0,scale=1080:1920,setsar=1"
                import time
                new_target = target_raw.replace('.mp4', f'_916_edit_{int(time.time())}.mp4')
                cmd_ffmpeg = ['ffmpeg', '-y', '-i', target_raw, '-vf', filter_complex, '-c:v', 'h264_videotoolbox', '-b:v', '3M', '-c:a', 'copy', new_target]
                proc_ff = subprocess.run(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if proc_ff.returncode == 0 and os.path.exists(new_target):
                    old_target = clip_data['path']
                    if old_target and old_target != target_raw and os.path.exists(old_target):
                        try: os.remove(old_target)
                        except: pass
                    clip_data['path'] = new_target
                    
                    # Force Streamlit to recognize state mutation by reassigning the list
                    clips = st.session_state.processed_clips
                    clips[idx] = clip_data
                    st.session_state.processed_clips = clips
                    
                    st.rerun() # Menutup dialog dan refresh app
                else:
                    st.error("Gagal merender video.")
            except Exception as e:
                st.error(f"Error render: {e}")



# ==========================================================
# PAGE 1: SUMBER VIDEO (BERANDA)
# ==========================================================
if st.session_state.current_page == 1:
    
    with st.container(border=True):
        st.markdown("<h4 style='margin-bottom: 5px;'>Link YouTube</h4>", unsafe_allow_html=True)
        st.markdown("<p style='color: #475569; font-size: 0.9rem; margin-bottom: 15px;'>Durasi video sumber: 5 menit sampai 120 menit.</p>", unsafe_allow_html=True)
        
        url_input = st.text_input("URL", placeholder="https://www.youtube.com/watch?v=...", value=st.session_state.video_url, label_visibility="collapsed")
        
        if st.button("Proses Klip", type="primary"):
            if url_input:
                with st.spinner("Memuat data video..."):
                    st.session_state.video_url = url_input
                    success, err = load_metadata(url_input)
                    if success:
                        go_to_page(99)
                        st.rerun()
                    else:
                        st.error(f"Gagal memuat video: {err}")
            else:
                st.warning("Masukkan URL terlebih dahulu.")
                
        with st.expander("ℹ️ Informasi tambahan"):
            st.markdown("<p style='font-size: 0.9rem; color: #475569;'>Video yang diproses akan memakan kredit sesuai durasi hasil akhir.</p>", unsafe_allow_html=True)
                
    if 'trending_data' not in st.session_state:
        st.session_state.trending_data = {}
        
    with st.expander("🔥 Cari Video Trending (Opsional)"):
        if st.button("🔄 Cari Daftar Trending Sekarang", use_container_width=True) or st.session_state.trending_data:
            if not st.session_state.trending_data:
                with st.spinner("Mengambil tren terbaru dari YouTube..."):
                    try:
                        categories = {
                            "💰 Podcast Keuangan, Bisnis & Investasi": ("podcast investasi keuangan saham bisnis umkm indonesia", 25),
                            "🧠 Podcast Pengembangan Diri & Psikologi": ("podcast motivasi karir pengembangan diri mental health indonesia", 25),
                            "🧬 Podcast Edukasi, Sains & Sejarah": ("podcast edukasi sains sejarah filsafat indonesia", 25),
                            "🔥 Podcast Hiburan & Pop Culture": ("podcast hiburan komedi pop culture indonesia", 25),
                            "🛠️ Oddly Satisfying & Restorasi": ("Oddly Satisfying Restoration", 10),
                            "🏕️ Bushcraft & Outdoor Cooking": ("Bushcraft Outdoor Cooking", 10),
                            "🚶 POV Walk & Atmospheric Ambience": ("POV Walk Atmospheric Ambience", 10),
                            "🍔 Street Food Ekstrem Luar Negeri": ("Extreme Street Food", 10),
                            "🕵️ Rekaman Interogasi & Kasus Kriminal (EWU Style)": ("Police Interrogation True Crime", 10),
                            "🧽 Restorasi Barang Antik & Carpet Cleaning": ("Antique Restoration Carpet Cleaning", 10),
                            "🏕️ Primitive Technology / Survival": ("Primitive Technology Survival", 10),
                            "🎬 Alur Cerita Film Thriller / Survival": ("Movie Recap Thriller Survival", 10)
                        }
                        
                        st.info("Sedang mengambil 100+ video dari YouTube, ini mungkin memakan waktu 10-20 detik...")
                        for cat_name, (query, num) in categories.items():
                            base_cmd = get_ytdlp_base_cmd("ios,web")
                            cmd_search = f'{base_cmd}"ytsearch{num}:{query}" --flat-playlist --print "%(title)s|https://youtube.com/watch?v=%(id)s"'
                            proc = subprocess.Popen(cmd_search, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            stdout, _ = proc.communicate()
                            
                            if proc.returncode == 0:
                                results = stdout.decode('utf-8').strip().split('\n')
                                valid_res = [res for res in results if res and len(res.split('|')) == 2]
                                if valid_res:
                                    st.session_state.trending_data[cat_name] = valid_res
                    except Exception as e:
                        st.error(f"Terjadi kesalahan: {str(e)}")
                        
            # Render dari state agar tidak hilang saat tombol 'Pilih' diklik
            if st.session_state.trending_data:
                for cat_name, results in st.session_state.trending_data.items():
                    st.markdown(f"#### {cat_name}")
                    
                    # Pagination logic
                    page_key = f"page_{cat_name}"
                    if page_key not in st.session_state:
                        st.session_state[page_key] = 0
                        
                    items_per_page = 10
                    total_pages = max(1, (len(results) + items_per_page - 1) // items_per_page)
                    
                    if total_pages > 1:
                        col_prev, col_info, col_next = st.columns([1, 2, 1])
                        with col_prev:
                            if st.button("⬅️ Prev", key=f"prev_{cat_name}"):
                                st.session_state[page_key] = max(0, st.session_state[page_key] - 1)
                                st.rerun()
                        with col_info:
                            st.markdown(f"<div style='text-align:center; padding-top:5px; color:#475569; font-size:0.9rem;'>Halaman {st.session_state[page_key] + 1} dari {total_pages}</div>", unsafe_allow_html=True)
                        with col_next:
                            if st.button("Next ➡️", key=f"next_{cat_name}"):
                                st.session_state[page_key] = min(total_pages - 1, st.session_state[page_key] + 1)
                                st.rerun()
                                
                    start_idx = st.session_state[page_key] * items_per_page
                    end_idx = start_idx + items_per_page
                    current_results = results[start_idx:end_idx]
                    
                    for i, res in enumerate(current_results):
                        idx = start_idx + i
                        parts = res.split('|')
                        with st.container(border=True):
                            st.markdown(f"<p style='font-size:0.85rem; font-weight:600; line-height:1.2; height: 40px; overflow: hidden;'>{parts[0]}</p>", unsafe_allow_html=True)
                            st.video(parts[1])
                            if st.button(f"Pilih Video Ini", key=f"sel_{cat_name}_{idx}", type="primary"):
                                with st.spinner("Memuat data video terpilih..."):
                                    st.session_state.video_url = parts[1]
                                    success, err = load_metadata(parts[1])
                                    if success:
                                        go_to_page(99)
                                        st.rerun()
                                    else:
                                        st.error(f"Gagal memuat video: {err}")
                                        
    # =======================================================
    # DASHBOARD: HASIL KLIP (Rendered below Link YouTube)
    # =======================================================
    if hasattr(st.session_state, 'processed_clips') and st.session_state.processed_clips:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h4 style='margin-bottom: 5px;'>Hasil Klip</h4>", unsafe_allow_html=True)
            st.markdown("<p style='color: #475569; font-size: 0.9rem; margin-bottom: 15px;'>Lihat klip yang sudah jadi dan pantau progress yang sedang diproses.</p>", unsafe_allow_html=True)
            
            for idx, clip in enumerate(st.session_state.processed_clips):
                if clip.get('status') == 'success':
                    vid_url = st.session_state.video_url if st.session_state.video_url else "#"
                    card_html = f"""
                    <div class="result-card">
                        <div style="flex-shrink: 0; width: 240px; height: 135px; background-color: #000; border-radius: 8px; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; color: white;">
                            <span style="font-size: 2rem;">🎬</span>
                            <div style="position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.7); font-size: 0.7rem; padding: 2px 8px; border-radius: 12px; font-weight: 600;">SELESAI</div>
                            <div style="position: absolute; top: 10px; right: 10px; background: rgba(255,255,255,0.9); color: black; font-size: 0.7rem; padding: 2px 8px; border-radius: 12px; font-weight: 600;">AUTO</div>
                        </div>
                        <div style="flex-grow: 1; display: flex; flex-direction: column; justify-content: space-between;">
                            <div>
                                <h4 style="margin: 0 0 5px 0; font-size: 1.1rem; color: #0f172a;">Klip {idx+1}: {clip.get('hook', 'Tanpa Hook')}</h4>
                                <a href="{vid_url}" target="_blank" style="color: #3b82f6; font-size: 0.85rem; text-decoration: none; display: block; margin-bottom: 5px;">{vid_url}</a>
                                <div style="color: #64748b; font-size: 0.8rem; margin-bottom: 10px;">
                                    {datetime.datetime.now().strftime('%d %b %Y, %H.%M')} • Auto • <span style="color: #3b82f6;">● Subtitle</span>
                                </div>
                                <div style="background-color: #f8f9fa; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;">
                                    <div style="font-weight: 600; font-size: 0.85rem; margin-bottom: 2px;">Klip selesai</div>
                                    <div style="font-size: 0.8rem; color: #475569;">Hasil sudah siap. Klik Lihat Klip untuk menonton atau download.</div>
                                </div>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                                <div style="font-size: 0.8rem; color: #64748b;">Selesai dalam 2m 15s</div>
                                <div style="display: flex; gap: 10px; align-items: center;">
                                    <div style="background-color: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; display: flex; align-items: center; gap: 4px;">
                                        <span>✓</span> Selesai
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    if st.button(f"📹 Lihat Klip {idx+1}", key=f"view_dash_{idx}"):
                        go_to_page(3)
                        st.rerun()

# ==========================================================
# PAGE 2: PEMBAYARAN
# ==========================================================
elif st.session_state.current_page == 2:
    col_title, col_btn1, col_btn2 = st.columns([2.5, 1, 1])
    with col_title:
        st.markdown("<h2 style='margin-bottom: 0;'>Top Up Kredit</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; margin-top: 5px;'>Beli paket kredit untuk pemrosesan video YouTube</p>", unsafe_allow_html=True)
    with col_btn1:
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        st.button("Lihat Riwayat Kredit", use_container_width=True)
    with col_btn2:
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        st.button("Lihat Riwayat Pembayaran", use_container_width=True)
        
    with st.container(border=True):
        st.markdown("#### 💳 Saldo Kredit")
        st.markdown("<p style='color: #64748b; margin-top: -10px;'>Saldo kredit Anda saat ini</p>", unsafe_allow_html=True)
        st.markdown("<h1 style='color: #6366f1; margin: 10px 0;'>0 kredit</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; font-size: 0.9em; margin-bottom: 0;'>1 kredit = 1 pemrosesan video YouTube</p>", unsafe_allow_html=True)
        
    st.markdown("<h3 style='margin-bottom: 0; margin-top: 30px;'>Pilih Paket Kredit</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; margin-top: 5px;'>Semua paket dapat digunakan kapan saja</p>", unsafe_allow_html=True)
    
    st.info("Top up paket apa pun membuka antrian prioritas. Saat server ramai, job dari akun yang sudah top up diproses lebih dulu.")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    
    with col_p1:
        with st.container(border=True):
            st.markdown("#### ⚡ Starter")
            st.markdown("<p style='color: #64748b; font-size: 0.85em; margin-top: -10px; height: 35px;'>Untuk pemula yang ingin mencoba</p>", unsafe_allow_html=True)
            st.markdown("<h2 style='margin-bottom: 0;'>Rp25.000</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color: #64748b; font-size: 0.85em; margin-top: 5px;'>10 kredit - Rp2.500/kredit</p>", unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size: 0.85em; line-height: 2; margin-bottom: 20px; color: #475569;">
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> 10 kredit proses video</div>
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> AI potong klip otomatis</div>
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> Antrian prioritas saat server ramai</div>
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> Tidak ada batas waktu</div>
            </div>
            """, unsafe_allow_html=True)
            st.button("Beli Starter", key="btn_starter", use_container_width=True)
            
    with col_p2:
        with st.container(border=True):
            st.markdown("#### 🚀 Creator")
            st.markdown("<p style='color: #64748b; font-size: 0.85em; margin-top: -10px; height: 35px;'>Pilihan populer untuk konten rutin</p>", unsafe_allow_html=True)
            st.markdown("<h2 style='margin-bottom: 0;'>Rp50.000</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color: #64748b; font-size: 0.85em; margin-top: 5px;'>22 kredit - Rp2.270/kredit</p>", unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size: 0.85em; line-height: 2; margin-bottom: 20px; color: #475569;">
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> 22 kredit proses video</div>
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> AI potong klip otomatis</div>
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> Antrian prioritas saat server ramai</div>
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> Tidak ada batas waktu</div>
            </div>
            """, unsafe_allow_html=True)
            st.button("Beli Creator", key="btn_creator", use_container_width=True)
            
    with col_p3:
        with st.container(border=True):
            st.markdown("<div style='background: #6366f1; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.7em; display: inline-block; margin-bottom: 5px;'>★ Best Value</div>", unsafe_allow_html=True)
            st.markdown("<h4 style='margin-top: 0;'>🌟 Pro</h4>", unsafe_allow_html=True)
            st.markdown("<p style='color: #64748b; font-size: 0.85em; margin-top: -10px; height: 35px;'>Value terbaik untuk produksi maksimal</p>", unsafe_allow_html=True)
            st.markdown("<h2 style='margin-bottom: 0;'>Rp99.000</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color: #64748b; font-size: 0.85em; margin-top: 5px;'>60 kredit - Rp1.650/kredit</p>", unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size: 0.85em; line-height: 2; margin-bottom: 20px; color: #475569;">
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> 60 kredit proses video</div>
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> AI potong klip otomatis</div>
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> Antrian prioritas saat server ramai</div>
                <div><span style='color: #6366f1; font-weight: bold;'>✓</span> Tidak ada batas waktu</div>
            </div>
            """, unsafe_allow_html=True)
            st.button("Beli Pro", key="btn_pro", type="primary", use_container_width=True)
# ==========================================================
# PAGE 99: AI HIGHLIGHT FINDER (HIDDEN)
# ==========================================================
elif st.session_state.current_page == 99:
    
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 5px;">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0f172a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line></svg>
            <h2 style="margin: 0; font-size: 2rem; font-weight: 800; color: #0f172a;">Temukan Momen Emas</h2>
        </div>
        <p style='font-size: 1rem; color: #64748b; margin-bottom: 25px;'>Langkah 2: Biarkan AI mencari momen paling viral di video ini.</p>
    """, unsafe_allow_html=True)
    
    info = st.session_state.video_info
    
    # Custom Info Box instead of st.info
    st.markdown(f"""
        <div style="background-color: #e0f2fe; border: 1px solid #bae6fd; border-radius: 8px; padding: 12px 16px; margin-bottom: 25px; color: #0369a1; font-size: 0.9rem;">
            <span style="font-weight: 600;">Video Aktif:</span> {info['title']} <span style="margin: 0 8px; opacity: 0.5;">|</span> <span style="font-weight: 600;">Total Durasi:</span> {datetime.timedelta(seconds=info['duration'])}
        </div>
    """, unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 20px;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                <h3 style="margin: 0; font-size: 1.2rem;">Konfigurasi AI</h3>
            </div>
        """, unsafe_allow_html=True)
        # Load API key configuration
        fokus_ai = st.selectbox("Fokus Pencarian Konten (Topik):", ["🔥 Campur (Yang Paling Menarik & Viral)", "😂 Paling Lucu & Menghibur", "🧠 Paling Edukatif / Fakta Menarik", "😱 Momen Dramatis / Konflik", "😡 Debat / Kontroversial", "💡 Motivasi & Inspirasi", "🍔 Makan / Mukbang", "✂️ Cut Video (Hanya Potong Durasi)"])
        durasi_ai = st.selectbox("Target Durasi per Klip:", ["TikTok/Reels Pendek (15-30 detik)", "TikTok/Reels Standar (30-60 detik)", "Podcast Shorts (1-3 menit)", "Storytelling Panjang (3-5 menit)", "Micro (Bawah 15 detik)", "Fleksibel (Disesuaikan AI)"])
        layout_opts = ["🎯 AI Track Crop (9:16)", "Smart Face Crop (9:16)", "Center Crop (9:16)", "Blur Background (9:16)", "Asli (16:9)"]
        st.selectbox("Format Video Hasil Akhir (Semua Klip):", layout_opts, index=0, key="global_layout")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Tombol Utama
    btn_ai = st.button("✨ Mulai Analisis AI", type="primary", use_container_width=True)
    
    # Tombol Sekunder
    c_back, c_skip = st.columns(2)
    with c_back:
        if st.button("⬅️ Ganti Video", use_container_width=True):
            go_to_page(1)
            st.rerun()
    with c_skip:
        if st.button("⏭️ Lewati AI (Potong Manual)", use_container_width=True):
            go_to_page(3)
            st.rerun()
            
    if btn_ai:
        with st.spinner("Mengekstrak dan menganalisis transkrip dengan AI..."):
                    try:
                        video_url = st.session_state.video_url
                        video_id = video_url.split("v=")[1].split("&")[0] if "v=" in video_url else video_url.split("/")[-1].split("?")[0]
                        api = YouTubeTranscriptApi()
                        transcript_list = api.list(video_id)
                        
                        try:
                            transcript_data = transcript_list.find_transcript(['id', 'en'])
                        except:
                            transcript_data = None
                            for t in transcript_list:
                                transcript_data = t
                                break
                                
                        if transcript_data:
                            if transcript_data.language_code != 'id' and transcript_data.is_translatable:
                                transcript_data = transcript_data.translate('id')
                                
                            fetched_transcript = transcript_data.fetch()
                            text_lines = []
                            for t in fetched_transcript:
                                start = int(t.start)
                                hh, mm, ss = start // 3600, (start % 3600) // 60, start % 60
                                time_str = f"{hh:02d}:{mm:02d}:{ss:02d}"
                                text_lines.append(f"[{time_str}] {t.text}")
                            
                            content_payload = "\n".join(text_lines)[:35000]
                            content_type = "text"
                        else:
                            raise Exception("No transcript available")
                    except Exception as e:
                        st.info("⚠️ Subtitle tidak ditemukan. Mengunduh Audio (membutuhkan waktu tambahan)...")
                        import tempfile
                        tmpdir = tempfile.mkdtemp()
                        audio_path = os.path.join(tmpdir, "audio.m4a")
                        dl_audio_success = False
                        for cl in ["ios,android,web", "android,web", "web_creator", "mweb"]:
                            base_cmd = get_ytdlp_base_cmd(cl)
                            cmd_audio = f'{base_cmd}-f "bestaudio[ext=m4a]/bestaudio/best" -o "{audio_path}" "{st.session_state.video_url}"'
                            subprocess.run(cmd_audio, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
                                dl_audio_success = True
                                break
                        if not dl_audio_success:
                            st.error("Gagal mengunduh audio YouTube (403 Forbidden atau dibatasi). Coba tambahkan YOUTUBE_COOKIES di secrets.")
                            st.stop()
                        content_payload = audio_path
                        content_type = "audio"
                        
                    API_KEYS = []
                    if "GEMINI_API_KEYS" in st.secrets:
                        API_KEYS = list(st.secrets["GEMINI_API_KEYS"])
                    elif "GEMINI_API_KEY" in st.secrets:
                        API_KEYS = [st.secrets["GEMINI_API_KEY"]]
                    elif os.environ.get("GEMINI_API_KEYS"):
                        API_KEYS = [k.strip() for k in os.environ.get("GEMINI_API_KEYS").split(",") if k.strip()]
                    elif os.environ.get("GEMINI_API_KEY"):
                        API_KEYS = [os.environ.get("GEMINI_API_KEY")]
                    
                    if not API_KEYS:
                        st.error("⚠️ API Key Gemini belum dikonfigurasi. Silakan masukkan di .streamlit/secrets.toml atau menu Secrets Streamlit.")
                        st.stop()
                    
                    st.info("Menganalisis konten menggunakan Gemini AI (Load Balancing Mode)...")
                    success_api = False
                    response = None
                    
                    for idx_key, key in enumerate(API_KEYS * 2):
                        real_idx = (idx_key % len(API_KEYS)) + 1
                        try:
                            genai.configure(api_key=key)
                            model = genai.GenerativeModel(
                                'gemini-2.5-flash',
                                generation_config={"response_mime_type": "application/json"}
                            )
                            
                            if content_type == 'audio':
                                st.toast(f"Mengunggah audio menggunakan API Key ke-{real_idx} (Attempt {idx_key+1})...")
                                audio_file = genai.upload_file(path=content_payload)
                                while audio_file.state.name == 'PROCESSING':
                                    time.sleep(2)
                                    audio_file = genai.get_file(audio_file.name)
                                final_payload = audio_file
                            else:
                                final_payload = content_payload
                                
                            prompt = f"""
                            [ROLE & PURPOSE]
                            You are an expert Social Media Content Clipper, Viral Copywriter, and Meta/TikTok Policy Auditor. Your objective is to process video transcripts and automatically generate high-converting, policy-safe Overlay Hooks and Captions.
                            
                            Target Audiens / Topik Utama: {fokus_ai}
                            Durasi: {durasi_ai}. FORMAT WAKTU HARUS HH:MM:SS.
                            {("KHUSUS MUKBANG ASMR & EATING: Fokus UTAMA Anda 100% pada AKTIVITAS FISIK MAKAN (MENYUAP, MENGUNYAH, MENGGIGIT, MENELAN). Penonton ingin melihat proses makan secara nyata, BUKAN hanya orang berbicara. CARA MENCARI: 1) Jika ada tanda suara seperti [suara mengunyah], [slurp], [kriuk] di transkrip, pastikan itu dimasukkan penuh. 2) Segera setelah kata 'Mari makan', 'Bismillah', 'Suapan', atau 'Enak banget', PASTI ada adegan menyuap & mengunyah yang panjang. Ambil momen tersebut secara full! 3) Jeda atau keheningan dalam transkrip saat membahas makanan biasanya adalah momen mereka sibuk mengunyah. Klip HARUS dimulai tepat SEBELUM sendok/tangan masuk ke mulut (proses menyuap), menampilkan proses MENGUNYAH secara UTUH tanpa terpotong (bisa 20-40 detik), dan baru berakhir setelah mereka selesai menelan. HIGHLIGHT proses MENGUNYAH dan MENYUAP ini sedetail mungkin! Kumpulkan klip-klip ini agar total durasi gabungan mencapai minimal 1-2 menit." if "Makan" in fokus_ai else ("KHUSUS CUT VIDEO: Tugas Anda adalah memotong SEMUA isi video/pembahasan yang berbobot menjadi klip-klip panjang berdurasi masing-masing 1 hingga 3 menit. KELUARKAN SEMUA POTONGAN YANG ADA (keluarkan sebanyak mungkin klip, bisa 10 hingga 30 klip)! Jangan hanya beri 1 atau 2 klip. Pastikan setiap klip berdurasi 1-3 menit penuh dan merupakan pembahasan yang utuh." if "Cut Video" in fokus_ai else "Temukan MAKSIMAL 5 KLIP TERBAIK berpotensi viral."))}
                            Berikan Skor Keviralan (virality_score) dalam rentang 1.0 hingga 10.0 dan jelaskan alasannya secara singkat (viral_reason).

                            ### RULE 1: SENSITIVE WORD OBFUSCATION MATRIX (ANTI-SENSOR)
                            You MUST automatically apply "Text Camouflage" (leetspeak/pelesetan) whenever the input contains risky topics:
                            1. VIOLENCE & GRAPHIC CONTENT: "Mati"->"M4t1", "Digorok"->"D1gor0k", "Darah"->"D4r4h", "Bunuh"->"Bvnvh", "Pembunuhan"->"Tr4g3d1".
                            2. MYSTICISM, SCAMS & SPAM: "Pesugihan"->"P3su91h4n", "Kuncen"->"Kunc3n", "Dukun"->"Dvkvn", "Penipuan"->"P3n1pv4n".
                            3. MEDICAL & SENSITIVE ISSUES: "COVID"/"Vaksin" -> "Pandemi masa lalu".
                            4. CRIME & ILLEGAL ACTIVITIES: "Judi"->"Jvd1", "Pinjol"->"P1nj0l", "Korupsi"->"K0rvps1".

                            ### RULE 2: HOOK OVERLAY TEXT RULES (TEKS DALAM VIDEO)
                            1. LENGTH: Maximum 3 to 6 words.
                            2. STYLE: ALL CAPS for maximum visual intensity.
                            3. EMOJI: End with 1 or 2 high-emotion emojis (😱, 🚨, 🤯, 🔥).
                            4. COMPLIANCE: Always apply Rule 1 (Obfuscation) to any sensitive words.

                            ### RULE 3: DESKRIPSI & CAPTION RULES
                            1. DESKRIPSI (Teks Panjang dalam Video): Buat deskripsi menarik yang menceritakan isi klip dengan detail, dirancang untuk diletakkan di dalam layar video (panjang 1-2 kalimat).
                            2. CAPTION (Untuk Social Media): Buat caption pendek untuk postingan. Panjang MAKSIMAL 100 karakter. Sertakan MAKSIMAL 6 hashtag di dalamnya.
                            
                            PENTING UNTUK JSON: 
                            - PASTIKAN 100% VALID JSON.
                            - HINDARI penggunaan karakter baris baru (Enter/Newline) mentah di dalam value string, selalu gunakan '\\n'.
                            - HINDARI penggunaan tanda kutip ganda di dalam value string kecuali sudah di-escape (\\\").

                            Kembalikan HANYA format JSON array valid dengan struktur persis seperti berikut:
                            [ {{"start": "00:01:20", "end": "00:02:10", "name": "clip_1.mp4", "hook": "BONGKAR TAKTIK KUNC3N! 🚨", "deskripsi": "Ternyata nama artis sengaja diseret-seret untuk menarik minat publik. Cuma demi konten atau emang beneran terjadi? 🤔🔥", "caption": "Bongkar taktik kunc3n! Cuma demi konten? 👇\\n#kontroversi #podcast", "virality_score": 9.8, "viral_reason": "Momen ini memicu rasa penasaran penonton tinggi...", "risk_assessment": "MEDIUM (Mitigated via Camouflage)"}} ]
                            """
                            transkrip_txt = ('Transkrip:\\n' + final_payload) if content_type == 'text' else ''
                            prompt += f"{transkrip_txt}\\n"
                            
                            if content_type == 'text':
                                response = model.generate_content(prompt)
                            else:
                                response = model.generate_content([prompt, final_payload])
                                
                            success_api = True
                            break
                        except Exception as ai_e:
                            err_msg = str(ai_e).lower()
                            if idx_key < len(API_KEYS * 2) - 1:
                                if "429" in err_msg or "quota" in err_msg or "exhausted" in err_msg:
                                    if (idx_key + 1) == len(API_KEYS):
                                        st.warning("⏳ Putaran pertama API Key habis (Limit RPM). Otomatis menunggu 25 detik untuk me-reset kuota Google...")
                                        time.sleep(25)
                                    else:
                                        next_idx = ((idx_key + 1) % len(API_KEYS)) + 1
                                        st.toast(f"⚠️ Limit RPM di AI {real_idx}. Beralih ke AI {next_idx}...")
                                        time.sleep(2.5)
                                else:
                                    st.toast(f"⚠️ Error di AI {real_idx}. Beralih...")
                                    time.sleep(1)
                            continue
                            
                    if not success_api or not response:
                        st.error("❌ Semua API Key (12 buah) telah mencapai batas limit (Rate Limited) atau mengalami gangguan. Harap coba beberapa saat lagi!")
                    else:
                        clean_text = response.text.replace('```json', '').replace('```', '').strip()
                        json_str = re.search(r'\[.*\]', clean_text, re.DOTALL)
                        try:
                            if json_str:
                                st.session_state.ai_clips = json.loads(json_str.group())
                            else:
                                st.session_state.ai_clips = json.loads(clean_text)
                                
                            def to_s(t_str):
                                try:
                                    parts = list(map(int, str(t_str).split(':')))
                                    if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
                                    if len(parts) == 2: return parts[0]*60 + parts[1]
                                    return int(t_str)
                                except: return 0

                            max_dur = st.session_state.video_info['duration']
                            auto_configs = []
                            for i, c in enumerate(st.session_state.ai_clips):
                                d_name = c.get("name", f"clip_{i+1}.mp4")
                                d_caption = c.get("caption", "")
                                d_hook = c.get("hook", "")
                                d_deskripsi = c.get("deskripsi", "")
                                d_deskripsi = c.get("deskripsi", "")
                                d_score = str(c.get("virality_score", "8.0"))
                                d_reason = c.get("viral_reason", "")
                                
                                start_ts = to_s(c.get("start", "00:00:00"))
                                end_ts = to_s(c.get("end", "00:00:15"))
                                
                                if start_ts >= max_dur: start_ts = max(0, max_dur - 15)
                                if start_ts < 0: start_ts = 0
                                if end_ts <= start_ts: end_ts = start_ts + 15
                                if end_ts >= max_dur: 
                                    end_ts = max_dur - 1
                                    start_ts = max(0, end_ts - 15)
                                    
                                d_start = f"{start_ts//3600:02d}:{(start_ts%3600)//60:02d}:{start_ts%60:02d}"
                                d_end = f"{end_ts//3600:02d}:{(end_ts%3600)//60:02d}:{end_ts%60:02d}"
                                
                                layout_input = st.session_state.get("global_layout", "Center Crop (9:16)")
                                auto_configs.append((d_start, d_end, d_name, d_caption, d_hook, d_deskripsi, layout_input, d_score, d_reason))
                            
                            st.session_state.clip_configs_saved = auto_configs
                            st.session_state.processed_clips = []
                            go_to_page(4)
                            st.rerun()
                        except json.JSONDecodeError as e:
                            st.error(f"Gagal memproses hasil dari AI (Format tidak valid). Silakan klik tombol 'Mulai Analisis' sekali lagi! Error: {e}")


# ==========================================================
# PAGE 3: PENGATURAN KLIP
# ==========================================================
elif st.session_state.current_page == 3:
    st.title("✂️ Pengaturan Potongan Klip")
    st.markdown("<p style='font-size:1.1rem; color:#8b949e;'>Langkah 3: Tentukan rentang waktu untuk masing-masing klip.</p>", unsafe_allow_html=True)
    
    info = st.session_state.video_info
    max_dur = info['duration']
    
    def to_secs(t_str):
        try:
            parts = list(map(int, str(t_str).split(':')))
            if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
            if len(parts) == 2: return parts[0]*60 + parts[1]
            return int(t_str)
        except: return 0

    if st.session_state.get('ai_updated', False):
        val = len(st.session_state.ai_clips) if st.session_state.ai_clips else 1
        st.session_state.input_num_clips = min(val, 30)
        st.session_state.ui_version += 1
        st.session_state.ai_updated = False
        
    if 'input_num_clips' not in st.session_state:
        st.session_state.input_num_clips = 1
        
    num_clips = st.number_input("Jumlah Klip yang Diinginkan:", min_value=1, max_value=30, key='input_num_clips')
    uv = st.session_state.ui_version
    clip_configs = []
    
    for i in range(num_clips):
        with st.container(border=True):
            st.markdown(f"<h3 style='margin-bottom:0;'>🎬 Klip {i+1}</h3>", unsafe_allow_html=True)
            d_name, d_caption, d_hook, d_deskripsi = f"clip_{i+1}.mp4", "", "", ""
            d_score, d_reason = "8.0", "Momen menarik."
            
            raw_start = "00:01:00"
            raw_end = "00:01:15"
            
            if st.session_state.ai_clips and i < len(st.session_state.ai_clips):
                raw_start = st.session_state.ai_clips[i].get("start", raw_start)
                raw_end = st.session_state.ai_clips[i].get("end", raw_end)
                d_name = st.session_state.ai_clips[i].get("name", d_name)
                d_caption = st.session_state.ai_clips[i].get("caption", "")
                d_hook = st.session_state.ai_clips[i].get("hook", "")
                d_deskripsi = st.session_state.ai_clips[i].get("deskripsi", "")
                d_score = str(st.session_state.ai_clips[i].get("virality_score", "8.0"))
                d_reason = st.session_state.ai_clips[i].get("viral_reason", "")
            
            start_ts = to_secs(raw_start)
            end_ts = to_secs(raw_end)
            
            if start_ts >= max_dur: start_ts = max(0, max_dur - 15)
            if start_ts < 0: start_ts = 0
            
            if end_ts <= start_ts: end_ts = start_ts + 15
            if end_ts >= max_dur: 
                end_ts = max_dur - 1
                start_ts = max(0, end_ts - 15)
                
            d_start = f"{start_ts//3600:02d}:{(start_ts%3600)//60:02d}:{start_ts%60:02d}"
            d_end = f"{end_ts//3600:02d}:{(end_ts%3600)//60:02d}:{end_ts%60:02d}"
                
            c1, c2, c3 = st.columns(3)
            with c1: start_input = st.text_input("Mulai (HH:MM:SS)", value=d_start, key=f"start_{i}_v{uv}")
            with c2: end_input = st.text_input("Selesai (HH:MM:SS)", value=d_end, key=f"end_{i}_v{uv}")
            with c3: output_name = st.text_input("Nama File", value=d_name, key=f"name_{i}_v{uv}")
            
            with st.expander("📝 Pengaturan Tambahan (Opsional)"):
                hook_input = st.text_input("🎯 Hook (Teks Clickbait)", value=d_hook, key=f"hook_{i}_v{uv}")
                deskripsi_input = st.text_area("📝 Deskripsi (Dalam Video)", value=d_deskripsi, key=f"desk_{i}_v{uv}", height=68)
                caption_input = st.text_area("📝 Caption Social Media", value=d_caption, key=f"caption_{i}_v{uv}", height=68)
            
            layout_input = st.session_state.get("global_layout", "Center Crop (9:16)")
            clip_configs.append((start_input, end_input, output_name, caption_input, hook_input, deskripsi_input, layout_input, d_score, d_reason))

    c_back, c_next = st.columns(2)
    with c_back:
        if st.button("⬅️ Kembali ke Tahap AI"):
            go_to_page(99)
            st.rerun()
    with c_next:
        if st.button("🔥 Potong & Ambil Semua Video", type="primary"):
            st.session_state.clip_configs_saved = clip_configs
            st.session_state.processed_clips = [] # Reset output lama
            go_to_page(4)
            st.rerun()


# ==========================================================
# PAGE 4: PROSES ENGINE & HASIL
# ==========================================================
elif st.session_state.current_page == 4:
    st.title("📺 Proses Render & Hasil")
    st.markdown("<p style='font-size:1.1rem; color:#8b949e;'>Langkah 4: Silakan tunggu engine mengunduh dan merender video Anda.</p>", unsafe_allow_html=True)
    
    if st.button("🔄 Selesai & Mulai Baru (Kembali ke Awal)"):
        st.session_state.video_info = None
        st.session_state.video_url = ""
        st.session_state.ai_clips = None
        st.session_state.processed_clips = []
        go_to_page(1)
        st.rerun()
        
    log_box = st.empty()
    clip_placeholders = [st.empty() for _ in range(30)]
    
    def render_clip_ui(idx, clip_data):
        with clip_placeholders[idx].container():
            if clip_data.get("status") == "failed":
                st.error(f"❌ Klip {idx+1} ({clip_data['out']}) Gagal Diproses!\n\nDetail: {clip_data.get('error', 'Unknown Error')}")
                return
                
            try:
                with st.container(border=True):
                    col_vid, col_info = st.columns([1, 2])
                    
                    with col_vid:
                        st.video(clip_data['path'])
                        
                        with open(clip_data['path'], 'rb') as vf:
                            file_basename = os.path.basename(clip_data['path'])
                            
                            import re
                            hook_text = clip_data.get('hook', '')
                            safe_hook = re.sub(r'[^a-zA-Z0-9]', '_', hook_text).strip('_')
                            safe_hook = re.sub(r'_+', '_', safe_hook) # remove multiple underscores
                            dl_filename = f"{safe_hook}.mp4" if safe_hook else clip_data['out']
                            
                            st.download_button(
                                label=f"💾 Download Video", 
                                data=vf.read(), 
                                file_name=dl_filename, 
                                mime="video/mp4", 
                                key=f"dl_btn_{idx}_{file_basename}",
                                use_container_width=True
                            )
                        
                        if st.button("✏️ Edit Crop Manual", key=f"edit_btn_{idx}"):
                            manual_crop_dialog(idx, clip_data)
                            
                    with col_info:
                        st.markdown(f"<h3 style='margin-bottom: 0px;'>✨ Klip {idx+1}</h3>", unsafe_allow_html=True)
                        score = clip_data.get('score', '8.0')
                        st.markdown(f"<h1 style='font-size: 3.5rem; margin-top: -10px; margin-bottom: 5px; color: #60A5FA;'>{score} <span style='font-size: 1rem; color: #94A3B8;'>/ 10 (Virality Score)</span></h1>", unsafe_allow_html=True)
                        
                        if clip_data.get('reason'):
                            st.markdown(f"""
                            <div style='background-color: #1E293B; border-left: 4px solid #3B82F6; padding: 15px; border-radius: 4px; margin-bottom: 15px;'>
                                <span style='color: #FCD34D;'>💡 <strong>Viral Reason:</strong></span> <span style='color: #E2E8F0;'>{clip_data['reason']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        if clip_data.get('hook'): 
                            st.markdown("🎯 **Hook:**")
                            st.code(clip_data['hook'], language=None)
                        if clip_data.get('deskripsi'): 
                            st.markdown("📝 **Deskripsi (Dalam Video):**")
                            st.code(clip_data['deskripsi'], language=None)
                        if clip_data.get('caption'): 
                            st.markdown("📝 **Caption:**")
                            st.code(clip_data['caption'], language=None)
            except Exception as er:
                st.error(f"Gagal memuat preview: {er}")

    def to_seconds(t_str):
        parts = list(map(int, str(t_str).split(':')))
        if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2: return parts[0]*60 + parts[1]
        return int(t_str)
        
    configs = st.session_state.get('clip_configs_saved', [])
    valid_clips = []
    has_error = False
    
    if not st.session_state.processed_clips and configs:
        # TAHAP PROSESING
        for idx, (s, e, out, cap, hk, desk, lay, sc, rsn) in enumerate(configs):
            if not out.endswith('.mp4'):
                out += '.mp4'
            try:
                dur = to_seconds(e) - to_seconds(s)
                if dur <= 0:
                    st.error(f"❌ Waktu selesai Klip {idx+1} harus lebih besar dari waktu mulai!")
                    has_error = True
                else:
                    valid_clips.append((s, e, out, dur, cap, hk, desk, lay, sc, rsn))
            except:
                st.error(f"❌ Format waktu Klip {idx+1} salah!")
                has_error = True
        
        if not has_error:
            try:
                log_box.info("🔄 Step 1: Menyiapkan engine yt-dlp...")
                os.makedirs("downloads", exist_ok=True)
                info = st.session_state.video_info
                from concurrent.futures import ThreadPoolExecutor, as_completed
                from streamlit.runtime.scriptrunner import get_script_run_ctx, add_script_run_ctx
                
                ctx = get_script_run_ctx()
                
                # ── FASE 1: UNDUH SEKUENSIAL (YouTube blokir download paralel) ──
                log_box.info(f"📥 Step 2: Mengunduh {len(valid_clips)} klip secara berurutan...")
                download_results = []  # [(idx, out, target_raw, config_tuple, success)]
                
                for idx, config_tuple in enumerate(valid_clips):
                    s, e, out, dur, cap, hk, desk, lay, sc, rsn = config_tuple
                    with clip_placeholders[idx].container():
                        st.info(f"⏳ **Klip {idx+1} ({out})** - Mengunduh Video Mentah...")
                        st.progress(20)
                    target_raw = os.path.join("downloads", f"raw_{out}")
                    
                    # Retry dengan rotasi client jika terkena 403
                    success_dl = False
                    dl_clients = ["tv_embedded,web_embedded", "ios,mweb", "android,web", "web"]
                    last_dl_err = ""
                    for cl in dl_clients:
                        base_cmd = get_ytdlp_base_cmd(cl)
                        cmd_ytdlp = (
                            f'{base_cmd}'
                            f'-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best" '
                            f'--merge-output-format mp4 --download-sections "*{s}-{e}" '
                            f'--force-overwrites -o "{target_raw}" "{info["url"]}"'
                        )
                        proc_dl = subprocess.run(cmd_ytdlp, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if os.path.exists(target_raw) and os.path.getsize(target_raw) > 1000:
                            success_dl = True
                            break
                        last_dl_err = proc_dl.stderr.decode('utf-8', errors='ignore')
                        time.sleep(1)
                    
                    download_results.append((idx, out, target_raw, config_tuple, success_dl,
                                             last_dl_err if not success_dl else ""))

                # ── FASE 2: RENDER FFmpeg PARALEL (CPU-bound, aman diparalelkan) ──
                def render_clip(dl_result):
                    idx, out, target_raw, config_tuple, success_dl, dl_err = dl_result
                    add_script_run_ctx(ctx=ctx)
                    s, e, out, dur, cap, hk, desk, lay, sc, rsn = config_tuple

                    if not success_dl:
                        clip_data = {"out": out, "status": "failed", "error": dl_err[-500:]}
                        with clip_placeholders[idx].container():
                            st.error(f"❌ Klip {idx+1} Gagal Diunduh (403 atau koneksi gagal)")
                        return (idx, clip_data)

                    final_path = target_raw
                    if lay != "Asli (16:9)":
                        with clip_placeholders[idx].container():
                            st.info(f"⏳ **Klip {idx+1}** - Render & Crop Video...")
                            st.progress(70)
                        target_916 = os.path.join("downloads", out)

                        if lay == "Blur Background (9:16)":
                            filter_complex = "[0:v]split[original][copy];[copy]scale=135:240:force_original_aspect_ratio=increase,crop=135:240,boxblur=5:5,scale=1080:1920,setsar=1[blurred];[original]scale=1080:1920:force_original_aspect_ratio=decrease,setsar=1[scaled];[blurred][scaled]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,setsar=1"
                        elif lay == "Smart Face Crop (9:16)":
                            import cv2
                            best_x = None
                            iw, ih = 1920, 1080
                            try:
                                vcap = cv2.VideoCapture(os.path.abspath(target_raw))
                                if vcap.isOpened():
                                    iw = int(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                    ih = int(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                    total_frames = int(vcap.get(cv2.CAP_PROP_FRAME_COUNT))
                                    all_cx = []
                                    start_f = int(total_frames * 0.20)
                                    end_f = int(total_frames * 0.90)
                                    span = max(end_f - start_f, 1)
                                    sample_frames = [int(start_f + span * i / 8) for i in range(9)]
                                    try:
                                        import mediapipe as mp
                                        from mediapipe.tasks import python as mp_python
                                        from mediapipe.tasks.python import vision as mp_vision
                                        import os as _os
                                        model_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'face_detector.task')
                                        base_opts = mp_python.BaseOptions(model_asset_path=model_path)
                                        det_opts = mp_vision.FaceDetectorOptions(base_options=base_opts, min_detection_confidence=0.25)
                                        detector = mp_vision.FaceDetector.create_from_options(det_opts)
                                        
                                        try:
                                            mp_pose = mp.solutions.pose
                                            pose_detector = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.25)
                                        except:
                                            pose_detector = None
                                            
                                        for f_idx in sample_frames:
                                            vcap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                                            ret, frame = vcap.read()
                                            if not ret:
                                                continue
                                            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                            small_w, small_h = 480, 270
                                            rgb_small = cv2.resize(rgb, (small_w, small_h))
                                            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_small)
                                            res = detector.detect(mp_img)
                                            largest_face_cx = None
                                            if res.detections:
                                                max_area = 0
                                                for det in res.detections:
                                                    bb = det.bounding_box
                                                    area = bb.width * bb.height
                                                    if area > max_area:
                                                        max_area = area
                                                        largest_face_cx = int((bb.origin_x + bb.width / 2.0) * (iw / small_w))
                                            else:
                                                if pose_detector:
                                                    pose_res = pose_detector.process(rgb_small)
                                                    if pose_res.pose_landmarks:
                                                        lms = pose_res.pose_landmarks.landmark
                                                        largest_face_cx = int(sum([lm.x for lm in lms]) / len(lms) * iw)
                                                        
                                            if largest_face_cx is not None:
                                                all_cx.append(largest_face_cx)
                                        detector.close()
                                        if pose_detector:
                                            pose_detector.close()
                                    except Exception:
                                        pass
                                    vcap.release()
                                    if all_cx:
                                        best_x = int(sum(all_cx) / len(all_cx))
                            except: pass
                            if best_x is not None:
                                target_w = ih * 9 / 16
                                crop_x = int(max(0, min(iw - target_w, best_x - target_w / 2)))
                                filter_complex = f"[0:v]crop=ih*9/16:ih:{crop_x}:0,scale=1080:1920,setsar=1"
                            else:
                                filter_complex = "[0:v]crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,setsar=1"
                        elif lay == "🎯 AI Track Crop (9:16)":
                            import cv2
                            iw, ih = 1920, 1080
                            track_positions = {}
                            try:
                                abs_raw = os.path.abspath(target_raw)
                                vcap = cv2.VideoCapture(abs_raw)
                                if not vcap.isOpened() or not vcap.read()[0]:
                                    fixed_raw = abs_raw.replace('.mp4', '_fixed.mp4')
                                    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', abs_raw, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-c:a', 'copy', fixed_raw])
                                    abs_raw = fixed_raw
                                    vcap = cv2.VideoCapture(abs_raw)
                                    
                                if vcap.isOpened():
                                    iw = int(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                    ih = int(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                    fps_vid = vcap.get(cv2.CAP_PROP_FPS) or 25
                                    total_frames = int(vcap.get(cv2.CAP_PROP_FRAME_COUNT))
                                    duration_s = int(total_frames / fps_vid)
                                    crop_w = int(ih * 9 / 16)
                                    try:
                                        from ultralytics import YOLO
                                        import numpy as np
                                        import mediapipe as mp
                                        from mediapipe.tasks import python as mp_python
                                        from mediapipe.tasks.python import vision as mp_vision
                                        
                                        model = YOLO('yolov8n-pose.pt')
                                        base_opts = mp_python.BaseOptions(model_asset_path='face_landmarker.task')
                                        options = mp_vision.FaceLandmarkerOptions(base_options=base_opts, num_faces=5, min_face_detection_confidence=0.3)
                                        landmarker = mp_vision.FaceLandmarker.create_from_options(options)
                                        
                                        for sec in range(duration_s + 1):
                                            # ACTIVE SPEAKER TRACKING: Sample 4 frames within this second
                                            sec_frames = []
                                            for frac in [0.0, 0.25, 0.5, 0.75]:
                                                f_idx = int((sec + frac) * fps_vid)
                                                if f_idx >= total_frames: continue
                                                vcap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                                                ret, frame = vcap.read()
                                                if ret:
                                                    sec_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                                                    
                                            if not sec_frames: continue
                                                
                                            rgb_main = sec_frames[0]
                                            small_w, small_h = 480, 270
                                            rgb_small = cv2.resize(rgb_main, (small_w, small_h))
                                            
                                            # Turunkan conf ke 0.25 agar orang yg pakai topi/menyamping tetap terdeteksi
                                            results = model.predict(rgb_small, classes=[0], conf=0.25, verbose=False)
                                            
                                            if 'all_valid_centers' not in locals():
                                                all_valid_centers = {}
                                            
                                            largest_face_cx = None
                                            person_centers = []
                                            
                                            if len(results) > 0 and len(results[0].boxes) > 0 and results[0].keypoints is not None:
                                                boxes = results[0].boxes.xyxy.cpu().numpy()
                                                kpts = results[0].keypoints.data.cpu().numpy() # [num_people, 17, 3] (x, y, conf)
                                                
                                                valid_areas = []
                                                valid_boxes = []
                                                
                                                for i in range(len(boxes)):
                                                    # Filter objek palsu (minimal tinggi 15%)
                                                    h = boxes[i, 3] - boxes[i, 1]
                                                    if h < (small_h * 0.15):
                                                        continue
                                                        
                                                    person_kpt = kpts[i]
                                                    valid_x = []
                                                    high_conf_count = 0
                                                    for k in range(7):
                                                        if person_kpt[k, 2] > 0.15: # Threshold dasar untuk validasi area wajah/bahu
                                                            valid_x.append(person_kpt[k, 0])
                                                        if person_kpt[k, 2] > 0.3: # HARUS ada minimal 2 titik yang SANGAT jelas (mata/telinga/bahu)
                                                            high_conf_count += 1
                                                            
                                                    # Syarat ketat agar toples/bantal tidak dianggap manusia:
                                                    if len(valid_x) >= 2 and high_conf_count >= 2:
                                                        cx = sum(valid_x) / len(valid_x)
                                                    else:
                                                        # REJECT TOTAL! Ini PASTI benda mati (toples/bantal/sepeda)
                                                        continue
                                                        
                                                    person_centers.append(cx)
                                                    area = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
                                                    valid_areas.append(area)
                                                    valid_boxes.append(boxes[i])
                                                
                                                if len(person_centers) > 0:
                                                    all_valid_centers[sec] = [cx * (iw / small_w) for cx in person_centers]
                                                    min_x = min(person_centers)
                                                    max_x = max(person_centers)
                                                    group_w = max_x - min_x
                                                    
                                                    # Jangan satukan 2 orang kecuali mereka SANGAT berdekatan
                                                    if group_w * (iw / small_w) <= (crop_w * 0.3):
                                                        target_cx_small = (min_x + max_x) / 2.0
                                                    else:
                                                        # ACTIVE SPEAKER DETECTION
                                                        lip_vars = []
                                                        for p_idx in range(len(person_centers)):
                                                            bx = valid_boxes[p_idx]
                                                            sx1 = max(0, int(bx[0] * iw / small_w) - 50)
                                                            sy1 = max(0, int(bx[1] * ih / small_h) - 50)
                                                            sx2 = min(iw, int(bx[2] * iw / small_w) + 50)
                                                            sy2 = min(ih, int(bx[3] * ih / small_h) + 50)
                                                            
                                                            dists = []
                                                            for frm in sec_frames:
                                                                face_crop = frm[sy1:sy2, sx1:sx2]
                                                                if face_crop.shape[0] < 20 or face_crop.shape[1] < 20: continue
                                                                face_crop = np.ascontiguousarray(face_crop)
                                                                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=face_crop)
                                                                fm_res = landmarker.detect(mp_img)
                                                                if hasattr(fm_res, 'face_landmarks') and fm_res.face_landmarks:
                                                                    lms = fm_res.face_landmarks[0]
                                                                    fh = sy2 - sy1
                                                                    dist = abs(lms[13].y * fh - lms[14].y * fh)
                                                                    dists.append(dist)
                                                            
                                                            var = np.var(dists) if len(dists) > 1 else 0.0
                                                            lip_vars.append(var)
                                                            
                                                        max_var_idx = np.argmax(lip_vars)
                                                        largest_idx = np.argmax(valid_areas)
                                                        
                                                        if lip_vars[max_var_idx] > 2.0:
                                                            # Ada pergerakan bibir signifikan (orang ngomong)
                                                            best_idx = max_var_idx
                                                        else:
                                                            # Tidak ada yang jelas ngomong, gunakan hysteresis atau ukuran terbesar
                                                            best_idx = largest_idx
                                                            if 'tracking_cx_small' in locals():
                                                                distances = [abs(cx - tracking_cx_small) for cx in person_centers]
                                                                closest_idx = np.argmin(distances)
                                                                if valid_areas[largest_idx] < valid_areas[closest_idx] * 1.3:
                                                                    best_idx = closest_idx
                                                                    
                                                        target_cx_small = person_centers[best_idx]
                                                        tracking_cx_small = target_cx_small
                                                        
                                                    largest_face_cx = int(target_cx_small * (iw / small_w))
                                                        
                                            if largest_face_cx is not None:
                                                crop_x = int(max(0, min(iw - crop_w, largest_face_cx - crop_w / 2)))
                                                track_positions[sec] = crop_x
                                        landmarker.close()
                                    except Exception as e:
                                        print(f"TRACKING ERROR: {e}")
                                    vcap.release()
                                    
                                    global_safe_cx = None
                                    if 'all_valid_centers' in locals():
                                        all_cx = [cx for centers in all_valid_centers.values() for cx in centers]
                                        if len(all_cx) > 0:
                                            counts, bins = np.histogram(all_cx, bins=10)
                                            dominant_bin = np.argmax(counts)
                                            global_safe_cx = (bins[dominant_bin] + bins[dominant_bin+1]) / 2.0
                                    
                                    if track_positions:
                                        filled = {}
                                        for sec in range(duration_s + 1):
                                            if sec in track_positions:
                                                filled[sec] = track_positions[sec]
                                            else:
                                                nearest = min(track_positions.keys(), key=lambda k: abs(k - sec))
                                                filled[sec] = track_positions[nearest]
                                        
                                        TOLERANCE = iw * 0.10 # 10% toleransi pergerakan
                                        secs = sorted(filled.keys())
                                        segments = []
                                        cur_start = secs[0]
                                        cur_list = [filled[secs[0]]]
                                        cur_avg = cur_list[0]
                                        
                                        for sec in secs[1:]:
                                            pos = filled[sec]
                                            if abs(pos - cur_avg) > TOLERANCE:
                                                segments.append((cur_start, sec - 1, cur_list))
                                                cur_start = sec
                                                cur_list = [pos]
                                                cur_avg = pos
                                            else:
                                                cur_list.append(pos)
                                                cur_avg = sum(cur_list) / len(cur_list)
                                        segments.append((cur_start, secs[-1], cur_list))
                                        
                                        merged = []
                                        for seg in segments:
                                            s_start, s_end, s_lst = seg
                                            if len(merged) > 0 and (s_end - s_start) < 2:
                                                merged[-1][2].extend(s_lst)
                                                merged[-1] = (merged[-1][0], s_end, merged[-1][2])
                                            else:
                                                merged.append(seg)
                                                
                                        final_segments = []
                                        for s_start, s_end, s_lst in merged:
                                            final_segments.append((s_start, s_end, int(sum(s_lst)/len(s_lst))))
                                            
                                        # ================= QC AI CHECK =================
                                        try:
                                            if 'clip_placeholders' in globals() or 'clip_placeholders' in locals():
                                                with clip_placeholders[idx].container():
                                                    st.info("🤖 QC AI: Sedang mengecek kebocoran frame...")
                                            
                                            bocor_count = 0
                                            for idx_seg in range(len(final_segments)):
                                                s_start, s_end, pos = final_segments[idx_seg]
                                                mid_sec = (s_start + s_end) // 2
                                                
                                                if 'all_valid_centers' in locals() and mid_sec in all_valid_centers and len(all_valid_centers[mid_sec]) > 0:
                                                    centers = all_valid_centers[mid_sec]
                                                    is_aman = any(pos - 100 <= cx <= pos + crop_w + 100 for cx in centers)
                                                    if not is_aman:
                                                        bocor_count += 1
                                                        aman_cx = centers[0] 
                                                        new_pos = int(max(0, min(iw - crop_w, aman_cx - crop_w / 2)))
                                                        final_segments[idx_seg] = (s_start, s_end, new_pos)
                                                else:
                                                    if global_safe_cx is not None:
                                                        is_aman = (pos - 100 <= global_safe_cx <= pos + crop_w + 100)
                                                        if not is_aman:
                                                            bocor_count += 1
                                                            new_pos = int(max(0, min(iw - crop_w, global_safe_cx - crop_w / 2)))
                                                            final_segments[idx_seg] = (s_start, s_end, new_pos)
                                                            
                                            if bocor_count > 0:
                                                if 'clip_placeholders' in globals() or 'clip_placeholders' in locals():
                                                    with clip_placeholders[idx].container():
                                                        st.warning(f"⚠️ QC AI: Menemukan {bocor_count} clip bocor! Melakukan Auto-Correction sebelum render...")
                                            else:
                                                if 'clip_placeholders' in globals() or 'clip_placeholders' in locals():
                                                    with clip_placeholders[idx].container():
                                                        st.success("✅ QC AI: Lolos. Tidak ada frame yang bocor!")
                                        except Exception as e:
                                            pass
                                        # ===============================================
                                            
                                        track_positions = final_segments
                                    elif global_safe_cx is not None:
                                        # Jika track_positions kosong (gagal di semua frame), gunakan global safe cx
                                        new_pos = int(max(0, min(iw - crop_w, global_safe_cx - crop_w / 2)))
                                        track_positions = [(0, duration_s, new_pos)]
                            except: pass
                            
                            if track_positions:
                                crop_w = int(ih * 9 / 16)
                                expr = str(track_positions[-1][2])
                                for s_start, s_end, pos in reversed(track_positions[:-1]):
                                    expr = f"if(lt(t,{s_end+1}),{pos},{expr})"
                                filter_complex = f"[0:v]crop={crop_w}:ih:'{expr}':0,scale=1080:1920,setsar=1"
                            else:
                                st.warning("⚠️ AI gagal melacak wajah di video ini. Mungkin karena tidak ada orang atau buram. Secara otomatis menggunakan Center Crop (Tengah).")
                                filter_complex = "[0:v]crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,setsar=1"
                        elif lay == "Center Crop (9:16)":
                            filter_complex = "[0:v]crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,setsar=1"
                        else:
                            # Fallback center crop
                            filter_complex = "[0:v]crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,setsar=1"

                        # --- ASS GENERATION START ---
                        ass_filter = ""
                        try:
                            from faster_whisper import WhisperModel
                            import time
                            
                            # Cache whisper model globally to avoid OOM in ThreadPoolExecutor
                            if 'global_whisper_model' not in globals():
                                global global_whisper_model
                                global_whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
                                
                            model_wh = global_whisper_model
                            ass_filename = os.path.abspath(f"downloads/sub_{out}.ass")
                            
                            segs, _ = model_wh.transcribe(target_raw, beam_size=5, language="id", word_timestamps=True)
                            
                            words_list = []
                            for seg in segs:
                                for w in seg.words:
                                    words_list.append(w)
                                    
                            def format_ass_time(sec):
                                h = int(sec // 3600)
                                m = int((sec % 3600) // 60)
                                s = int(sec % 60)
                                cs = int(round(sec % 1, 2) * 100)
                                return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
                                
                            chunks = []
                            cur_chunk = []
                            for w in words_list:
                                cur_chunk.append(w)
                                if len(cur_chunk) >= 4 or w.word.endswith(('.', '?', '!')):
                                    chunks.append(cur_chunk)
                                    cur_chunk = []
                            if cur_chunk: chunks.append(cur_chunk)
                            
                            ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HookYellow,Titan One,80,&H00FFFFFF,&H000000FF,&H0000FFFF,&H00000000,-1,0,0,0,100,100,0,0,1,18,0,8,40,40,250,1
Style: HookBlack,Titan One,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,8,0,8,40,40,250,1
Style: Sub,Titan One,70,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,10,0,2,40,40,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
                            with open(ass_filename, 'w', encoding='utf-8') as f:
                                f.write(ass_header)
                                if hk and hk.strip():
                                    safe_hook = hk.replace('\n', '\\N')
                                    f.write(f"Dialogue: 0,0:00:00.00,0:10:00.00,HookYellow,,0,0,0,,{safe_hook}\n")
                                    f.write(f"Dialogue: 1,0:00:00.00,0:10:00.00,HookBlack,,0,0,0,,{safe_hook}\n")
                                for chunk in chunks:
                                    for active_idx, active_word in enumerate(chunk):
                                        a_start = format_ass_time(active_word.start)
                                        a_end = format_ass_time(active_word.end)
                                        t_parts = []
                                        for i, w in enumerate(chunk):
                                            safe_word = w.word.strip().upper()
                                            if i == active_idx:
                                                t_parts.append(f"{{\\3c&H0000FF&}}{safe_word}{{\\3c&H000000&}}")
                                            else:
                                                t_parts.append(safe_word)
                                        l_text = " ".join(t_parts)
                                        f.write(f"Dialogue: 2,{a_start},{a_end},Sub,,0,0,0,,{l_text}\n")
                            
                            # Hapus penggunaan absolute path dan single quotes yang membuat FFmpeg bingung
                            # Gunakan relative path yang aman karena tidak mengandung spasi
                            ass_filename_relative = f"downloads/sub_{out}.ass"
                            ass_filter = f",subtitles={ass_filename_relative}:fontsdir=."
                        except Exception as e:
                            st.warning(f"Gagal generate subtitle ASS: {e}")
                            print(f"ASS ERROR: {e}")
                            
                        filter_complex += ass_filter
                        # --- ASS GENERATION END ---

                        import imageio_ffmpeg
                        import time
                        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                        cmd_ffmpeg = [ffmpeg_exe, '-y', '-loglevel', 'error', '-i', target_raw, '-vf', filter_complex, '-c:v', 'h264_videotoolbox', '-b:v', '3M', '-c:a', 'copy', target_916]
                        
                        # Beri jeda sedikit agar file target_raw selesai di-sync oleh sistem file / iCloud
                        time.sleep(2)
                        
                        proc_ff = subprocess.run(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if proc_ff.returncode == 0 and os.path.exists(target_916):
                            final_path = target_916
                        else:
                            err_msg = proc_ff.stderr.decode('utf-8', errors='ignore') if proc_ff.stderr else "Kesalahan ffmpeg crop."
                            clip_data = {"out": out, "status": "failed", "error": err_msg[-500:]}
                            with clip_placeholders[idx].container():
                                st.error(f"❌ Klip {idx+1} Gagal Render")
                            return (idx, clip_data)

                    clip_data = {"out": out, "path": final_path, "raw_path": target_raw if final_path != target_raw else None,
                                 "caption": cap, "hook": hk, "deskripsi": desk, "layout": lay, "status": "success", "score": sc, "reason": rsn,
                                 "ai_segments": track_positions if 'track_positions' in locals() and track_positions else None}
                    with clip_placeholders[idx].container():
                        st.success(f"✅ Klip {idx+1} Selesai Diproses!")
                    return (idx, clip_data)

                log_box.info(f"🚀 Step 3: Render {len(valid_clips)} klip secara PARALEL...")
                with ThreadPoolExecutor(max_workers=len(valid_clips)) as executor:
                    render_futures = [executor.submit(render_clip, dl) for dl in download_results]
                    results = [f.result() for f in as_completed(render_futures)]

                results.sort(key=lambda x: x[0])
                st.session_state.processed_clips = [x[1] for x in results]
                        
                log_box.success("🎉 Semua klip berhasil diproses!")
                st.balloons()
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Gagal memproses: {str(e)}")
    
    # RENDER JIKA SUDAH SELESAI
    if st.session_state.processed_clips:
        for idx, clip in enumerate(st.session_state.processed_clips):
            render_clip_ui(idx, clip)
            
        if len(st.session_state.processed_clips) > 1:
            st.markdown("---")
            st.markdown("### 🔗 Gabungkan Semua Klip")
            st.caption("Gunakan fitur ini jika Anda memotong banyak momen kecil (seperti momen mukbang/makan) dan ingin menggabungkannya menjadi 1 video berurutan.")
            if st.button("🔗 Gabungkan Menjadi 1 Video", type="primary", use_container_width=True):
                with st.spinner("Menggabungkan klip menggunakan FFmpeg..."):
                    import tempfile
                    merge_txt_path = os.path.join("downloads", "merge_list.txt")
                    merge_out_path = os.path.join("downloads", f"merged_video_{int(time.time())}.mp4")
                    
                    # Generate file list for ffmpeg concat
                    has_files = False
                    with open(merge_txt_path, "w") as f:
                        for c in st.session_state.processed_clips:
                            if c.get("status") == "success" and os.path.exists(c["path"]):
                                f.write(f"file '{os.path.basename(c['path'])}'\n")
                                has_files = True
                    
                    if has_files:
                        cmd_merge = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', merge_txt_path, '-c', 'copy', merge_out_path]
                        proc_merge = subprocess.run(cmd_merge, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        if proc_merge.returncode == 0 and os.path.exists(merge_out_path):
                            st.success("✅ Semua klip berhasil digabung menjadi 1 video!")
                            st.video(merge_out_path)
                            with open(merge_out_path, 'rb') as f:
                                st.download_button("💾 Download Video Gabungan", f, file_name=os.path.basename(merge_out_path), mime="video/mp4", use_container_width=True)
                        else:
                            st.error(f"Gagal menggabungkan klip: {proc_merge.stderr.decode('utf-8', errors='ignore')}")
                    else:
                        st.error("Tidak ada klip valid yang bisa digabungkan.")
