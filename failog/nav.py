# failog/nav.py
import streamlit as st


def top_nav():
    if "screen" not in st.session_state:
        st.session_state["screen"] = "planner"

    c1, c2, _ = st.columns([1.2, 1.8, 6])
    with c1:
        if st.button(" Planner", use_container_width=True, key="nav_plan"):
            st.session_state["screen"] = "planner"
            st.rerun()
    with c2:
        if st.button(" Failure Report", use_container_width=True, key="nav_fail"):
            st.session_state["screen"] = "fail"
            st.rerun()

    st.write("")
    return st.session_state["screen"]
