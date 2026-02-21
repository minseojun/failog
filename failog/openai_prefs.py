# failog/openai_prefs.py
from __future__ import annotations

import streamlit as st
from failog.prefs import ck_get


def prefs_openai_key() -> str:
    return ck_get("failog_openai_key", "").strip()


def prefs_openai_model() -> str:
    m = ck_get("failog_openai_model", "gpt-4o-mini").strip()
    return m if m else "gpt-4o-mini"


def effective_openai_key() -> str:
    sk = st.session_state.get("openai_api_key", "")
    return sk.strip() if sk and sk.strip() else prefs_openai_key()


def effective_openai_model() -> str:
    sm = st.session_state.get("openai_model", "")
    return sm.strip() if sm and sm.strip() else prefs_openai_model()
