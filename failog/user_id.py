# failog/user_id.py
import uuid
import streamlit as st


def get_or_create_user_id() -> str:
    qp = st.query_params
    uid = (qp.get("uid", "") or "").strip()
    if uid:
        st.session_state["user_id"] = uid
        return uid

    new_uid = str(uuid.uuid4())
    st.query_params["uid"] = new_uid
    st.session_state["user_id"] = new_uid
    st.rerun()
