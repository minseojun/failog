# failog/ui.py
import streamlit as st

ACCENT_BLUE = "#111111"
TEXT_DARK = "#111111"


def inject_css():
    st.markdown(
        """
<style>
/* =========================================================
   FAILOG Skin — Black & White (No gradients)
   - Keep layout same
   - Change only visuals
   ========================================================= */
:root{
  --bg: #ffffff;
  --surface: #ffffff;
  --surface2: #f3f4f6;     /* light gray blocks */
  --surface3: #e5e7eb;     /* darker gray lines */
  --text: #111111;
  --muted: #555555;
  --border: #111111;

  --r0: 0px;
  --r1: 4px;
  --r2: 6px;

  --pad: 12px;
}

/* App background: flat white */
[data-testid="stAppViewContainer"]{
  background: var(--bg) !important;
  color: var(--text) !important;
}
.block-container{
  max-width: 1120px;
  padding-top: 1.0rem;
  padding-bottom: 2.0rem;
}

/* Remove Streamlit header transparency noise */
[data-testid="stHeader"]{ background: var(--bg) !important; }

/* Typography */
html, body, [class*="css"]{
  color: var(--text) !important;
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo",
               "Noto Sans KR", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
.small{
  color: var(--muted);
  font-size: 0.92rem;
}

/* Kill all pills/badges (요구사항 #3) */
.pill, .pill-strong{
  display: none !important;
}

/* =========================================================
   “Heading in rectangular box” (요구사항 #4)
   - Applies to Streamlit markdown headers
   ========================================================= */
h2, h3{
  display: inline-block !important;
  padding: 6px 10px !important;
  border: 2px solid var(--border) !important;
  border-radius: var(--r0) !important;
  background: var(--surface) !important;
  letter-spacing: -0.01em;
}
h2{ font-size: 1.25rem !important; }
h3{ font-size: 1.05rem !important; }

/* Divider */
hr{
  margin: 1.0rem 0;
  border: none;
  border-top: 2px solid var(--border);
}

/* =========================================================
   Your wrappers
   ========================================================= */
.failog-hero{
  border: 2px solid var(--border);
  border-radius: var(--r0);
  padding: 16px 16px;
  background: var(--surface);
}
.failog-title{
  font-size: 2.4rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  margin: 0;
  line-height: 1.04;
}
.failog-sub{
  margin-top: 6px;
  color: var(--muted);
  font-size: 1.0rem;
}

.card{
  border: 2px solid var(--border);
  border-radius: var(--r0);
  padding: var(--pad);
  background: var(--surface);
}
.task{
  border: 2px solid var(--border);
  border-radius: var(--r0);
  padding: 10px 10px;
  background: var(--surface2);
}
.task + .task{ margin-top: 10px; }

/* =========================================================
   Streamlit components — square, BW
   ========================================================= */

/* Buttons: square, BW */
.stButton>button{
  border-radius: var(--r0) !important;
  border: 2px solid var(--border) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  padding: 0.42rem 0.7rem !important;
  box-shadow: none !important;
}
.stButton>button:hover{
  background: var(--surface2) !important;
}
.stButton>button:active{
  background: var(--surface3) !important;
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input{
  border-radius: var(--r0) !important;
  border: 2px solid var(--border) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  box-shadow: none !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stNumberInput"] input:focus{
  outline: none !important;
  box-shadow: none !important;
  background: var(--surface2) !important;
}

/* Tabs: make them rectangular too */
[data-testid="stTabs"] [role="tablist"]{
  gap: 6px;
}
[data-testid="stTabs"] button[role="tab"]{
  border-radius: var(--r0) !important;
  border: 2px solid var(--border) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  padding: 8px 12px !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{
  background: var(--surface2) !important;
}

/* Expander: square box */
details{
  border: 2px solid var(--border);
  border-radius: var(--r0);
  background: var(--surface);
  padding: 6px 10px;
}
details summary{
  cursor: pointer;
}

/* Metrics: square */
[data-testid="stMetric"]{
  border: 2px solid var(--border);
  border-radius: var(--r0);
  background: var(--surface);
  padding: 10px 12px;
}
[data-testid="stMetricLabel"]{ color: var(--muted) !important; }
[data-testid="stMetricValue"]{ color: var(--text) !important; }

/* Altair container: square */
[data-testid="stVegaLiteChart"]{
  border: 2px solid var(--border);
  border-radius: var(--r0);
  background: var(--surface);
  padding: 10px;
}

/* =========================================================
   Calendar grid (요구사항 #2)
   - Applied to wrapper .cal-grid that we add in planner screen
   ========================================================= */
.cal-grid .stButton>button{
  border-radius: var(--r0) !important;
  border: 1px solid #111111 !important;
  background: #ffffff !important;
  padding: 0.25rem 0 !important;
  min-height: 34px !important;
  line-height: 1.0 !important;
  font-size: 0.86rem !important;
  font-weight: 700 !important;
}
.cal-grid .stButton>button:hover{
  background: #f3f4f6 !important;
}
.cal-grid .stButton>button:active{
  background: #e5e7eb !important;
}

/* Calendar weekday header cells */
.cal-weekdays{
  display:grid;
  grid-template-columns: repeat(7, 1fr);
  gap:6px;
  font-size:0.80rem;
  color:#111111;
  margin-top:8px;
}
.cal-weekdays > div{
  border: 1px solid #111111;
  background: #f3f4f6;
  padding: 6px 0;
  text-align:center;
  font-weight:800;
}

/* Optional: make column gaps tighter */
.cal-row{
  margin-top: 6px;
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_hero():
    # pill 제거(요구사항 #3) + 블랙&화이트 히어로
    st.markdown(
        """
<div class="failog-hero">
  <div class="failog-title">FAILOG</div>
  <div class="failog-sub">실패를 성공으로 — 계획과 습관의 실패를 기록하고, 패턴을 이해하고, 다음 주를 설계해요.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
