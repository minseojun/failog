# failog/ui.py
from __future__ import annotations

from datetime import date
import streamlit as st


def inject_css(today: date | None = None, selected: date | None = None):
    """
    Black & White minimal theme.
    Fixes:
    - Form submit buttons (st.form_submit_button) also styled (no more black buttons)
    - Calendar: "우물정" grid 붙게, 폭 넓게, 줄바꿈 방지
    - Today cell: light gray background (cal_YYYY-MM-DD key 기반)
    - Selected cell: bold inset border (cal_YYYY-MM-DD key 기반)
    - Pills removed (your custom .pill)
    - Fix white-on-white text
    - Better English font: Inter
    """

    today_iso = today.isoformat() if today else ""
    sel_iso = selected.isoformat() if selected else ""

    dynamic = ""
    if today_iso:
        dynamic += f"""
/* Today highlight (calendar button key: cal_YYYY-MM-DD) */
.st-key-cal_{today_iso} button {{
  background: #e5e7eb !important;
}}
"""
    if sel_iso:
        dynamic += f"""
/* Selected highlight */
.st-key-cal_{sel_iso} button {{
  box-shadow: inset 0 0 0 2px #111111 !important;
}}
"""

    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

/* ---- Layout ---- */
.block-container {{
  max-width: 1240px;              /* 달력 폭 넓히기 */
  padding-top: 1.0rem;
  padding-bottom: 2.2rem;
}}
[data-testid="stAppViewContainer"] {{
  background: #ffffff !important;
}}

/* ---- Global typography ---- */
html, body, [class*="css"] {{
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
               Arial, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif !important;
  color: #111111 !important;
}}

/* Fix common "white text on white bg" */
label, p, span, div, small, li {{
  color: #111111 !important;
}}
[data-testid="stCaptionContainer"] {{
  color: rgba(17,17,17,0.70) !important;
  font-size: 0.92rem;
}}
::placeholder {{
  color: rgba(17,17,17,0.45) !important;
}}

/* ---- Remove custom pills completely ---- */
.pill, .pill-strong {{
  display: none !important;
  border: none !important;
  background: transparent !important;
}}

/* ---- Section title: grey rectangular emphasis ---- */
.section-title {{
  display: inline-block;
  padding: 6px 10px;
  background: #f3f4f6;
  border: 1px solid #111111;
  border-radius: 0px;
  font-weight: 800;
  color: #111111;
  margin: 0 0 8px 0;
}}
.section-title.tight {{ margin-bottom: 6px; }}

/* ---- Buttons (ALL kinds) -> white bg + black border ---- */
/* Normal st.button */
[data-testid="stButton"] > button {{
  background: #ffffff !important;
  color: #111111 !important;
  border: 1px solid #111111 !important;
  border-radius: 0px !important;
  box-shadow: none !important;
  font-weight: 700 !important;
  padding: 0.55rem 0.75rem !important;
}}
/* Form submit button (this is why "추가/습관 저장" stayed black) */
[data-testid="stFormSubmitButton"] > button {{
  background: #ffffff !important;
  color: #111111 !important;
  border: 1px solid #111111 !important;
  border-radius: 0px !important;
  box-shadow: none !important;
  font-weight: 700 !important;
  padding: 0.55rem 0.75rem !important;
}}
/* Hover/active */
[data-testid="stButton"] > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {{
  background: #f3f4f6 !important;
}}
[data-testid="stButton"] > button:active,
[data-testid="stFormSubmitButton"] > button:active {{
  background: #e5e7eb !important;
}}
/* Disabled readability */
[data-testid="stButton"] > button:disabled,
[data-testid="stFormSubmitButton"] > button:disabled {{
  opacity: 0.55 !important;
  color: #111111 !important;
  border-color: rgba(17,17,17,0.55) !important;
}}

/* ---- Inputs ---- */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
  border-radius: 0px !important;
  border: 1px solid rgba(17,17,17,0.55) !important;
  background: #ffffff !important;
  color: #111111 !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
  outline: none !important;
  box-shadow: 0 0 0 2px rgba(17,17,17,0.18) !important;
  border-color: #111111 !important;
}}

/* ---- Border containers (st.container(border=True)) ----
   This replaces the old <div class='card'> hack and removes the empty white boxes.
*/
[data-testid="stVerticalBlockBorderWrapper"] {{
  border: 1px solid #111111 !important;
  border-radius: 0px !important;
  background: #ffffff !important;
}}

/* ---- Expanders: make them square and monochrome ---- */
[data-testid="stExpander"] {{
  border: 1px solid rgba(17,17,17,0.25) !important;
  border-radius: 0px !important;
  background: #ffffff !important;
}}

/* ---- HR ---- */
hr {{
  margin: 1.1rem 0;
  border: none;
  border-top: 1px solid rgba(17,17,17,0.18);
}}

/* =========================================================
   Calendar (Month): 우물정 grid, no gaps, no wrapping
   ========================================================= */
.cal-weekdays {{
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0px;
  margin-top: 8px;
  border: 1px solid #111111;
  border-bottom: none;
}}
.cal-weekdays > div {{
  text-align: center;
  font-size: 0.82rem;
  padding: 6px 0;
  background: #f3f4f6;
  border-right: 1px solid #111111;
}}
.cal-weekdays > div:last-child {{
  border-right: none;
}}

.cal-grid {{
  border: 1px solid #111111;
  border-top: none;
}}

/* Remove gaps inside calendar rows */
.cal-grid [data-testid="stHorizontalBlock"] {{
  gap: 0px !important;
}}
.cal-grid [data-testid="column"] {{
  padding-left: 0px !important;
  padding-right: 0px !important;
}}

/* Calendar day buttons: numeric only, no wrapping */
.cal-grid [data-testid="stButton"] > button {{
  width: 100% !important;
  min-height: 38px !important;
  padding: 0px !important;
  margin: 0px !important;

  border-radius: 0px !important;
  border: none !important;
  background: #ffffff !important;

  font-size: 0.92rem !important;
  line-height: 1 !important;
  white-space: nowrap !important;
  font-weight: 700 !important;

  /* internal grid lines */
  box-shadow: inset -1px -1px 0 0 #111111;
}}

/* ---- Hero ---- */
.failog-hero {{
  border: 1px solid #111111;
  border-radius: 0px;
  padding: 14px 14px;
  background: #ffffff;
}}
.failog-title {{
  font-size: 2.25rem;
  font-weight: 900;
  letter-spacing: -0.02em;
  margin: 0;
  line-height: 1.08;
  color: #111111;
}}
.failog-sub {{
  margin-top: 6px;
  color: rgba(17,17,17,0.70) !important;
  font-size: 1.02rem;
}}

{dynamic}
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
