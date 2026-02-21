# failog/ui.py
import streamlit as st
from failog.constants import TEXT_DARK


def inject_css():
    st.markdown(
        f"""
<style>
/* Layout */
.block-container {{
  max-width: 1120px;
  padding-top: 1.0rem;
  padding-bottom: 2.2rem;
}}
[data-testid="stAppViewContainer"] {{
  background: radial-gradient(1200px 420px at 30% 0%, rgba(160,196,242,0.28), rgba(255,255,255,0) 60%),
              linear-gradient(180deg, rgba(160,196,242,0.18) 0%, rgba(255,255,255,1) 55%);
}}
.small {{
  color: rgba(31,36,48,0.65);
  font-size: 0.92rem;
}}
.card {{
  border: 1px solid rgba(160,196,242,0.58);
  border-radius: 18px;
  padding: 14px 14px;
  background: rgba(255,255,255,0.94);
  box-shadow: 0 10px 26px rgba(160,196,242,0.14);
}}
.task {{
  border: 1px solid rgba(160,196,242,0.46);
  border-radius: 16px;
  padding: 10px 10px;
  background: rgba(255,255,255,0.95);
}}
.task + .task {{ margin-top: 8px; }}

.pill {{
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:4px 10px;
  border-radius:999px;
  border:1px solid rgba(160,196,242,0.60);
  font-size:0.82rem;
  background: rgba(255,255,255,0.80);
  color: rgba(31,36,48,0.78);
}}
.pill-strong {{
  background: rgba(160,196,242,0.28);
  border-color: rgba(160,196,242,0.88);
  color: rgba(31,36,48,0.90);
}}
hr {{
  margin: 1.1rem 0;
  border: none;
  border-top: 1px solid rgba(160,196,242,0.35);
}}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
  border-radius: 14px !important;
  border: 1px solid rgba(160,196,242,0.55) !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
  outline: none !important;
  box-shadow: 0 0 0 4px rgba(160,196,242,0.35) !important;
  border-color: rgba(160,196,242,0.95) !important;
}}

/* Hero title */
.failog-hero {{
  border: 1px solid rgba(160,196,242,0.60);
  border-radius: 22px;
  padding: 18px 18px;
  background: rgba(255,255,255,0.92);
  box-shadow: 0 12px 34px rgba(160,196,242,0.14);
}}
.failog-title {{
  font-size: 2.55rem;
  font-weight: 900;
  letter-spacing: -0.02em;
  margin: 0;
  line-height: 1.08;
  color: {TEXT_DARK};
}}
.failog-sub {{
  margin-top: 6px;
  color: rgba(31,36,48,0.66);
  font-size: 1.02rem;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def render_hero():
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
