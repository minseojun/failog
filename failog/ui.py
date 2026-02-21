# failog/ui.py
import streamlit as st

# (호환/기록용) 기존 코드에서 쓰던 상수명이 다른 곳에 남아있을 수 있어 유지합니다.
ACCENT_BLUE = "#A0C4F2"
TEXT_DARK = "#0f172a"


def inject_css():
    """
    FAILOG Minimal Skin (Notion / Apple-ish)
    - Light, minimal, premium look
    - Works with existing .card / .task / .pill / .failog-hero markup
    """
    st.markdown(
        """
<style>
/* =========================
   FAILOG Minimal (Notion/Apple-ish)
   ========================= */

/* Design Tokens */
:root{
  --bg: #fbfbfc;
  --surface: #ffffff;
  --surface-2: #f6f7f9;
  --border: rgba(15, 23, 42, 0.10);
  --border-2: rgba(15, 23, 42, 0.14);

  --text: rgba(15, 23, 42, 0.92);
  --muted: rgba(15, 23, 42, 0.62);
  --muted2: rgba(15, 23, 42, 0.48);

  --accent: #2563eb;      /* blue */
  --accent-soft: rgba(37, 99, 235, 0.12);
  --success: #16a34a;
  --danger: #e11d48;

  --r-xl: 24px;
  --r-lg: 18px;
  --r-md: 14px;
  --r-sm: 12px;

  --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06);
  --shadow-md: 0 10px 30px rgba(15, 23, 42, 0.08);
  --shadow-focus: 0 0 0 4px rgba(37, 99, 235, 0.18);
}

/* System font stack (Apple-ish) */
html, body{
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text",
               "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", Roboto, Helvetica, Arial, "Apple Color Emoji",
               "Segoe UI Emoji", "Segoe UI Symbol", sans-serif;
}

/* Page background & layout */
[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1200px 420px at 20% 0%, rgba(37,99,235,0.08), rgba(255,255,255,0) 60%),
    radial-gradient(900px 380px at 85% 8%, rgba(15,23,42,0.06), rgba(255,255,255,0) 55%),
    linear-gradient(180deg, var(--bg) 0%, var(--bg) 100%);
  color: var(--text);
}

.block-container{
  max-width: 1120px;
  padding-top: 1.2rem;
  padding-bottom: 2.3rem;
}

/* Default text */
html, body, [class*="css"]{
  color: var(--text) !important;
}
h1, h2, h3, h4{
  letter-spacing: -0.01em;
}
.small{
  color: var(--muted);
  font-size: 0.92rem;
}

/* Remove Streamlit header background */
[data-testid="stHeader"]{
  background: transparent;
}

/* =========================
   Hero
   ========================= */
.failog-hero{
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: 18px 18px;
  background: rgba(255,255,255,0.88);
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(10px);
}
.failog-title{
  font-size: 2.55rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  margin: 0;
  line-height: 1.05;
  color: var(--text);
}
.failog-sub{
  margin-top: 8px;
  color: var(--muted);
  font-size: 1.02rem;
}

/* link */
.failog-hero a{
  color: rgba(37, 99, 235, 0.92);
  text-decoration: none;
}
.failog-hero a:hover{
  text-decoration: underline;
}

/* =========================
   Cards / Sections
   ========================= */
.card{
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: 14px 14px;
  background: rgba(255,255,255,0.92);
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(10px);
}

.task{
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 10px 10px;
  background: rgba(255,255,255,0.96);
  box-shadow: var(--shadow-sm);
}
.task + .task { margin-top: 10px; }

/* Dividers */
hr{
  margin: 1.05rem 0;
  border: none;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

/* =========================
   Pills / Badges
   ========================= */
.pill{
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:4px 10px;
  border-radius:999px;
  border:1px solid rgba(15, 23, 42, 0.10);
  font-size:0.82rem;
  background: rgba(15, 23, 42, 0.03);
  color: rgba(15, 23, 42, 0.70);
}
.pill-strong{
  background: var(--accent-soft);
  border-color: rgba(37, 99, 235, 0.28);
  color: rgba(37, 99, 235, 0.92);
}

/* =========================
   Buttons
   ========================= */
.stButton>button{
  border-radius: 14px !important;
  border: 1px solid rgba(15, 23, 42, 0.12) !important;
  background: rgba(255,255,255,0.96) !important;
  color: var(--text) !important;
  box-shadow: var(--shadow-sm) !important;
  transition: transform .06s ease, box-shadow .2s ease, border-color .2s ease, background .2s ease;
}
.stButton>button:hover{
  border-color: rgba(37, 99, 235, 0.26) !important;
  background: rgba(37, 99, 235, 0.06) !important;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.10) !important;
}
.stButton>button:active{
  transform: translateY(1px);
}

/* =========================
   Inputs
   ========================= */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea{
  border-radius: 14px !important;
  border: 1px solid rgba(15, 23, 42, 0.12) !important;
  background: rgba(255,255,255,0.96) !important;
  color: var(--text) !important;
  box-shadow: var(--shadow-sm) !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder{
  color: rgba(15, 23, 42, 0.38) !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus{
  outline: none !important;
  box-shadow: var(--shadow-focus) !important;
  border-color: rgba(37, 99, 235, 0.55) !important;
}

/* Select / multiselect */
[data-testid="stSelectbox"] div[role="combobox"],
[data-testid="stMultiSelect"] div[role="combobox"]{
  border-radius: 14px !important;
  border: 1px solid rgba(15, 23, 42, 0.12) !important;
  background: rgba(255,255,255,0.96) !important;
  box-shadow: var(--shadow-sm) !important;
}
[data-testid="stSelectbox"] div[role="combobox"]:focus-within,
[data-testid="stMultiSelect"] div[role="combobox"]:focus-within{
  box-shadow: var(--shadow-focus) !important;
  border-color: rgba(37, 99, 235, 0.55) !important;
}

/* Number input */
[data-testid="stNumberInput"] input{
  border-radius: 14px !important;
  border: 1px solid rgba(15, 23, 42, 0.12) !important;
  background: rgba(255,255,255,0.96) !important;
  box-shadow: var(--shadow-sm) !important;
}

/* =========================
   Tabs
   ========================= */
[data-testid="stTabs"] [role="tablist"]{
  gap: 6px;
}
[data-testid="stTabs"] button[role="tab"]{
  border-radius: 999px !important;
  border: 1px solid rgba(15, 23, 42, 0.10) !important;
  background: rgba(255,255,255,0.70) !important;
  color: rgba(15, 23, 42, 0.68) !important;
  padding: 8px 12px !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{
  background: rgba(37, 99, 235, 0.08) !important;
  border-color: rgba(37, 99, 235, 0.22) !important;
  color: rgba(37, 99, 235, 0.92) !important;
  box-shadow: var(--shadow-sm) !important;
}

/* =========================
   Expanders
   ========================= */
details{
  border: 1px solid rgba(15, 23, 42, 0.10);
  border-radius: var(--r-xl);
  background: rgba(255,255,255,0.88);
  box-shadow: var(--shadow-sm);
  padding: 6px 10px;
}
details summary{
  cursor: pointer;
  color: var(--text);
}
details summary:hover{
  color: rgba(37, 99, 235, 0.95);
}

/* =========================
   Metrics
   ========================= */
[data-testid="stMetric"]{
  border: 1px solid rgba(15, 23, 42, 0.10);
  border-radius: var(--r-xl);
  background: rgba(255,255,255,0.90);
  box-shadow: var(--shadow-sm);
  padding: 10px 12px;
}
[data-testid="stMetricLabel"]{
  color: var(--muted) !important;
}
[data-testid="stMetricValue"]{
  color: var(--text) !important;
}

/* =========================
   Altair charts container polish
   ========================= */
[data-testid="stVegaLiteChart"]{
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--r-xl);
  background: rgba(255,255,255,0.92);
  box-shadow: var(--shadow-sm);
  padding: 10px;
}

/* Toast subtle */
div[data-baseweb="toast"]{
  border-radius: 16px;
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_hero():
    """
    Notion/Apple-ish hero.
    기존처럼 HTML 기반이지만, 더 미니멀/고급 톤으로 정리.
    """
    st.markdown(
        """
<div class="failog-hero">
  <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">
    <div>
      <div class="failog-title">FAILOG</div>
      <div class="failog-sub">
        실패를 성공으로 — 계획과 습관의 실패를 기록하고, 패턴을 이해하고, 다음 주를 설계해요.
      </div>
    </div>
    <div style="min-width:120px; text-align:right;">
      <div class="pill pill-strong" title="KST 기준">KST · Seoul</div>
    </div>
  </div>
  <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap;">
    <span class="pill">Planner</span>
    <span class="pill">Failure Report</span>
    <span class="pill">Weekly PDF</span>
    <span class="pill">AI Coaching (opt-in)</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
