# failog/prefs.py
from __future__ import annotations

import streamlit as st

# Optional cookie manager (best-effort)
try:
    import extra_streamlit_components as stx
except Exception:
    stx = None


def cookie_mgr():
    """
    Cookie manager is best-effort.
    If stx is not installed/available, returns None and prefs fall back to defaults.
    """
    if stx is None:
        return None
    if "x_cookie_mgr" not in st.session_state:
        st.session_state["x_cookie_mgr"] = stx.CookieManager()
    return st.session_state["x_cookie_mgr"]


def ck_get(key: str, default: str = "") -> str:
    cm = cookie_mgr()
    if cm is None:
        return default
    try:
        v = cm.get(key)
        return default if v is None else str(v)
    except Exception:
        return default


def ck_set(key: str, value: str, expires_days: int = 3650) -> None:
    cm = cookie_mgr()
    if cm is None:
        return
    v = "" if value is None else str(value)
    try:
        # Some versions support expires_at_days
        if hasattr(cm, "set") and "expires_at_days" in cm.set.__code__.co_varnames:
            cm.set(key, v, expires_at_days=int(expires_days))
        else:
            cm.set(key, v)
    except Exception:
        try:
            cm.set(key, v)
        except Exception:
            pass


def ck_del(key: str) -> None:
    cm = cookie_mgr()
    if cm is None:
        return
    for fn in ("delete", "remove", "delete_cookie"):
        if hasattr(cm, fn):
            try:
                getattr(cm, fn)(key)
                return
            except Exception:
                pass
    try:
        cm.set(key, "")
    except Exception:
        pass
