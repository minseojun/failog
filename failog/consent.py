# failog/consent.py
import streamlit as st
from failog.cookies import ck_get, ck_set
from failog.constants import CONSENT_COOKIE_KEY


def consent_value() -> bool:
    # 1) session_state first
    if "ai_consent" in st.session_state:
        return bool(st.session_state["ai_consent"])
    # 2) cookie best-effort
    v = ck_get(CONSENT_COOKIE_KEY, "").strip().lower()
    if v in ("true", "1", "yes", "y"):
        st.session_state["ai_consent"] = True
        return True
    if v in ("false", "0", "no", "n"):
        st.session_state["ai_consent"] = False
        return False
    # default: not consented
    st.session_state["ai_consent"] = False
    return False


def set_consent(v: bool):
    st.session_state["ai_consent"] = bool(v)
    ck_set(CONSENT_COOKIE_KEY, "true" if v else "false")
