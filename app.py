# app.py
import streamlit as st

from failog.ui import inject_css, render_hero
from failog.db import init_db
from failog.user_id import get_or_create_user_id
from failog.nav import top_nav
from failog.screens_planner import screen_planner
from failog.screens_failures import screen_failures
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
    else:
        screen_failures(user_id)

    render_openai_bottom_panel()
    render_privacy_ai_consent_panel()


if __name__ == "__main__":
    main()
