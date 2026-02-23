# failog/nav.py
from __future__ import annotations

import streamlit as st


def top_nav() -> str:
    """
    Returns one of:
      - "planner"
      - "failures"
      - "puzzle"
    """

    if "nav_screen" not in st.session_state:
        st.session_state["nav_screen"] = "planner"

    # 상단 메뉴 바
    c1, c2, c3, c4 = st.columns([1.2, 1.6, 1.0, 6.2], gap="small")

    with c1:
        if st.button("Planner", use_container_width=True, key="nav_planner"):
            st.session_state["nav_screen"] = "planner"

    with c2:
        if st.button("Failure Report", use_container_width=True, key="nav_failures"):
            st.session_state["nav_screen"] = "failures"

    # ✅ 퍼즐: 메인메뉴 옆에 "퍼즐 이모지"로
    with c3:
        if st.button("🧩", use_container_width=True, key="nav_puzzle"):
            st.session_state["nav_screen"] = "puzzle"

    # 오른쪽 여백
    with c4:
        st.write("")

    return str(st.session_state["nav_screen"])
