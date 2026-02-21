# failog/ui.py
import streamlit as st

ACCENT_BLUE = "#2563eb"
TEXT_DARK = "#0f172a"


def inject_css():
    st.markdown(
        """
<style>
/* =========================================================
   FAILOG Skin — Minimal Premium (Notion + Apple-ish)
   - Layout unchanged (Streamlit columns/forms/buttons stay)
   - Only visual skin overrides
   ========================================================= */

/* ---------- Tokens ---------- */
:root{
  --bg: #fbfbfc;
  --surface: #ffffff;
  --surface-2: #f6f7f9;

  --text: rgba(15, 23, 42, 0.92);
  --muted: rgba(15, 23, 42, 0.62);
  --muted2: rgba(15, 23, 42, 0.46);

  --border: rgba(15, 23, 42, 0.10);
  --border-strong: rgba(15, 23, 42, 0.16);

  --accent: #2563eb;
  --accent-soft: rgba(37, 99, 235, 0.10);

  --success: #16a34a;
  --danger: #e11d48;

  --r-xl: 24px;
  --r-lg: 18px;
  --r-md: 14px;
  --r-sm: 12px;

  --shadow-sm: 0 1px 2px rgba(15,23,42,0.06);
  --shadow-md: 0 10px 30px rgba(15,23,42,0.08);
  --shadow-lg: 0 18px 60px rgba(15,23,42,0.10);
  --focus: 0 0 0 4px rgba(37,99,235,0.16);
}

/* ---------- Font (Apple-ish) ---------- */
html, body{
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text",
               "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", Roboto, Helvetica, Arial,
               "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", sans-serif;
}

/* ---------- Page / Container ---------- */
[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1200px 420px at 20% 0%, rgba(37,99,235,0.08), rgba(255,255,255,0) 60%),
    radial-gradient(900px 380px at 85% 8%, rgba(15,23,42,0.06), rgba(255,255,255,0) 55%),
    linear-gradient(180deg, var(--bg) 0%, var(--bg) 100%);
  color: var(--text);
}

.block-container{
  max-width: 1120px;
  padding-top: 1.15rem;
  padding-bottom: 2.2rem;
}

[data-testid="stHeader"]{ background: transparent; }

/* Default text */
html, body, [class*="css"]{ color: var(--text) !important; }
.small{ color: var(--muted); font-size: 0.92rem; }

/* ---------- Subtle global spacing polish ---------- */
div[data-testid="stVerticalBlock"] > div:has(> hr){
  margin-top: 10px;
}

/* ---------- Dividers ---------- */
hr{
  margin: 1.05rem 0;
  border: none;
  border-top: 1px solid rgba(15,23,42,0.08);
}

/* =========================================================
   Your custom wrappers (safe, stable)
   ========================================================= */
.card{
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: 14px 14px;
  background: rgba(255,255,255,0.92);
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(10px);
}

.task{
  border: 1px solid rgba(15,23,42,0.10);
  border-radius: var(--r-lg);
  padding: 11px 11px;
  background: rgba(255,255,255,0.96);
  box-shadow: var(--shadow-sm);
}
.task + .task{ margin-top: 10px; }

/* Pills */
.pill{
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:4px 10px;
  border-radius:999px;
  border:1px solid rgba(15,23,42,0.10);
  font-size:0.82rem;
  background: rgba(15,23,42,0.03);
  color: rgba(15,23,42,0.70);
}
.pill-strong{
  background: var(--accent-soft);
  border-color: rgba(37,99,235,0.22);
  color: rgba(37,99,235,0.92);
}

/* Hero */
.failog-hero{
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: 18px 18px;
  background: rgba(255,255,255,0.88);
  box-shadow: var(--shadow-lg);
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

/* =========================================================
   Streamlit component skin overrides (layout unchanged)
   ========================================================= */

/* --- Buttons --- */
.stButton>button{
  border-radius: 14px !important;
  border: 1px solid rgba(15,23,42,0.12) !important;
  background: rgba(255,255,255,0.96) !important;
  color: var(--text) !important;
  box-shadow: var(--shadow-sm) !important;
  transition: transform .06s ease, box-shadow .20s ease, border-color .20s ease, background .20s ease;
}
.stButton>button:hover{
  border-color: rgba(37,99,235,0.24) !important;
  background: rgba(37,99,235,0.06) !important;
  box-shadow: var(--shadow-md) !important;
}
.stButton>button:active{ transform: translateY(1px); }

/* Make “primary-like” when inside forms (same placement, just emphasis) */
[data-testid="stForm"] .stButton>button{
  border-color: rgba(37,99,235,0.22) !important;
}

/* --- Inputs / Textareas --- */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea{
  border-radius: 14px !important;
  border: 1px solid rgba(15,23,42,0.12) !important;
  background: rgba(255,255,255,0.96) !important;
  color: var(--text) !important;
  box-shadow: var(--shadow-sm) !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder{
  color: rgba(15,23,42,0.38) !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus{
  outline: none !important;
  box-shadow: var(--focus) !important;
  border-color: rgba(37,99,235,0.55) !important;
}

/* --- Select / MultiSelect --- */
[data-testid="stSelectbox"] div[role="combobox"],
[data-testid="stMultiSelect"] div[role="combobox"]{
  border-radius: 14px !important;
  border: 1px solid rgba(15,23,42,0.12) !important;
  background: rgba(255,255,255,0.96) !important;
  box-shadow: var(--shadow-sm) !important;
}
[data-testid="stSelectbox"] div[role="combobox"]:focus-within,
[data-testid="stMultiSelect"] div[role="combobox"]:focus-within{
  box-shadow: var(--focus) !important;
  border-color: rgba(37,99,235,0.55) !important;
}

/* --- Number input --- */
[data-testid="stNumberInput"] input{
  border-radius: 14px !important;
  border: 1px solid rgba(15,23,42,0.12) !important;
  background: rgba(255,255,255,0.96) !important;
  box-shadow: var(--shadow-sm) !important;
}

/* --- Checkbox / Toggle polish --- */
[data-testid="stCheckbox"] label,
[data-testid="stToggle"] label{
  color: var(--text) !important;
}
[data-testid="stCheckbox"] p,
[data-testid="stToggle"] p{
  color: var(--muted) !important;
}

/* --- Tabs --- */
[data-testid="stTabs"] [role="tablist"]{ gap: 6px; }
[data-testid="stTabs"] button[role="tab"]{
  border-radius: 999px !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  background: rgba(255,255,255,0.70) !important;
  color: rgba(15,23,42,0.68) !important;
  padding: 8px 12px !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{
  background: rgba(37,99,235,0.08) !important;
  border-color: rgba(37,99,235,0.22) !important;
  color: rgba(37,99,235,0.92) !important;
  box-shadow: var(--shadow-sm) !important;
}

/* --- Expanders --- */
details{
  border: 1px solid rgba(15,23,42,0.10);
  border-radius: var(--r-xl);
  background: rgba(255,255,255,0.88);
  box-shadow: var(--shadow-sm);
  padding: 6px 10px;
}
details summary{
  cursor: pointer;
  color: var(--text);
}
details summary:hover{ color: rgba(37,99,235,0.95); }

/* --- Metric cards --- */
[data-testid="stMetric"]{
  border: 1px solid rgba(15,23,42,0.10);
  border-radius: var(--r-xl);
  background: rgba(255,255,255,0.90);
  box-shadow: var(--shadow-sm);
  padding: 10px 12px;
}
[data-testid="stMetricLabel"]{ color: var(--muted) !important; }
[data-testid="stMetricValue"]{ color: var(--text) !important; }

/* --- Altair chart container --- */
[data-testid="stVegaLiteChart"]{
  border: 1px solid rgba(15,23,42,0.08);
  border-radius: var(--r-xl);
  background: rgba(255,255,255,0.92);
  box-shadow: var(--shadow-sm);
  padding: 10px;
}

/* --- Toast --- */
div[data-baseweb="toast"]{ border-radius: 16px; }

/* Small labels */
.stCaption, [data-testid="stCaptionContainer"]{
  color: var(--muted) !important;
}

/* Optional: Hide Streamlit “hamburger / deploy” area spacing issues (safe-ish) */
[data-testid="stToolbar"]{
  right: 0.6rem;
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_hero():
    """
    Same placement as before. Just premium minimal styling.
    No functional/layout changes to the rest of the app.
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
