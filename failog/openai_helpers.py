# failog/openai_helpers.py
import streamlit as st

from failog.constants import OpenAI
from failog.cookies import ck_get, ck_set


def openai_client(api_key: str):
    if OpenAI is None:
        raise RuntimeError("openai 패키지가 설치되지 않았어요. pip install openai")
    if not api_key.strip():
        raise RuntimeError("OpenAI API Key가 비어 있어요.")
    return OpenAI(api_key=api_key.strip())


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


def set_prefs_openai(api_key: str, model: str):
    ck_set("failog_openai_key", (api_key or "").strip())
    ck_set("failog_openai_model", (model or "gpt-4o-mini").strip())
