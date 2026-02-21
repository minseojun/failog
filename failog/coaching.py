# --- (ADD BELOW) compatibility helpers for screens_* imports ---

from __future__ import annotations

import re
import json
from typing import Any, Dict, List

import streamlit as st

from failog.prefs import ck_get, ck_set, ck_del

# Consent (privacy/AI usage)
CONSENT_COOKIE_KEY = "failog_ai_consent"  # "true"/"false"


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


# (Optional) helpers used by coaching logic (if your file uses them)
def normalize_reason(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\s가-힣]", "", t)
    return t
