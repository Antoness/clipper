import datetime
import html
import os
import tempfile
import time
import warnings

warnings.filterwarnings("ignore", message=".*google.generativeai.*")

import streamlit as st

from engine import highlights as HL
from engine import render as R
from engine import subtitles as SB
from engine import transcript as TR
from engine import youtube as YT
from engine.ffmpeg import encoder_label, ffmpeg_exe, probe, supports_subtitles
from engine.paths import DOWNLOADS_DIR, ensure_dirs, safe_filename

st.set_page_config(page_title="YouClip — AI Video Clipper", page_icon="✂️", layout="wide",
                   initial_sidebar_state="expanded")

# ==========================================================
# DESIGN SYSTEM
# ==========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
:root{
  --bg:#F5F6FB; --surface:#FFFFFF; --ink:#0F172A; --ink2:#334155; --muted:#64748B; --line:#E5E7F0;
  --primary:#5B4CF5; --primary2:#8B5CF6; --primary-soft:#EEECFF; --ok:#10B981; --ok-soft:#E7F8F1;
  --warn:#F59E0B; --hot:#F43F5E; --radius:16px;
}
html, body, p, h1, h2, h3, h4, h5, h6, input, button, select, textarea, label, li {
  font-family:'Plus Jakarta Sans', system-ui, sans-serif;
}
.material-symbols-rounded, .material-symbols-outlined, [class*="icon"], [class*="stIcon"] {
  font-family:'Material Symbols Rounded' !important;
}
.stApp { background:var(--bg) !important; }
.block-container { max-width:1180px; padding-top:1.4rem !important; padding-bottom:4rem !important; }
.stDeployButton { display:none !important; }
h1,h2,h3,h4 { color:var(--ink); letter-spacing:-.02em; }

/* Sidebar */
section[data-testid="stSidebar"] { background:#FFFFFF !important; border-right:1px solid var(--line); }
section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="tertiary"]{
  justify-content:flex-start !important; padding:10px 14px !important; border-radius:12px !important;
  color:var(--ink2) !important; font-weight:600 !important; width:100% !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="tertiary"]:hover{ background:var(--primary-soft) !important; color:var(--primary) !important; }

/* Buttons */
div[data-testid="stButton"] > button, div[data-testid="stDownloadButton"] > button {
  border-radius:12px !important; font-weight:700 !important; min-height:44px !important; transition:all .15s ease;
}
div[data-testid="stButton"] > button[kind="primary"], div[data-testid="stDownloadButton"] > button[kind="primary"]{
  background:linear-gradient(135deg,var(--primary),var(--primary2)) !important; border:none !important; color:#fff !important;
  box-shadow:0 8px 20px -8px rgba(91,76,245,.55) !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover{ transform:translateY(-1px); box-shadow:0 12px 24px -10px rgba(91,76,245,.65) !important; }
div[data-testid="stButton"] > button[kind="secondary"], div[data-testid="stDownloadButton"] > button[kind="secondary"]{
  background:#fff !important; border:1px solid var(--line) !important; color:var(--ink) !important;
}
div[data-testid="stButton"] > button[kind="secondary"]:hover{ border-color:var(--primary) !important; color:var(--primary) !important; }

/* Inputs */
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div, div[data-testid="stNumberInput"] input {
  border-radius:12px !important; border-color:var(--line) !important; background:#fff !important;
}
div[data-testid="stTextInput"] input { min-height:46px; }

/* Cards (container border=True) */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]) {
  border-radius:var(--radius) !important; background:var(--surface) !important; border:1px solid var(--line) !important;
  box-shadow:0 1px 2px rgba(15,23,42,.04), 0 8px 24px -16px rgba(15,23,42,.18) !important;
}
div[data-testid="stExpander"] details { border-radius:14px !important; border:1px solid var(--line) !important; background:#fff; }
div[data-testid="stExpander"] summary p { font-weight:700 !important; color:var(--ink2) !important; }
div[data-testid="stVideo"] video, .stVideo video { border-radius:14px; background:#000; }
div[data-testid="stTabs"] button p { font-weight:700; }

/* Komponen custom */
.yc-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.yc-top .title{font-size:1.65rem;font-weight:800;color:var(--ink);letter-spacing:-.03em}
.yc-top .sub{color:var(--muted);font-size:.95rem;margin-top:2px}
.yc-user{display:flex;gap:10px;align-items:center}
.yc-chip{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;background:#fff;border:1px solid var(--line);
  font-size:.8rem;font-weight:700;color:var(--ink2)}
.yc-chip.ok{background:var(--ok-soft);border-color:#bfeedd;color:#047857}
.yc-chip.pri{background:var(--primary-soft);border-color:#d9d4ff;color:var(--primary)}
.yc-chip.hot{background:#FFE8EC;border-color:#ffc9d3;color:#BE123C}
.yc-steps{display:flex;gap:8px;margin:14px 0 22px 0;flex-wrap:wrap}
.yc-step{flex:1;min-width:140px;display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:14px;background:#fff;border:1px solid var(--line);
  color:var(--muted);font-weight:700;font-size:.85rem}
.yc-step .n{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#F1F2F8;color:var(--muted);font-size:.8rem}
.yc-step.active{border-color:#cfc9ff;background:var(--primary-soft);color:var(--primary)}
.yc-step.active .n{background:var(--primary);color:#fff}
.yc-step.done{color:#047857}.yc-step.done .n{background:var(--ok);color:#fff}
.yc-hero{border-radius:24px;padding:42px 40px 30px 40px;color:#fff;margin-bottom:18px;
  background:radial-gradient(1200px 400px at 10% -10%, rgba(255,255,255,.18), transparent 60%),
             linear-gradient(135deg,#4F46E5 0%,#7C3AED 55%,#DB2777 120%);
  box-shadow:0 24px 50px -28px rgba(79,70,229,.8)}
.yc-hero h1{color:#fff;font-size:2.35rem;line-height:1.12;margin:0 0 10px 0;font-weight:800;letter-spacing:-.035em}
.yc-hero p{color:rgba(255,255,255,.88);font-size:1.05rem;margin:0}
.yc-hero .badges{display:flex;gap:8px;margin-top:18px;flex-wrap:wrap}
.yc-hero .badges span{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);padding:6px 12px;border-radius:999px;font-size:.8rem;font-weight:700}
.yc-feature{padding:4px 2px}
.yc-feature .ic{font-size:1.5rem}
.yc-feature b{display:block;color:var(--ink);margin:6px 0 4px 0}
.yc-feature span{color:var(--muted);font-size:.88rem}
.yc-video{display:flex;gap:16px;align-items:center}
.yc-video img{width:200px;border-radius:12px;aspect-ratio:16/9;object-fit:cover}
.yc-video .t{font-weight:800;color:var(--ink);font-size:1.05rem;line-height:1.3}
.yc-video .m{color:var(--muted);font-size:.85rem;margin-top:6px}
.yc-thumb img{width:100%;border-radius:12px;aspect-ratio:16/9;object-fit:cover}
.yc-thumb .t{font-weight:700;font-size:.85rem;color:var(--ink);line-height:1.3;height:2.6em;overflow:hidden;margin:8px 0 4px 0}
.yc-score{font-size:2rem;font-weight:800;line-height:1;background:linear-gradient(135deg,var(--primary),var(--hot));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.yc-clip-title{font-weight:800;color:var(--ink);font-size:1rem;line-height:1.3;margin:4px 0 6px 0}
.yc-meta{color:var(--muted);font-size:.8rem}
.yc-reason{background:#F8F7FF;border:1px solid #E7E3FF;border-radius:12px;padding:10px 12px;color:var(--ink2);font-size:.85rem;margin:8px 0}
.yc-section{font-weight:800;font-size:1.15rem;color:var(--ink);margin:22px 0 10px 0}
.yc-muted{color:var(--muted);font-size:.9rem}
.yc-dl{display:block;text-align:center;padding:11px 14px;border-radius:12px;font-weight:700;text-decoration:none !important;
  color:#fff !important;background:linear-gradient(135deg,var(--primary),var(--primary2));box-shadow:0 8px 20px -8px rgba(91,76,245,.55);margin:6px 0 8px 0}
.yc-dl:hover{filter:brightness(1.06);transform:translateY(-1px)}
.yc-plan h3{margin:0}.yc-plan .price{font-size:1.9rem;font-weight:800;color:var(--ink);margin:6px 0 0 0}
.yc-plan ul{padding-left:0;list-style:none;color:var(--ink2);font-size:.9rem;line-height:2}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# STATE
# ==========================================================
_DEFAULTS = {
    "current_page": 1, "video_info": None, "video_url": "", "ai_clips": None, "ai_updated": False,
    "processed_clips": [], "ui_version": 0, "clip_configs_saved": [], "transcript": None,
    "trending_data": {}, "style_version": 0,
    "opt_zoom": True, "opt_enhance": True, "opt_remove_silence": False, "opt_second_pass": True,
    "options_saved": {"zoom": True, "enhance": True, "remove_silence": False, "second_pass": True},
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v
# Pulihkan nilai widget toggle dari salinan persisten (Streamlit menghapus state widget saat pindah halaman)
for _k in ("zoom", "enhance", "remove_silence", "second_pass"):
    if f"opt_{_k}" not in st.session_state:
        st.session_state[f"opt_{_k}"] = st.session_state.options_saved[_k]
if "caption_style" not in st.session_state:
    st.session_state.caption_style = SB.make_style()

FOKUS_OPTIONS = ["🔥 Campur (Yang Paling Menarik & Viral)", "😂 Paling Lucu & Menghibur",
                 "🧠 Paling Edukatif / Fakta Menarik", "😱 Momen Dramatis / Konflik", "😡 Debat / Kontroversial",
                 "💡 Motivasi & Inspirasi", "🍔 Makan / Mukbang", "✂️ Cut Video (Hanya Potong Durasi)"]
DURASI_OPTIONS = ["TikTok/Reels Pendek (15-30 detik)", "TikTok/Reels Standar (30-60 detik)",
                  "Podcast Shorts (1-3 menit)", "Storytelling Panjang (3-5 menit)", "Micro (Bawah 15 detik)",
                  "Fleksibel (Disesuaikan AI)"]


def go_to_page(page):
    st.session_state.current_page = page


def secret(name, default=None):
    """Baca st.secrets dengan aman (tidak crash jika secrets.toml tidak ada), fallback ke env."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


def get_api_keys():
    keys = secret("GEMINI_API_KEYS")
    if keys:
        if isinstance(keys, str):
            return [k.strip() for k in keys.split(",") if k.strip()]
        return [k for k in list(keys) if k]
    key = secret("GEMINI_API_KEY")
    return [key] if key else []


YT.set_cookies(secret("YOUTUBE_COOKIES"))
for _name in ("WHISPER_MODEL", "CLIPPER_ENCODER"):
    _val = secret(_name)
    if _val:
        os.environ[_name] = str(_val)
ensure_dirs()

fmt_time = HL.fmt_time
parse_time = HL.parse_time
esc = html.escape


STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PUBLIC_DIR = os.path.join(DOWNLOADS_DIR, "public")   # hanya berisi hardlink klip yang sedang tampil


def _ensure_static_link():
    """`static/` (disajikan Streamlit di /app/static/) -> folder kecil `public/` di folder kerja.
    Streamlit mematikan static serving jika foldernya > 1 GB, jadi video sumber TIDAK boleh ada di sini."""
    try:
        os.makedirs(PUBLIC_DIR, exist_ok=True)
        if os.path.islink(STATIC_DIR) and os.path.realpath(STATIC_DIR) != os.path.realpath(PUBLIC_DIR):
            os.remove(STATIC_DIR)
        if not os.path.exists(STATIC_DIR):
            os.symlink(PUBLIC_DIR, STATIC_DIR, target_is_directory=True)
        return os.path.realpath(STATIC_DIR) == os.path.realpath(PUBLIC_DIR)
    except OSError:
        return False


STATIC_OK = _ensure_static_link() and bool(st.get_option("server.enableStaticServing"))


def _sync_public(keep_paths):
    """Hapus tautan publik yang sudah tidak dipakai agar folder static tetap kecil."""
    keep = {os.path.basename(p) for p in keep_paths if p}
    try:
        for f in os.listdir(PUBLIC_DIR):
            if f not in keep:
                os.remove(os.path.join(PUBLIC_DIR, f))
    except OSError:
        pass


def download_link(path, file_name, label="⬇️ Download HD", key=None):
    """Tombol download andal: link langsung ke file (tidak bergantung sesi & tidak memakan memori).
    Fallback ke st.download_button jika static serving tidak tersedia."""
    if STATIC_OK:
        pub = os.path.join(PUBLIC_DIR, os.path.basename(path))
        try:
            if not os.path.exists(pub):
                try:
                    os.link(path, pub)          # hardlink: tanpa salin, tanpa makan ruang
                except OSError:
                    import shutil
                    shutil.copy2(path, pub)
            from urllib.parse import quote
            st.markdown(f'''<a class="yc-dl" href="app/static/{quote(os.path.basename(pub))}" '''
                        f'''download="{esc(file_name)}">{label}</a>''', unsafe_allow_html=True)
            return
        except OSError:
            pass
    with open(path, "rb") as f:
        st.download_button(label, data=f, file_name=file_name, mime="video/mp4", key=key, type="primary",
                           width="stretch")


def thumb_url(video_id):
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


# ==========================================================
# KOMPONEN UI
# ==========================================================
def page_header(title, subtitle=""):
    st.markdown(f"""
    <div class="yc-top">
      <div><div class="title">{title}</div><div class="sub">{subtitle}</div></div>
      <div class="yc-user">
        <span class="yc-chip pri">⚡ Kredit 0</span>
        <img src="https://ui-avatars.com/api/?name=Anton&background=5B4CF5&color=fff&rounded=true&size=36" width="36" height="36" style="border-radius:50%">
      </div>
    </div>""", unsafe_allow_html=True)


def stepper(active):
    steps = ["Link Video", "Analisis AI", "Atur Potongan", "Render & Hasil"]
    html_steps = []
    for i, name in enumerate(steps, 1):
        cls = "active" if i == active else ("done" if i < active else "")
        mark = "✓" if i < active else str(i)
        html_steps.append(f'<div class="yc-step {cls}"><span class="n">{mark}</span>{name}</div>')
    st.markdown(f'<div class="yc-steps">{"".join(html_steps)}</div>', unsafe_allow_html=True)


def video_card(info):
    tr = st.session_state.transcript
    tr_chip = ""
    if tr and tr.get("video_id") == info["id"]:
        tr_chip = f'<span class="yc-chip ok">📄 Transkrip siap · {esc(tr["source"])}</span>'
    st.markdown(f"""
    <div class="yc-video">
      <img src="{thumb_url(info['id'])}">
      <div>
        <div class="t">{esc(info['title'])}</div>
        <div class="m">⏱️ {datetime.timedelta(seconds=int(info['duration']))} &nbsp;·&nbsp; youtube.com/watch?v={esc(info['id'])}</div>
        <div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">{tr_chip}</div>
      </div>
    </div>""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin:4px 6px 22px 6px">
      <div style="width:36px;height:36px;border-radius:11px;background:linear-gradient(135deg,#5B4CF5,#DB2777);display:flex;align-items:center;justify-content:center;color:#fff;font-size:18px">✂️</div>
      <div><div style="font-size:19px;font-weight:800;color:#0F172A;letter-spacing:-.03em">YouClip</div>
      <div style="font-size:11px;color:#64748B;font-weight:600">AI Video Clipper</div></div>
    </div>""", unsafe_allow_html=True)
    nav = [("🏠  Beranda", 1), ("🎬  Proyek Aktif", 4), ("💳  Pembayaran", 2), ("🛟  Bantuan", 5)]
    for label, page in nav:
        if page == 4 and not (st.session_state.processed_clips or st.session_state.clip_configs_saved):
            continue
        if st.button(label, type="tertiary", width="stretch", key=f"nav_{page}"):
            go_to_page(page)
            st.rerun()
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    n_keys = len(get_api_keys())
    st.markdown(f"""
    <div style="border:1px solid #E5E7F0;border-radius:14px;padding:12px 14px;font-size:.8rem;color:#475569;line-height:1.9">
      <div style="font-weight:800;color:#0F172A;margin-bottom:4px">Status sistem</div>
      {'🟢' if n_keys else '🔴'} Gemini: {n_keys} key<br>
      {'🟢' if supports_subtitles() else '🟠'} Subtitle: {'aktif' if supports_subtitles() else 'tanpa libass'}<br>
      {'🟢' if TR.whisper_available() else '🟠'} Whisper: {'siap' if TR.whisper_available() else 'tidak ada'}
    </div>""", unsafe_allow_html=True)


# ==========================================================
# LOGIKA BERSAMA
# ==========================================================
def _style_reset(preset_key):
    st.session_state.caption_style = SB.make_style(st.session_state[preset_key])
    st.session_state.style_version += 1


def style_editor(prefix):
    """Editor gaya subtitle & hook dengan preview. Hasil disimpan di st.session_state.caption_style."""
    style = st.session_state.caption_style
    v = st.session_state.style_version
    k = lambda name: f"{prefix}_{name}_v{v}"  # noqa: E731
    fonts = list(SB.FONTS)
    col_form, col_prev = st.columns([1.7, 1], gap="large")
    with col_form:
        st.selectbox("Preset gaya", list(SB.PRESETS), key=f"{prefix}_preset", on_change=_style_reset,
                     args=(f"{prefix}_preset",), help="Memilih preset mengisi ulang semua pengaturan.")
        t_sub, t_hook, t_other = st.tabs(["💬 Subtitle", "🎯 Hook (judul)", "➕ Lainnya"])
        with t_sub:
            style["sub_enabled"] = st.toggle("Tampilkan subtitle", value=style["sub_enabled"], key=k("sub_en"))
            c1, c2 = st.columns(2)
            with c1:
                style["sub_mode"] = st.selectbox("Mode", list(SB.SUB_MODES), format_func=SB.SUB_MODES.get,
                                                 index=list(SB.SUB_MODES).index(style["sub_mode"]), key=k("sub_mode"))
                style["sub_font"] = st.selectbox("Font", fonts, index=fonts.index(style["sub_font"]), key=k("sub_font"))
                style["sub_size"] = st.slider("Ukuran", 40, 160, int(style["sub_size"]), key=k("sub_size"))
                style["sub_words"] = st.slider("Kata per baris", 1, 6, int(style["sub_words"]), key=k("sub_words"),
                                               disabled=style["sub_mode"] == "kata")
                style["sub_position"] = st.slider("Posisi (% dari bawah)", 3, 85, int(style["sub_position"]),
                                                  key=k("sub_pos"))
            with c2:
                cc1, cc2, cc3 = st.columns(3)
                style["sub_color"] = cc1.color_picker("Teks", style["sub_color"], key=k("sub_color"))
                style["sub_highlight"] = cc2.color_picker("Sorot", style["sub_highlight"], key=k("sub_hl"))
                style["sub_outline_color"] = cc3.color_picker("Garis", style["sub_outline_color"], key=k("sub_oc"))
                style["sub_outline"] = st.slider("Tebal garis tepi", 0, 16, int(style["sub_outline"]), key=k("sub_ol"))
                style["sub_box"] = st.toggle("Latar kotak", value=style["sub_box"], key=k("sub_box"))
                if style["sub_box"]:
                    bc1, bc2 = st.columns(2)
                    style["sub_box_color"] = bc1.color_picker("Warna kotak", style["sub_box_color"], key=k("sub_bc"))
                    style["sub_box_opacity"] = bc2.slider("Opasitas", 10, 100, int(style["sub_box_opacity"]),
                                                          key=k("sub_bo"))
                style["sub_uppercase"] = st.toggle("HURUF BESAR", value=style["sub_uppercase"], key=k("sub_up"))
                style["sub_animation"] = "pop" if st.toggle("Animasi pop", value=style["sub_animation"] == "pop",
                                                            key=k("sub_anim")) else "none"
        with t_hook:
            style["hook_enabled"] = st.toggle("Tampilkan hook", value=style["hook_enabled"], key=k("hook_en"))
            c1, c2 = st.columns(2)
            with c1:
                style["hook_font"] = st.selectbox("Font hook", fonts, index=fonts.index(style["hook_font"]),
                                                  key=k("hook_font"))
                style["hook_size"] = st.slider("Ukuran hook", 40, 160, int(style["hook_size"]), key=k("hook_size"))
                style["hook_position"] = st.slider("Posisi (% dari atas)", 2, 80, int(style["hook_position"]),
                                                   key=k("hook_pos"))
                style["hook_duration"] = st.slider("Tampil selama (detik, 0 = sepanjang klip)", 0, 15,
                                                   int(style["hook_duration"]), key=k("hook_dur"))
            with c2:
                style["hook_box"] = st.toggle("Gaya label (kotak)", value=style["hook_box"], key=k("hook_box"))
                hc1, hc2 = st.columns(2)
                if style["hook_box"]:
                    style["hook_box_color"] = hc1.color_picker("Kotak", style["hook_box_color"], key=k("hook_bc"))
                    style["hook_text_on_box"] = hc2.color_picker("Teks", style["hook_text_on_box"], key=k("hook_tb"))
                else:
                    style["hook_color"] = hc1.color_picker("Teks", style["hook_color"], key=k("hook_color"))
                    style["hook_glow_color"] = hc2.color_picker("Glow", style["hook_glow_color"], key=k("hook_glow"))
                style["hook_uppercase"] = st.toggle("HURUF BESAR", value=style["hook_uppercase"], key=k("hook_up"))
                style["hook_animation"] = "pop" if st.toggle("Animasi muncul", value=style["hook_animation"] == "pop",
                                                             key=k("hook_anim")) else "none"
        with t_other:
            style["progress_bar"] = st.toggle("Progress bar di bawah video", value=style["progress_bar"], key=k("pb"))
            if style["progress_bar"]:
                style["progress_color"] = st.color_picker("Warna progress bar", style["progress_color"], key=k("pbc"))
    with col_prev:
        st.markdown("<div class='yc-muted' style='margin-bottom:6px'>Preview</div>", unsafe_allow_html=True)
        prev_key = f"{prefix}_preview_img"
        if st.button("👁️ Perbarui Preview", key=f"{prefix}_preview_btn", width="stretch"):
            bg = None
            for c in st.session_state.processed_clips:
                if c.get("raw_path") and os.path.exists(c["raw_path"]):
                    bg = c["raw_path"]
                    break
            if not bg and st.session_state.video_info:
                src = YT.source_path(st.session_state.video_info["id"])
                bg = src if os.path.exists(src) else None
            try:
                out = os.path.join(DOWNLOADS_DIR, f"style_preview_{prefix}_{int(time.time())}.png")
                SB.render_preview(style, out, background=bg)
                st.session_state[prev_key] = out
            except Exception as e:  # noqa: BLE001
                st.error(f"Gagal membuat preview: {e}")
        if st.session_state.get(prev_key) and os.path.exists(st.session_state[prev_key]):
            st.image(st.session_state[prev_key], width="stretch")
        else:
            st.markdown("<div style='aspect-ratio:9/16;border-radius:14px;background:linear-gradient(160deg,#334155,#0F172A);"
                        "display:flex;align-items:center;justify-content:center;color:#94A3B8;font-size:.85rem;text-align:center;padding:20px'>"
                        "Klik <b>&nbsp;Perbarui Preview&nbsp;</b> untuk melihat gaya di video</div>", unsafe_allow_html=True)


def current_options():
    return {
        "subtitles": st.session_state.caption_style.get("sub_enabled", True),
        "style": dict(st.session_state.caption_style),
        "remove_silence": st.session_state.options_saved["remove_silence"],
        "zoom": st.session_state.options_saved["zoom"],
        "enhance": st.session_state.options_saved["enhance"],
    }


def _replace_output(c, new_path, preview):
    for key in ("path", "preview_path"):
        old = c.get(key)
        if old and os.path.exists(old) and old not in (new_path, preview, c.get("raw_path")):
            try:
                os.remove(old)
            except OSError:
                pass
    c["path"], c["preview_path"] = new_path, preview


def restyle_one(idx, hook=None):
    """Render ulang satu klip dengan gaya saat ini (tanpa proses AI/tracking ulang)."""
    clips = st.session_state.processed_clips
    c = clips[idx]
    new_path, ass, style, preview = R.restyle_clip(c, st.session_state.caption_style, hook=hook)
    _replace_output(c, new_path, preview)
    c.update(ass_path=ass, style=style)
    if hook is not None:
        c["hook"] = hook
    clips[idx] = c
    st.session_state.processed_clips = clips


def start_with_url(url):
    """Muat metadata video lalu pindah ke halaman AI."""
    try:
        info = YT.fetch_metadata(url)
    except ValueError as e:
        st.error(str(e))
        return
    except Exception as e:  # noqa: BLE001
        st.error(f"Gagal memuat video: {e}")
        return
    if st.session_state.video_info and st.session_state.video_info.get("id") != info["id"]:
        st.session_state.transcript = None
        st.session_state.ai_clips = None
    st.session_state.video_url = info["url"]
    st.session_state.video_info = info
    go_to_page(99)
    st.rerun()


# ==========================================================
# DIALOG: EDIT CROP MANUAL
# ==========================================================
@st.dialog("✂️ Edit Crop Manual", width="large")
def manual_crop_dialog(idx):
    import cv2

    clip_data = st.session_state.processed_clips[idx]
    target_raw = clip_data.get("raw_path", "")
    if not target_raw or not os.path.exists(target_raw):
        st.error("File mentah tidak ditemukan. Edit manual gagal.")
        return
    info = probe(target_raw)
    iw, ih = info["width"] or 1920, info["height"] or 1080
    duration = max(1, int(info["duration"] or 1))
    target_w = int(ih * 9 / 16)
    max_x = max(0, iw - target_w)
    if max_x == 0:
        st.info("Video ini sudah vertikal, tidak ada yang perlu di-crop.")
        return

    state_key = f"fixes_{idx}"
    if state_key not in st.session_state:
        st.session_state[state_key] = []
    fixes = st.session_state[state_key]

    def ai_pos_at(t):
        for s_start, s_end, crop_px in clip_data.get("ai_segments") or []:
            if s_start <= t < s_end:
                return max(0, min(100, int(crop_px / max_x * 100)))
        return 50

    st.caption("Geser waktu ke bagian yang crop-nya meleset, atur posisi kotak, lalu **Terapkan**. "
               "Di luar tambalan, kamera tetap mengikuti AI.")
    c_prev, c_ctrl = st.columns([1.4, 1], gap="large")
    with c_ctrl:
        t_start = st.slider("Detik", 0, duration, 0, key=f"ts_{idx}")
        current_pos = ai_pos_at(t_start)
        for f in fixes:
            if f["start"] <= t_start <= f["end"]:
                current_pos = f["pos"]
        t_dur = st.number_input("Terapkan selama (detik)", min_value=1, max_value=duration, value=2, key=f"tdur_{idx}")
        t_end = min(duration, t_start + t_dur - 1)
        t_pos = st.slider("Posisi kotak (0 = kiri, 100 = kanan)", 0, 100, value=current_pos, key=f"tpos_{idx}_{t_start}")
        if st.button("➕ Terapkan Tambalan", type="primary", width="stretch"):
            fixes.append({"start": t_start, "end": t_end, "pos": t_pos})
        if fixes:
            st.markdown("**Tambalan:**")
            for i, f in enumerate(list(fixes)):
                a, b = st.columns([4, 1])
                a.markdown(f"<span class='yc-chip'>{f['start']}–{f['end']} dtk → {f['pos']}%</span>", unsafe_allow_html=True)
                if b.button("✕", key=f"del_{idx}_{i}"):
                    fixes.pop(i)
                    st.rerun(scope="fragment")
    with c_prev:
        vcap = cv2.VideoCapture(os.path.abspath(target_raw))
        vcap.set(cv2.CAP_PROP_POS_MSEC, int(t_start * 1000))
        ret, frame = vcap.read()
        vcap.release()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            crop_x = int((t_pos / 100.0) * max_x)
            overlay = frame_rgb.copy()
            cv2.rectangle(overlay, (0, 0), (crop_x, ih), (0, 0, 0), -1)
            cv2.rectangle(overlay, (crop_x + target_w, 0), (iw, ih), (0, 0, 0), -1)
            preview = cv2.addWeighted(overlay, 0.7, frame_rgb, 0.3, 0)
            cv2.rectangle(preview, (crop_x, 0), (crop_x + target_w, ih), (255, 255, 255), 6)
            st.image(preview, caption=f"Detik {t_start}", width="stretch")

    if st.button("💾 Simpan & Render Ulang", type="primary", width="stretch", disabled=not fixes):
        with st.spinner("Merender ulang (subtitle, zoom & warna dipertahankan)..."):
            try:
                positions = [ai_pos_at(t) for t in range(duration + 1)]
                for f in fixes:
                    for t in range(f["start"], min(f["end"] + 1, duration + 1)):
                        positions[t] = f["pos"]
                segments = []
                cur_start, cur_pos = 0, positions[0]
                for t in range(1, duration + 1):
                    if positions[t] != cur_pos:
                        segments.append((float(cur_start), float(t), int(cur_pos / 100 * max_x)))
                        cur_start, cur_pos = t, positions[t]
                segments.append((float(cur_start), float(info["duration"] or duration), int(cur_pos / 100 * max_x)))
                new_path, new_base, new_zooms, preview = R.rerender_with_segments(clip_data, segments)
                _replace_output(clip_data, new_path, preview)
                clip_data.update(ai_segments=segments, base_vf=new_base, zooms=new_zooms, wide_ranges=[])
                clips = st.session_state.processed_clips
                clips[idx] = clip_data
                st.session_state.processed_clips = clips
                st.session_state[state_key] = []
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Gagal merender: {e}")


# ==========================================================
# PAGE 1: BERANDA
# ==========================================================
if st.session_state.current_page == 1:
    page_header("Beranda", "Ubah video YouTube panjang menjadi klip pendek siap viral.")

    st.markdown("""
    <div class="yc-hero">
      <h1>Video panjang → klip viral,<br>otomatis dengan AI.</h1>
      <p>Tempel link YouTube. AI memilih momen terbaik, kamera mengikuti pembicara, subtitle karaoke langsung jadi.</p>
      <div class="badges"><span>🎯 Deteksi pembicara</span><span>🧠 Klimaks tidak terpotong</span>
      <span>💬 Subtitle karaoke</span><span>🎨 8 font & 6 gaya</span></div>
    </div>""", unsafe_allow_html=True)

    with st.container(border=True):
        c_in, c_btn = st.columns([4, 1], vertical_alignment="bottom")
        with c_in:
            url_input = st.text_input("Link YouTube", placeholder="https://www.youtube.com/watch?v=...",
                                      value=st.session_state.video_url)
        with c_btn:
            go = st.button("✨ Proses Klip", type="primary", width="stretch")
        st.markdown("<div class='yc-muted'>Durasi video sumber ideal 5–120 menit. Video publik saja.</div>",
                    unsafe_allow_html=True)
        if go:
            if url_input:
                with st.spinner("Memuat data video..."):
                    start_with_url(url_input)
            else:
                st.warning("Masukkan link YouTube terlebih dahulu.")

    f1, f2, f3, f4 = st.columns(4)
    for col, (ic, t, d) in zip((f1, f2, f3, f4), [
        ("📄", "Baca transkrip penuh", "AI membaca seluruh isi video, bukan cuma judul."),
        ("✂️", "Potong di batas kalimat", "Mulai di awal cerita, berakhir setelah klimaks & reaksi."),
        ("🎯", "Kamera ikut pembicara", "Gerak bibir dicocokkan dengan suara."),
        ("🎨", "Gaya bebas", "Font, warna, posisi subtitle & hook bisa diatur."),
    ]):
        with col:
            with st.container(border=True):
                st.markdown(f"<div class='yc-feature'><div class='ic'>{ic}</div><b>{t}</b><span>{d}</span></div>",
                            unsafe_allow_html=True)

    done = [c for c in st.session_state.processed_clips if c.get("status") == "success"]
    if done:
        st.markdown("<div class='yc-section'>🎬 Klip terakhir</div>", unsafe_allow_html=True)
        with st.container(border=True):
            cols = st.columns(4)
            for i, clip in enumerate(done[:8]):
                with cols[i % 4]:
                    st.markdown(f"<div class='yc-clip-title'>{esc(clip.get('hook') or clip.get('out'))}</div>"
                                f"<div class='yc-meta'>⭐ {clip.get('score', '-')} · {clip.get('duration', 0):.0f} dtk</div>",
                                unsafe_allow_html=True)
            if st.button("Buka Proyek Aktif →", key="view_dash"):
                go_to_page(4)
                st.rerun()

    st.markdown("<div class='yc-section'>🔥 Cari ide video trending</div>", unsafe_allow_html=True)
    categories = {
        "💰 Bisnis": ("podcast investasi keuangan saham bisnis umkm indonesia", 12),
        "🧠 Pengembangan Diri": ("podcast motivasi karir pengembangan diri mental health indonesia", 12),
        "🧬 Edukasi": ("podcast edukasi sains sejarah filsafat indonesia", 12),
        "😂 Hiburan": ("podcast hiburan komedi pop culture indonesia", 12),
        "🛠️ Satisfying": ("Oddly Satisfying Restoration", 8),
        "🍔 Street Food": ("Extreme Street Food", 8),
        "🕵️ True Crime": ("Police Interrogation True Crime", 8),
        "🎬 Movie Recap": ("Movie Recap Thriller Survival", 8),
    }
    with st.container(border=True):
        cat = st.segmented_control("Kategori", list(categories), default=list(categories)[0],
                                   label_visibility="collapsed", key="trend_cat") or list(categories)[0]
        data = st.session_state.trending_data.get(cat)
        if data is None:
            if st.button(f"🔎 Tampilkan video trending: {cat}", width="stretch"):
                with st.spinner("Mengambil video dari YouTube..."):
                    q, n = categories[cat]
                    try:
                        st.session_state.trending_data[cat] = YT.search(q, n)
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Gagal mengambil data: {e}")
                st.rerun()
        elif not data:
            st.info("Tidak ada hasil. Coba lagi nanti.")
        else:
            cols = st.columns(4)
            for i, res in enumerate(data):
                title, _, link = res.rpartition("|")
                vid = YT.extract_video_id(link)
                with cols[i % 4]:
                    st.markdown(f"<div class='yc-thumb'><img src='{thumb_url(vid)}' loading='lazy'>"
                                f"<div class='t'>{esc(title)}</div></div>", unsafe_allow_html=True)
                    if st.button("Pilih", key=f"sel_{cat}_{i}", width="stretch"):
                        with st.spinner("Memuat video..."):
                            start_with_url(link)

# ==========================================================
# PAGE 2: PEMBAYARAN
# ==========================================================
elif st.session_state.current_page == 2:
    page_header("Top Up Kredit", "Beli paket kredit untuk pemrosesan video YouTube.")
    with st.container(border=True):
        a, b = st.columns([3, 2], vertical_alignment="center")
        a.markdown("<div class='yc-muted'>Saldo kredit Anda</div><div style='font-size:2.4rem;font-weight:800;color:#5B4CF5'>0 kredit</div>"
                   "<div class='yc-muted'>1 kredit = 1 pemrosesan video YouTube</div>", unsafe_allow_html=True)
        with b:
            st.button("Riwayat Kredit", width="stretch")
            st.button("Riwayat Pembayaran", width="stretch")
    st.info("Top up paket apa pun membuka antrian prioritas saat server ramai.")
    plans = [("⚡ Starter", "Untuk mencoba", "Rp25.000", "10 kredit · Rp2.500/kredit", 10, False),
             ("🚀 Creator", "Pilihan populer untuk konten rutin", "Rp50.000", "22 kredit · Rp2.270/kredit", 22, False),
             ("🌟 Pro", "Value terbaik untuk produksi maksimal", "Rp99.000", "60 kredit · Rp1.650/kredit", 60, True)]
    cols = st.columns(3)
    for col, (name, desc, price, unit, n, best) in zip(cols, plans):
        with col:
            with st.container(border=True):
                badge = "<span class='yc-chip pri'>★ Best value</span>" if best else "<span class='yc-chip'>&nbsp;</span>"
                st.markdown(f"""<div class="yc-plan">{badge}<h3 style="margin-top:10px">{name}</h3>
                <div class="yc-muted">{desc}</div><div class="price">{price}</div><div class="yc-muted">{unit}</div>
                <ul><li>✓ {n} kredit proses video</li><li>✓ AI potong klip otomatis</li>
                <li>✓ Antrian prioritas</li><li>✓ Tanpa batas waktu</li></ul></div>""", unsafe_allow_html=True)
                st.button(f"Beli {name.split()[-1]}", key=f"buy_{n}", type="primary" if best else "secondary",
                          width="stretch")

# ==========================================================
# PAGE 99: ANALISIS AI
# ==========================================================
elif st.session_state.current_page == 99:
    info = st.session_state.video_info
    if not info:
        go_to_page(1)
        st.rerun()
    page_header("Temukan Momen Emas", "AI membaca seluruh video dan memilih momen paling layak viral.")
    stepper(2)

    with st.container(border=True):
        video_card(info)

    left, right = st.columns([1, 1], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("#### ⚙️ Konfigurasi AI")
            fokus_ai = st.selectbox("Fokus konten", FOKUS_OPTIONS)
            durasi_ai = st.selectbox("Target durasi per klip", DURASI_OPTIONS, index=1)
            if "global_layout" not in st.session_state:
                st.session_state.global_layout = st.session_state.get("layout_saved", R.LAYOUT_AI)
            st.selectbox("Format video", R.LAYOUTS, key="global_layout",
                         help="AI Track: kamera mengikuti orang yang sedang bicara (suara + gerak bibir). "
                              "Smart Face: mengikuti wajah paling dominan.")
            st.session_state.layout_saved = st.session_state.global_layout
    with right:
        with st.container(border=True):
            st.markdown("#### 🎬 Edit Otomatis")
            st.toggle("Zoom dinamis halus", key="opt_zoom", help="Punch-in halus saat ganti pembicara/kalimat.")
            st.toggle("Perbaiki warna & ketajaman", key="opt_enhance")
            st.toggle("Hapus jeda hening (jump cut)", key="opt_remove_silence",
                      help="Hanya jeda yang benar-benar sepi; tawa/reaksi dipertahankan.")
            st.toggle("Periksa ulang batas klip dengan AI", key="opt_second_pass",
                      help="Lebih akurat agar klimaks tidak terpotong (+1 panggilan AI).")
    st.session_state.options_saved = {k: st.session_state[f"opt_{k}"]
                                      for k in ("zoom", "enhance", "remove_silence", "second_pass")}

    with st.expander("🎨 Gaya Subtitle & Hook — font, warna, posisi", expanded=False):
        style_editor("p99")

    btn_ai = st.button("✨ Mulai Analisis AI", type="primary", width="stretch")
    c_back, c_skip = st.columns(2)
    with c_back:
        if st.button("← Ganti Video", width="stretch"):
            go_to_page(1)
            st.rerun()
    with c_skip:
        if st.button("Lewati AI (potong manual) →", width="stretch"):
            st.session_state.ai_clips = None
            st.session_state.ai_updated = True
            go_to_page(3)
            st.rerun()

    if btn_ai:
        api_keys = get_api_keys()
        if not api_keys:
            st.error("⚠️ API Key Gemini belum dikonfigurasi. Isi GEMINI_API_KEYS di .streamlit/secrets.toml.")
            st.stop()
        min_sec, max_sec = HL.duration_bounds(durasi_ai)
        with st.status("Menganalisis video...", expanded=True) as status_box:
            tr = st.session_state.transcript
            if not tr or tr.get("video_id") != info["id"]:
                st.write("📄 Mengambil transkrip/subtitle YouTube...")
                tr = TR.get_transcript(info["id"])
                if tr:
                    st.write(f"✅ Transkrip ditemukan ({tr['source']}, bahasa: {tr['language']}, {len(tr['segments'])} baris).")
                elif TR.whisper_available():
                    st.write("⚠️ Subtitle YouTube tidak tersedia. Mentranskripsi audio dengan Whisper (bisa beberapa menit)...")
                    tmpdir = tempfile.mkdtemp(prefix="youclip_audio_")
                    local_src = YT.source_path(info["id"])
                    audio = local_src if os.path.exists(local_src) and os.path.getsize(local_src) > 10000 \
                        else YT.download_audio(info["id"], tmpdir)
                    if audio:
                        bar = st.progress(0.0, text="Transkripsi audio...")
                        try:
                            segs, lang = TR.whisper_transcribe(
                                audio, size=os.environ.get("WHISPER_LONG_MODEL", "base"),
                                on_progress=lambda p: bar.progress(p, text=f"Transkripsi audio... {int(p * 100)}%"),
                                total_duration=info["duration"])
                            if segs:
                                tr = {"segments": segs, "language": lang, "is_generated": True, "source": "whisper"}
                                st.write(f"✅ Transkripsi lokal selesai ({len(segs)} baris).")
                        except Exception as e:  # noqa: BLE001
                            st.write(f"Whisper gagal: {e}")
                if tr:
                    tr["video_id"] = info["id"]
                    st.session_state.transcript = tr

            content_kind, audio_path, transcript_text = "title", None, ""
            segments = tr["segments"] if tr else []
            if segments:
                content_kind = "text"
                transcript_text = TR.to_prompt_lines(segments)
                if segments[-1]["end"] > info["duration"]:
                    info["duration"] = int(segments[-1]["end"]) + 1
            else:
                st.write("⚠️ Transkrip tidak tersedia. Mengirim audio ke Gemini...")
                audio_path = YT.download_audio(info["id"], tempfile.mkdtemp(prefix="youclip_audio_"))
                if audio_path:
                    content_kind = "audio"
                else:
                    st.warning("Audio juga gagal diunduh. AI hanya menebak dari judul — disarankan potong manual.")

            st.write("🤖 Gemini memilih momen terbaik...")
            prompt = HL.build_prompt(fokus_ai, min_sec, max_sec, content_kind, transcript_text,
                                     video_title=info["title"], video_duration=info["duration"])
            models = [secret("GEMINI_MODEL")] + HL.DEFAULT_MODELS if secret("GEMINI_MODEL") else None
            try:
                raw_clips = HL.parse_clips(HL.call_gemini(api_keys, prompt, audio_path=audio_path, models=models,
                                                          on_status=lambda m: st.write("⏳ " + m)))
            except Exception as e:  # noqa: BLE001
                status_box.update(label="Gagal", state="error")
                st.error(f"❌ Gagal mendapatkan hasil AI: {e}")
                st.stop()

            st.write("✂️ Merapikan batas klip ke awal kalimat & setelah klimaks...")
            clips = HL.refine_clips(raw_clips, segments, min_sec, max_sec, info["duration"],
                                    many="Cut Video" in fokus_ai)
            if clips and segments and st.session_state.options_saved["second_pass"]:
                st.write("🔎 AI memeriksa ulang setiap klip agar klimaks tidak terpotong...")
                clips = HL.second_pass(api_keys, clips, segments, min_sec, max_sec, info["duration"],
                                       models=models, on_status=lambda m: st.write("⏳ " + m))
            if not clips:
                status_box.update(label="AI tidak menemukan klip", state="error")
                st.error("AI tidak mengembalikan klip yang valid. Coba lagi atau ubah fokus/durasi.")
                st.stop()
            status_box.update(label=f"✅ {len(clips)} klip ditemukan", state="complete")

        layout = st.session_state.get("layout_saved", R.LAYOUT_AI)
        st.session_state.ai_clips = clips
        st.session_state.ai_updated = True
        st.session_state.clip_configs_saved = [dict(c, layout=layout) for c in clips]
        st.session_state.processed_clips = []
        go_to_page(4)
        st.rerun()

# ==========================================================
# PAGE 3: ATUR POTONGAN
# ==========================================================
elif st.session_state.current_page == 3:
    info = st.session_state.video_info
    if not info:
        st.info("Belum ada video yang dipilih. Masukkan link YouTube terlebih dahulu.")
        if st.button("← Ke Beranda"):
            go_to_page(1)
            st.rerun()
        st.stop()
    page_header("Atur Potongan Klip", "Sesuaikan waktu mulai & selesai. Format HH:MM:SS atau HH:MM:SS.s")
    stepper(3)
    max_dur = info["duration"]
    ai_clips = st.session_state.ai_clips or []
    if st.session_state.get("ai_updated", False):
        st.session_state.input_num_clips = min(max(1, len(ai_clips)), 30)
        st.session_state.ui_version += 1
        st.session_state.ai_updated = False
    if "input_num_clips" not in st.session_state:
        st.session_state.input_num_clips = 1

    num_clips = st.number_input("Jumlah klip", min_value=1, max_value=30, key="input_num_clips")
    uv = st.session_state.ui_version
    layout = st.session_state.get("layout_saved", R.LAYOUT_AI)
    clip_configs = []
    cols = st.columns(2, gap="medium")
    for i in range(num_clips):
        c = ai_clips[i] if i < len(ai_clips) else {}
        start_d = float(c.get("start", min(60 + i * 30, max(0, max_dur - 25))))
        end_d = float(c.get("end", min(start_d + 25, max_dur)))
        with cols[i % 2]:
            with st.container(border=True):
                score = f"<span class='yc-chip pri'>⭐ {c['score']}</span>" if c.get("score") else ""
                st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                            f"<div class='yc-clip-title'>Klip {i + 1}{(' · ' + esc(c['hook'])) if c.get('hook') else ''}</div>{score}</div>",
                            unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                start_input = c1.text_input("Mulai", value=fmt_time(start_d), key=f"start_{i}_v{uv}")
                end_input = c2.text_input("Selesai", value=fmt_time(end_d), key=f"end_{i}_v{uv}")
                s_val, e_val = parse_time(start_input), parse_time(end_input)
                if e_val <= s_val:
                    st.warning("Waktu selesai harus lebih besar dari waktu mulai.")
                elif e_val > max_dur + 1:
                    st.warning(f"Melebihi durasi video ({fmt_time(max_dur)}).")
                else:
                    st.markdown(f"<span class='yc-chip'>⏱️ {e_val - s_val:.1f} dtk</span>", unsafe_allow_html=True)
                if st.session_state.transcript:
                    preview = TR.text_between(st.session_state.transcript["segments"], s_val, e_val)
                    if preview:
                        st.caption("🗣️ " + (preview[:200] + ("…" if len(preview) > 200 else "")))
                with st.expander("Teks klip"):
                    output_name = st.text_input("Nama file", value=c.get("name", f"clip_{i + 1}"), key=f"name_{i}_v{uv}")
                    hook_input = st.text_input("Hook (teks di video)", value=c.get("hook", ""), key=f"hook_{i}_v{uv}")
                    deskripsi_input = st.text_area("Deskripsi", value=c.get("deskripsi", ""), key=f"desk_{i}_v{uv}", height=68)
                    caption_input = st.text_area("Caption sosmed", value=c.get("caption", ""), key=f"caption_{i}_v{uv}", height=68)
                clip_configs.append({"start": s_val, "end": e_val, "name": output_name, "hook": hook_input,
                                     "deskripsi": deskripsi_input, "caption": caption_input,
                                     "score": c.get("score", 8.0), "reason": c.get("reason", ""), "layout": layout})

    c_back, c_next = st.columns(2)
    with c_back:
        if st.button("← Kembali ke Analisis AI", width="stretch"):
            go_to_page(99)
            st.rerun()
    with c_next:
        if st.button("🔥 Render Semua Klip", type="primary", width="stretch"):
            st.session_state.clip_configs_saved = clip_configs
            st.session_state.ai_clips = [dict(c) for c in clip_configs]
            st.session_state.processed_clips = []
            go_to_page(4)
            st.rerun()

# ==========================================================
# PAGE 4: RENDER & HASIL
# ==========================================================
elif st.session_state.current_page == 4:
    configs = st.session_state.get("clip_configs_saved", [])
    page_header("Render & Hasil", "Klip siap ditonton, diunduh, dan diedit.")
    stepper(4)

    cb1, cb2, _ = st.columns([1, 1, 2])
    with cb1:
        if st.button("✏️ Atur Ulang Potongan", width="stretch"):
            st.session_state.ai_updated = True
            go_to_page(3)
            st.rerun()
    with cb2:
        if st.button("🔄 Proyek Baru", width="stretch"):
            for key in ("video_info", "ai_clips", "transcript"):
                st.session_state[key] = None
            st.session_state.video_url = ""
            st.session_state.processed_clips = []
            st.session_state.clip_configs_saved = []
            go_to_page(1)
            st.rerun()

    # ---------------- PROSES ----------------
    if not st.session_state.processed_clips and configs:
        info = st.session_state.video_info
        valid, used_names = [], set()
        for idx, c in enumerate(configs):
            s_sec, e_sec = parse_time(c["start"]), parse_time(c["end"])
            if e_sec - s_sec < 1:
                st.error(f"❌ Klip {idx + 1}: waktu selesai harus lebih besar dari waktu mulai.")
                continue
            base = safe_filename(c.get("name") or c.get("hook"), default=f"clip_{idx + 1}")
            name, n = base, 2
            while name in used_names:
                name, n = f"{base}_{n}", n + 1
            used_names.add(name)
            valid.append((idx, dict(c, start=s_sec, end=e_sec), name))

        if valid and info:
            try:
                ffmpeg_exe()
            except RuntimeError as e:
                st.error(str(e))
                st.stop()
            with st.container(border=True):
                log_box = st.empty()
                overall = st.progress(0.0)
                log_box.markdown("**📥 Menyiapkan video sumber** (diunduh sekali, lalu di-cache)…")
                source, dl_err = YT.download_source(info["id"], on_status=lambda m: log_box.markdown("**📥 " + m + "**"))
                if not source:
                    log_box.error("❌ Gagal mengunduh video sumber dari YouTube.")
                    with st.expander("Detail error yt-dlp"):
                        st.code(dl_err or "(kosong)")
                    st.info("Tips: tambahkan YOUTUBE_COOKIES di secrets atau file cookies.txt di folder project.")
                    st.stop()
                src_dur = probe(source)["duration"]
                if src_dur:
                    info["duration"] = int(src_dur)
                tr = st.session_state.transcript
                segments = tr["segments"] if tr and tr.get("video_id") == info["id"] else None
                language = tr["language"] if segments else None
                options = current_options()

                cards = {}
                grid = st.columns(3)
                for n_i, (idx, clip, name) in enumerate(valid):
                    with grid[n_i % 3]:
                        cards[idx] = st.empty()
                        cards[idx].info(f"⏳ Klip {idx + 1} — menunggu antrian")

                from concurrent.futures import ThreadPoolExecutor, as_completed
                from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
                ctx = get_script_run_ctx()

                def work(item):
                    idx, clip, name = item
                    add_script_run_ctx(ctx=ctx)
                    ph = cards[idx]

                    def status(msg, pct=None):
                        with ph.container():
                            st.markdown(f"**Klip {idx + 1}** · {esc(clip.get('hook') or name)}")
                            st.progress(int(pct or 0), text=msg)

                    try:
                        e = min(clip["end"], src_dur) if src_dur else clip["end"]
                        clip = dict(clip, end=e)
                        data = R.process_clip(source, clip, clip.get("layout", R.LAYOUT_CENTER), name,
                                              transcript=segments, language=language,
                                              options=options, on_status=status)
                        ph.success(f"✅ Klip {idx + 1} selesai ({data['elapsed']:.0f} dtk)")
                        return idx, data
                    except Exception as ex:  # noqa: BLE001
                        ph.error(f"❌ Klip {idx + 1} gagal: {ex}")
                        return idx, {"out": f"{name}.mp4", "status": "failed", "error": str(ex)[-600:]}

                workers = max(1, min(len(valid), int(os.environ.get("CLIPPER_WORKERS", "2"))))
                log_box.markdown(f"**🚀 Memproses {len(valid)} klip** · encoder `{encoder_label()}` · {workers} paralel")
                results = []
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    futures = [ex.submit(work, v) for v in valid]
                    for f in as_completed(futures):
                        results.append(f.result())
                        overall.progress(len(results) / len(valid), text=f"{len(results)}/{len(valid)} klip selesai")
                results.sort(key=lambda x: x[0])
                st.session_state.processed_clips = [r[1] for r in results]
                ok = sum(1 for r in results if r[1].get("status") == "success")
                log_box.success(f"🎉 {ok}/{len(results)} klip berhasil diproses!")
                if ok:
                    st.balloons()
                time.sleep(0.8)
                st.rerun()

    # ---------------- HASIL ----------------
    @st.fragment
    def clip_card(idx):
        clip_data = st.session_state.processed_clips[idx]
        with st.container(border=True):
            if clip_data.get("status") == "failed":
                st.error(f"❌ Klip {idx + 1} gagal diproses.")
                with st.expander("Detail error"):
                    st.code(clip_data.get("error", "Unknown"))
                return
            path = clip_data.get("path", "")
            if not os.path.exists(path):
                st.warning(f"File klip {idx + 1} sudah tidak ada di disk.")
                return
            preview = clip_data.get("preview_path") if os.path.exists(clip_data.get("preview_path") or "") else path
            top_l, top_r = st.columns([3, 1])
            top_l.markdown(f"<div class='yc-meta'>KLIP {idx + 1} · {fmt_time(clip_data.get('start', 0))} – "
                           f"{fmt_time(clip_data.get('end', 0))}</div>"
                           f"<div class='yc-clip-title'>{esc(clip_data.get('hook') or clip_data['out'])}</div>",
                           unsafe_allow_html=True)
            top_r.markdown(f"<div style='text-align:right'><div class='yc-score'>{clip_data.get('score', '-')}</div>"
                           f"<div class='yc-meta'>skor viral</div></div>", unsafe_allow_html=True)
            st.video(preview)
            sub_lbl = {"whisper": "Whisper", "youtube": "Caption YT", "whisper+youtube": "Whisper + Caption YT",
                       "none": "tanpa subtitle"}.get(clip_data.get("sub_source"), "-")
            st.markdown(f"<span class='yc-chip'>⏱️ {clip_data.get('duration', 0):.0f} dtk</span> "
                        f"<span class='yc-chip'>💬 {sub_lbl}</span>", unsafe_allow_html=True)
            safe_hook = safe_filename(clip_data.get("hook", ""), default="")
            download_link(path, f"{safe_hook}.mp4" if safe_hook else clip_data["out"],
                          key=f"dl_{idx}_{os.path.basename(path)}")
            b1, b2 = st.columns(2)
            with b1:
                if clip_data.get("layout") != R.LAYOUT_ORIGINAL and clip_data.get("raw_path"):
                    if st.button("✂️ Edit Crop", key=f"edit_btn_{idx}", width="stretch"):
                        manual_crop_dialog(idx)
            with b2:
                with st.popover("✍️ Hook", width="stretch"):
                    new_hook = st.text_input("Teks hook", value=clip_data.get("hook", ""), key=f"hook_edit_{idx}")
                    if st.button("Render ulang", key=f"rehook_{idx}", type="primary", width="stretch"):
                        with st.spinner("Merender ulang..."):
                            try:
                                restyle_one(idx, new_hook)
                                st.rerun(scope="fragment")
                            except Exception as e:  # noqa: BLE001
                                st.error(f"Gagal: {e}")
            with st.expander("Caption, deskripsi & alasan"):
                if clip_data.get("reason"):
                    st.markdown(f"<div class='yc-reason'>💡 {esc(clip_data['reason'])}</div>", unsafe_allow_html=True)
                if clip_data.get("caption"):
                    st.caption("Caption sosmed")
                    st.code(clip_data["caption"], language=None, wrap_lines=True)
                if clip_data.get("deskripsi"):
                    st.caption("Deskripsi")
                    st.code(clip_data["deskripsi"], language=None, wrap_lines=True)
                for note in clip_data.get("notes") or []:
                    st.caption(f"ℹ️ {note}")

    clips_now = st.session_state.processed_clips
    _sync_public([c.get("path") for c in clips_now] + [st.session_state.get("merged_path")])
    if clips_now:
        ok_n = sum(1 for c in clips_now if c.get("status") == "success")
        st.markdown(f"<div class='yc-section'>🎬 {ok_n} klip siap</div>", unsafe_allow_html=True)
        grid = st.columns(3, gap="medium")
        for idx in range(len(clips_now)):
            with grid[idx % 3]:
                clip_card(idx)

        restylable = [i for i, c in enumerate(clips_now)
                      if c.get("status") == "success" and c.get("base_vf") and os.path.exists(c.get("raw_path", ""))]
        if restylable:
            with st.expander("🎨 Ganti gaya subtitle & hook untuk semua klip (tanpa proses ulang)"):
                style_editor("p4")
                if st.button("✅ Terapkan Gaya ke Semua Klip", type="primary", width="stretch"):
                    bar = st.progress(0.0, text="Merender ulang...")
                    errs = []
                    for n_i, i in enumerate(restylable):
                        try:
                            restyle_one(i)
                        except Exception as e:  # noqa: BLE001
                            errs.append(f"Klip {i + 1}: {e}")
                        bar.progress((n_i + 1) / len(restylable), text=f"Merender ulang {n_i + 1}/{len(restylable)}...")
                    for e in errs:
                        st.error(e)
                    st.rerun()

        good = [c for c in clips_now if c.get("status") == "success" and os.path.exists(c.get("path", ""))]
        if len(good) > 1:
            with st.expander("🔗 Gabungkan semua klip menjadi 1 video"):
                if st.button("Gabungkan", type="primary", width="stretch"):
                    with st.spinner("Menggabungkan klip..."):
                        try:
                            out = os.path.join(DOWNLOADS_DIR, f"merged_video_{int(time.time())}.mp4")
                            R.merge_clips([c["path"] for c in good], out)
                            st.session_state.merged_path = out
                        except Exception as e:  # noqa: BLE001
                            st.error(f"Gagal menggabungkan klip: {e}")
                mp = st.session_state.get("merged_path")
                if mp and os.path.exists(mp):
                    st.success("✅ Video gabungan siap.")
                    download_link(mp, os.path.basename(mp), label="⬇️ Download Video Gabungan", key="dl_merged")
    elif not configs:
        st.info("Belum ada klip untuk diproses. Mulai dari Beranda.")

# ==========================================================
# PAGE 5: BANTUAN
# ==========================================================
elif st.session_state.current_page == 5:
    page_header("Bantuan", "Cara pakai, konfigurasi, dan diagnostik sistem.")
    a, b = st.columns([1.4, 1], gap="large")
    with a:
        with st.container(border=True):
            st.markdown("""
#### Alur pemakaian
1. Tempel link YouTube di **Beranda** → **Proses Klip**.
2. Pilih fokus, durasi, format, dan gaya → **Mulai Analisis AI**. AI membaca transkrip lengkap, memilih momen, dan memastikan klimaks tidak terpotong.
3. Engine memotong, melacak pembicara, membuat subtitle, lalu merender.
4. Potongan kurang pas → **Atur Ulang Potongan**. Crop meleset → **Edit Crop**. Ganti teks judul → **Hook**.

#### Fitur edit
- **AI Track Crop** — kamera mengikuti orang yang sedang bicara (gerak bibir dicocokkan dengan suara, 12x per detik). Shot lebar berisi banyak orang ditampilkan utuh di atas latar blur.
- **Smart Face Crop** — mengikuti wajah paling dominan.
- **Edit Otomatis** — zoom dinamis, perbaikan warna, hapus jeda hening.
- **Gaya** — 8 font, 6 preset, warna, ukuran, posisi, mode karaoke/kotak/kata/baris, progress bar.
            """)
        with st.container(border=True):
            st.markdown("""
#### Konfigurasi (`.streamlit/secrets.toml`)
- `GEMINI_API_KEYS = ["key1", "key2"]` — wajib
- `YOUTUBE_COOKIES` — bila YouTube memblokir unduhan
- `WHISPER_MODEL` — `small` (default) / `base` (cepat) / `medium` (akurat)
- `CLIPPER_ENCODER` — `auto` / `libx264` / `videotoolbox` / `nvenc` / `qsv` / `amf`
- `CLIPPER_WORKERS` (env) — jumlah klip paralel, default 2
            """)
    with b:
        with st.container(border=True):
            st.markdown("#### 🔧 Diagnostik")
            try:
                st.markdown(f"**FFmpeg**  \n`{os.path.basename(ffmpeg_exe())}`")
                st.markdown(f"**Subtitle (libass):** {'✅ didukung' if supports_subtitles() else '❌ tidak — pip install imageio-ffmpeg'}")
                st.markdown(f"**Encoder:** `{encoder_label()}`")
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
            st.markdown(f"**Whisper:** {'✅ terpasang' if TR.whisper_available() else '❌ pip install faster-whisper'}")
            st.markdown(f"**Gemini API key:** {len(get_api_keys())}")
            st.markdown(f"**Folder kerja:**  \n`{DOWNLOADS_DIR}`")
