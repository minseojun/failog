# failog/ui.py
from __future__ import annotations

from datetime import date
import streamlit as st


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

/* ---------- Layout ---------- */

.block-container {{
  max-width: 1240px;
  padding-top: 1.6rem;   /* 🔥 제목 잘림 방지: 위쪽 여백 증가 */
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

label, p, span, div, small, li {{
  color: #111111 !important;
}}

[data-testid="stCaptionContainer"] {{
  color: rgba(17,17,17,0.78) !important;
  font-size: 0.92rem;
}}

::placeholder {{
  color: rgba(17,17,17,0.45) !important;
}}

/* ---------- Hero ---------- */

.failog-hero {{
  margin-top: 8px;   /* 🔥 위에서 살짝 더 내려줌 */
  border: 1px solid #111111;
  border-radius: 0px;
  padding: 16px 18px;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

.hero-left {{
  display: flex;
  flex-direction: column;
}}

.failog-title {{
  font-size: 2.4rem;
  font-weight: 900;
  letter-spacing: -0.02em;
  margin: 0;
  line-height: 1.15;   /* 🔥 잘림 방지 */
  color: #111111;
}}

.failog-sub {{
  margin-top: 6px;
  color: rgba(17,17,17,0.75);
  font-size: 1.02rem;
}}

.hero-gif {{
  height: 60px;       /* GIF 크기 조절 */
  width: auto;
}}

{dynamic}
</style>
""",
        unsafe_allow_html=True,
    )


def section_title(text: str):
    st.markdown(f"<div class='section-title'>{text}</div>", unsafe_allow_html=True)


def render_hero():
    st.markdown(
        """
<div class="failog-hero">
  <div class="hero-left">
    <div class="failog-title">FAILOG</div>
    <div class="failog-sub">
      실패를 성공으로 — 계획과 습관의 실패를 기록하고, 패턴을 이해하고, 다음 주를 설계해요.
    </div>
  </div>

  <!-- 🔥 오른쪽 GIF -->
  <div>
    <img src="assets/hamster.gif" class="hero-gif">
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
