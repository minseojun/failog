# failog/ui.py
from __future__ import annotations

from datetime import date
import base64
import os
from functools import lru_cache

import streamlit as st


@lru_cache(maxsize=16)
def _asset_data_uri(rel_path: str) -> str:
    candidates = []
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, rel_path))
    candidates.append(os.path.join(here, "..", rel_path))
    candidates.append(os.path.join(here, "..", "..", rel_path))

    cwd = os.getcwd()
    candidates.append(os.path.join(cwd, rel_path))
    candidates.append(os.path.join(cwd, "failog", rel_path))

    path = None
    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            path = p
            break
    if path is None:
        return ""

    with open(path, "rb") as f:
        b = f.read()

    b64 = base64.b64encode(b).decode("utf-8")
    # gif/png/jpg 구분 없이 일단 gif로 (너는 hamster.gif 사용)
    return f"data:image/gif;base64,{b64}"


def inject_css(today: date | None = None, selected: date | None = None):
    today_iso = today.isoformat() if today else ""
    sel_iso = selected.isoformat() if selected else ""

    dynamic = ""
    if today_iso:
        dynamic += f"""
.st-key-cal_{today_iso} button {{
  background: #e5e7eb !important;
}}
"""
    if sel_iso:
        dynamic += f"""
.st-key-cal_{sel_iso} button {{
  box-shadow: inset 0 0 0 2px #111111 !important;
}}
"""

    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

.block-container {{
  max-width: 1240px;
  padding-top: 1.0rem;
  padding-bottom: 2.2rem;
}}
[data-testid="stAppViewContainer"] {{
  background: #ffffff !important;
}}

html, body, [class*="css"] {{
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
               Arial, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif !important;
  color: #111111 !important;
}}

label, p, span, div, small, li, summary {{
  color: #111111 !important;
}}

[data-testid="stCaptionContainer"] {{
  color: rgba(17,17,17,0.78) !important;
  font-size: 0.92rem;
}}

::placeholder {{
  color: rgba(17,17,17,0.45) !important;
}}

.pill, .pill-strong {{
  display: none !important;
}}

.section-title {{
  display: inline-block;
  padding: 7px 12px;
  background: #f3f4f6;
  border: 1px solid #111111;
  border-radius: 0px;
  font-weight: 900;
  color: #111111;
  margin: 0 0 10px 0;
  letter-spacing: -0.01em;
}}
.section-title.tight {{ margin-bottom: 6px; }}

/* Buttons: 전부 흰 버튼+검은 테두리 */
[data-testid="stButton"] > button,
[data-testid="stFormSubmitButton"] > button {{
  background: #ffffff !important;
  color: #111111 !important;
  border: 1px solid #111111 !important;
  border-radius: 0px !important;
  box-shadow: none !important;
  font-weight: 800 !important;
  padding: 0.55rem 0.75rem !important;
}}
[data-testid="stButton"] > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {{
  background: #f3f4f6 !important;
}}
[data-testid="stButton"] > button:active,
[data-testid="stFormSubmitButton"] > button:active {{
  background: #e5e7eb !important;
}}

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

[data-testid="stVerticalBlockBorderWrapper"] {{
  border: 1px solid #111111 !important;
  border-radius: 0px !important;
  background: #ffffff !important;
}}

hr {{
  margin: 1.1rem 0;
  border: none;
  border-top: 1px solid rgba(17,17,17,0.18);
}}

/* ===== Tabs: 연회색 박스 처리 + 아래 검정선 제거 ===== */
[data-testid="stTabs"] button {{
  background: #f3f4f6 !important;
  border: 1px solid #111111 !important;
  border-bottom: none !important;
  border-radius: 0px !important;
  padding: 8px 12px !important;
  font-weight: 900 !important;
  color: #111111 !important;
}}
[data-testid="stTabs"] button[aria-selected="true"] {{
  background: #e5e7eb !important;
}}

/* ✅ 스샷의 '길게 검정색(빨강 조금)선' 제거 포인트
   Streamlit 버전에 따라 아래 요소가 라인 역할을 함.
   - tab-border
   - tab-list 아래 border
   - focus outline
*/
[data-testid="stTabs"] [data-baseweb="tab-border"] {{
  display: none !important;
}}
[data-testid="stTabs"] div[role="tablist"] {{
  border-bottom: none !important;
}}
[data-testid="stTabs"] div[role="tablist"]::after {{
  display: none !important;
  content: none !important;
}}

/* ===== Chat input: 연회색 배경 ===== */
[data-testid="stChatInput"] textarea {{
  background: #f3f4f6 !important;
  border: 1px solid rgba(17,17,17,0.55) !important;
  color: #111111 !important;
  border-radius: 0px !important;
}}
[data-testid="stChatInput"] textarea:focus {{
  box-shadow: 0 0 0 2px rgba(17,17,17,0.18) !important;
  border-color: #111111 !important;
}}

/* ===== Failure Report 상단 주 이동 UI(화살표/기간 박스) 조금 더 작게 ===== */
/* 이건 st.columns로 만든 버튼/컨테이너가 공통 버튼 스타일을 이미 따르므로,
   글자/패딩/높이만 살짝 줄이는 방식으로 안전하게 처리 */
.small-nav [data-testid="stButton"] > button {{
  padding: 0.45rem 0.55rem !important;
  min-height: 40px !important;
  font-weight: 800 !important;
}}
.small-nav .date-box {{
  background: #f3f4f6;
  border: 1px solid #111111;
  text-align: center;
  padding: 0.55rem 0.6rem;
  font-weight: 900;
  font-size: 1.25rem;
}}

/* ===== Calendar: 우물정 ===== */
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
.cal-grid [data-testid="stHorizontalBlock"] {{
  gap: 0px !important;
}}
.cal-grid [data-testid="column"] {{
  padding-left: 0px !important;
  padding-right: 0px !important;
}}
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
  font-weight: 800 !important;

  box-shadow: inset -1px -1px 0 0 #111111;
}}

/* ===== Planner: 성공/실패/삭제 액션 버튼을 더 작게 ===== */
div[class*="st-key-s_"] button,
div[class*="st-key-f_"] button,
div[class*="st-key-del_"] button,
div[class*="st-key-hab_s_"] button,
div[class*="st-key-hab_f_"] button,
div[class*="st-key-hab_del_task_"] button {{
  font-size: 0.82rem !important;
  padding: 0.28rem 0.4rem !important;
  min-height: 32px !important;
  font-weight: 700 !important;
}}

/* Hero */
.failog-hero {{
  border: 1px solid #111111;
  border-radius: 0px;
  padding: 14px 14px;
  background: #ffffff;

  display: flex;
  align-items: center;
  justify-content: space-between;

  margin-top: 6px;
}}
.hero-left {{
  display: flex;
  flex-direction: column;
}}
.hero-gif {{
  height: 90px;
  width: auto;
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
  color: rgba(17,17,17,0.78) !important;
  font-size: 1.02rem;
}}

{dynamic}
</style>
""",
        unsafe_allow_html=True,
    )


def section_title(text: str):
    st.markdown(f"<div class='section-title'>{text}</div>", unsafe_allow_html=True)


def render_hero():
    gif_uri = _asset_data_uri(os.path.join("assets", "hamster.gif"))
    gif_html = f"<img src='{gif_uri}' class='hero-gif' />" if gif_uri else ""

    st.markdown(
        f"""
<div class="failog-hero">
  <div class="hero-left">
    <div class="failog-title">FAILOG</div>
    <div class="failog-sub">실패를 성공으로 — 계획과 습관의 실패를 기록하고, 패턴을 이해하고, 미래를 설계해요.</div>
  </div>
  {gif_html}
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
