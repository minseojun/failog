# failog/panels.py
import streamlit as st

from failog.cookies import ck_del, ck_set
from failog.openai_helpers import prefs_openai_key, prefs_openai_model, set_prefs_openai
from failog.consent import consent_value, set_consent


def render_openai_bottom_panel():
    st.markdown("<hr/>", unsafe_allow_html=True)
    st.markdown("### 🔑 OpenAI 설정")

    default_key = prefs_openai_key()
    default_model = prefs_openai_model()

    col1, col2, col3 = st.columns([3.0, 1.6, 1.4])
    with col1:
        api_key = st.text_input(
            "OpenAI API Key",
            value=st.session_state.get("openai_api_key", "") or default_key,
            type="password",
            placeholder="sk-...",
            key="bottom_openai_key",
        )
    with col2:
        model = st.text_input(
            "모델",
            value=st.session_state.get("openai_model", "") or default_model,
            key="bottom_openai_model",
        )
    with col3:
        save_default = (default_key.strip() != "")
        save = st.toggle(
            "쿠키 저장",
            value=save_default,
            help="같은 브라우저에서 유지돼요. (쿠키가 막히면 저장 안 될 수 있어요)",
            key="bottom_openai_save",
        )

    a, b, c = st.columns([1, 1, 3])
    with a:
        if st.button("적용", use_container_width=True, key="bottom_apply"):
            st.session_state["openai_api_key"] = (api_key or "").strip()
            st.session_state["openai_model"] = (model or "gpt-4o-mini").strip()

            if save:
                set_prefs_openai(api_key or "", model or "gpt-4o-mini")
            else:
                ck_del("failog_openai_key")
                ck_set("failog_openai_model", (model or "gpt-4o-mini").strip())

            st.success("적용됐어요.")
    with b:
        if st.button("저장값 삭제", use_container_width=True, key="bottom_clear"):
            ck_del("failog_openai_key")
            ck_del("failog_openai_model")
            st.success("저장값을 삭제했어요.")
            st.rerun()
    with c:
        st.caption("user_id는 URL(uid)로 고정되어 있고, OpenAI 키는 선택적으로 쿠키에 저장됩니다.")


def render_privacy_ai_consent_panel():
    st.markdown("<hr/>", unsafe_allow_html=True)
    st.markdown("### 🔒 데이터/AI 안내 및 동의")

    current = consent_value()

    with st.container():
        st.caption(
            "실패 이유·생활 패턴은 개인에게 민감한 데이터일 수 있어요. "
            "FAILOG는 아래 원칙으로 데이터를 다룹니다."
        )

        with st.expander("자세히 보기", expanded=False):
            st.markdown(
                """
- **저장**: 계획/습관/체크/실패원인은 서버의 **SQLite(planner.db)**에 저장됩니다.  
- **식별자**: user_id는 로그인 대신 **URL의 uid 파라미터**로 구분됩니다. (링크를 공유하면 동일 데이터가 보일 수 있어요)  
- **쿠키**: OpenAI 키/모델, 알림/날씨 등 일부 설정은 **쿠키**에 저장될 수 있습니다. (브라우저 정책에 따라 제한 가능)  
- **AI(OpenAI) 사용**:  
  - *버튼을 눌러 요청한 경우에만* 실패 원인을 분석/카테고리화/코칭을 위해 OpenAI API가 호출됩니다.  
  - 호출 시, 분석에 필요한 범위의 텍스트(실패 원인/요약된 패턴 등)가 전송될 수 있습니다.  
  - 동의하지 않으면 AI 기능은 작동하지 않습니다.
                """.strip()
            )

        checked = st.checkbox(
            "위 내용을 이해했으며, OpenAI 기반 분석/코칭 기능 사용에 동의합니다.",
            value=current,
            key="ai_consent_checkbox",
        )
        if checked != current:
            set_consent(bool(checked))
            st.success("동의 설정이 저장됐어요.")
