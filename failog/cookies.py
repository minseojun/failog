# failog/cookies.py
import streamlit as st
from failog.constants import stx


def cookie_mgr():
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


def ck_set(key: str, value: str, expires_days: int = 3650):
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


def ck_del(key: str):
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
