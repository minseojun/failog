# app.py
from __future__ import annotations

import streamlit as st

from failog.db import init_db
from failog.nav import top_nav
from failog.ui import inject_css, render_hero
from failog.user_id import get_or_create_user_id

from failog.screens_planner import screen_planner
from failog.screens_failures import screen_failures
from failog.screens_puzzle import screen_puzzle

from failog.panels import render_openai_bottom_panel, render_privacy_ai_consent_panel


def main():
    st.set_page_config(page_title="FAILOG", page_icon="🧊", layout="wide")

    inject_css()
    init_db()

    user_id = get_or_create_user_id()
    render_hero()

    screen = top_nav()

    if screen == "planner":
        screen_planner(user_id)

        with st.expander("🔑 OpenAI 설정", expanded=False):
            render_openai_bottom_panel()

        with st.expander("🔒 데이터/AI 안내 및 동의", expanded=False):
            render_privacy_ai_consent_panel()

    elif screen == "failures":
        screen_failures(user_id)

    elif screen == "puzzle":
        screen_puzzle(user_id)

    else:
        # fallback
        screen_planner(user_id)


if __name__ == "__main__":
    main()
