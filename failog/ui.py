# failog/ui.py
from __future__ import annotations

from datetime import date
import base64
import os
from functools import lru_cache

import streamlit as st


@lru_cache(maxsize=16)
def _asset_data_uri(rel_path: str) -> str:
    """
    Streamlit에서 <img src="...">로 로컬 파일을 직접 참조하면(정적 서빙 X) 배포 환경에서 깨질 수 있음.
    그래서 파일을 base64 data URI로 임베드해 100% 안정적으로 표시한다.
    """
    # 후보 경로들(레포 구조가 조금 달라도 찾게끔)
    candidates = []

    # 1) 현재 파일 기준 (failog/ui.py)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, rel_path))                          # failog/assets/hamster.gif 같은 경우
    candidates.append(os.path.join(here, "..", rel_path))                    # failog/../assets/hamster.gif (레포 루트 assets)
    candidates.append(os.path.join(here, "..", "..", rel_path))              # 더 상위 대비

    # 2) 현재 작업 디렉토리 기준
    cwd = os.getcwd()
    candidates.append(os.path.join(cwd, rel_path))
    candidates.append(os.path.join(cwd, "failog", rel_path))

    path = None
    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            path = p
            break

    if path is None:
        # 깨진 아이콘 대신 "왜 안 뜨는지" 알 수 있게 빈 문자열 반환
        return ""

    with open(path, "rb") as f:
        b = f.read()

    b64 = base64.b64encode(b).decode("utf-8")
    # GIF이므로 image/gif
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

/* 캡션이 너무 연해 보인다고 했으니 조금 더 진하게 */
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

/* ===== Tabs: 연회색 박스 처리 ===== */
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
[data-testid="stTabs"] [data-baseweb="tab-border"] {{
  background: #111111 !important;
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
  height: 60px;
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
    # gif가 경로 문제로 못 찾아지면 깨진 아이콘 대신 그냥 안 보이게 처리
    gif_html = f"<img src='{gif_uri}' class='hero-gif' />" if gif_uri else ""

    st.markdown(
        f"""
<div class="failog-hero">
  <div class="hero-left">
    <div class="failog-title">FAILOG</div>
    <div class="failog-sub">실패를 성공으로 — 계획과 습관의 실패를 기록하고, 패턴을 이해하고, 다음 주를 설계해요.</div>
  </div>
  {gif_html}
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
