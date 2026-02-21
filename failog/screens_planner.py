# failog/screens_planner.py
from datetime import date, datetime, timedelta

import streamlit as st

from failog.constants import KST, st_autorefresh
from failog.cookies import ck_get, ck_set
from failog.dates import week_start, week_days, korean_dow, month_grid
from failog.habits_tasks import (
    ensure_week_habit_tasks,
    add_plan_task,
    list_habits,
    add_habit,
    set_habit_active,
    delete_habit,
    list_tasks_for_date,
    update_task_status,
    update_task_fail,
    delete_task,
    count_today_todos,
)
from failog.reminder import parse_hhmm, should_remind
from failog.weather import weather_card


def screen_planner(user_id: str):
    st.markdown("## Planner")

    if st_autorefresh is not None:
        st_autorefresh(interval=60_000, key="auto_refresh_planner")

    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = date.today()

    selected = st.session_state["selected_date"]
    ws = week_start(selected)
    ensure_week_habit_tasks(user_id, ws)

    # Reminder settings (prefs)
    en = (ck_get("failog_rem_enabled", "true").lower() == "true")
    rt_str = ck_get("failog_rem_time", "21:30")
    win_str = ck_get("failog_rem_win", "15")
    remind_t = parse_hhmm(rt_str)
    try:
        win = int(win_str)
    except Exception:
        win = 15

    if en and should_remind(datetime.now(KST), remind_t, win):
        todos = count_today_todos(user_id)
        if todos > 0:
            st.toast(f"⏰ 아직 체크하지 않은 항목이 {todos}개 있어요", icon="⏰")

    left, right = st.columns([1.05, 1.95], gap="large")

    with left:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("### Month")

        y, m = selected.year, selected.month
        nav = st.columns([1, 2, 1])
        with nav[0]:
            if st.button("◀", use_container_width=True, key="m_prev"):
                if m == 1:
                    y -= 1
                    m = 12
                else:
                    m -= 1
                st.session_state["selected_date"] = date(y, m, 1)
                st.rerun()
        with nav[1]:
            st.markdown(
                f"<div style='text-align:center; font-weight:800; font-size:1.05rem;'>{y}.{m:02d}</div>",
                unsafe_allow_html=True,
            )
        with nav[2]:
            if st.button("▶", use_container_width=True, key="m_next"):
                if m == 12:
                    y += 1
                    m = 1
                else:
                    m += 1
                st.session_state["selected_date"] = date(y, m, 1)
                st.rerun()

        st.markdown(
            "<div style='display:grid; grid-template-columns: repeat(7, 1fr); gap:6px; font-size:0.78rem; opacity:0.75; margin-top:8px;'>"
            + "".join([f"<div style='text-align:center;'>{k}</div>" for k in ["월", "화", "수", "목", "금", "토", "일"]])
            + "</div>",
            unsafe_allow_html=True,
        )

        grid = month_grid(y, m)
        today = date.today()
        for row in grid:
            cols = st.columns(7, gap="small")
            for i, d in enumerate(row):
                if d is None:
                    cols[i].markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)
                    continue
                label = f"{d.day}"
                if d == today:
                    label = f"•{d.day}"
                if cols[i].button(label, key=f"cal_{d.isoformat()}", use_container_width=True):
                    st.session_state["selected_date"] = d
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("알림 설정", expanded=False):
            en_ui = st.toggle("리마인더 켜기", value=en, key="rem_en_ui")
            t_ui = st.text_input("시간(HH:MM)", value=rt_str, key="rem_t_ui")
            w_ui = st.number_input("허용 오차(분)", min_value=1, max_value=120, value=win, key="rem_w_ui")
            if st.button("저장", use_container_width=True, key="rem_save"):
                ck_set("failog_rem_enabled", "true" if en_ui else "false")
                ck_set("failog_rem_time", (t_ui or "21:30"))
                ck_set("failog_rem_win", str(int(w_ui)))
                st.success("저장됐어요.")

        weather_card(selected)

    with right:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("### Current Week")
        st.markdown(
            f"<span class='pill pill-strong'>Week</span> "
            f"<span class='pill'>{ws.isoformat()} ~ {(ws+timedelta(days=6)).isoformat()}</span>",
            unsafe_allow_html=True,
        )
        st.write("")

        wcols = st.columns(7, gap="small")
        days = week_days(ws)
        for i, d in enumerate(days):
            label = f"{korean_dow(i)}\n{d.day}"
            if wcols[i].button(label, key=f"w_{d.isoformat()}", use_container_width=True):
                st.session_state["selected_date"] = d
                st.rerun()
            if d == selected:
                wcols[i].caption("선택")

        st.markdown("<hr/>", unsafe_allow_html=True)
        st.markdown(f"#### {selected.isoformat()} ({korean_dow(selected.weekday())})")

        with st.form("plan_add_form", clear_on_submit=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                plan_text = st.text_input("계획 추가(1회성)", placeholder="예: 독서 10분 / 이메일 정리", key="plan_text_input")
            with c2:
                submitted = st.form_submit_button("추가", use_container_width=True)
            if submitted:
                add_plan_task(user_id, selected, plan_text)
                st.rerun()

        with st.expander("습관(반복) 관리", expanded=False):
            with st.form("habit_add_form", clear_on_submit=True):
                hc1, hc2 = st.columns([3, 2])
                with hc1:
                    habit_title = st.text_input("습관 이름", placeholder="예: 운동 10분", key="habit_title_input")
                with hc2:
                    dow_labels = [korean_dow(i) for i in range(7)]
                    picked = st.multiselect(
                        "반복 요일",
                        options=list(range(7)),
                        format_func=lambda x: dow_labels[x],
                        default=[0, 1, 2, 3, 4],
                        key="habit_dow_input",
                    )
                habit_submit = st.form_submit_button("습관 저장", use_container_width=True)

                if habit_submit:
                    add_habit(user_id, habit_title, picked)
                    ensure_week_habit_tasks(user_id, ws)
                    st.success("습관을 저장했어요.")
                    st.rerun()

            hdf = list_habits(user_id, active_only=False)
            if hdf.empty:
                st.markdown("<div class='small'>아직 습관이 없어요.</div>", unsafe_allow_html=True)
            else:
                for _, h in hdf.iterrows():
                    hid = int(h["id"])
                    mask = str(h["dow_mask"] or "0000000")
                    days_txt = " ".join([korean_dow(i) for i in range(7) if mask[i] == "1"]) or "—"
                    active = int(h["active"]) == 1

                    a, b, c = st.columns([6, 1, 1], gap="small")
                    with a:
                        st.write(f"• {h['title']}  ·  {days_txt}")
                    with b:
                        if st.button("ON" if active else "OFF", key=f"hab_toggle_{hid}", use_container_width=True):
                            set_habit_active(user_id, hid, not active)
                            ensure_week_habit_tasks(user_id, ws)
                            st.rerun()
                    with c:
                        if st.button("삭제", key=f"hab_del_{hid}", use_container_width=True):
                            delete_habit(user_id, hid)
                            st.success("습관을 삭제했어요.")
                            st.rerun()

        df = list_tasks_for_date(user_id, selected)
        if df.empty:
            st.markdown("<div class='small'>아직 항목이 없어요.</div>", unsafe_allow_html=True)
        else:
            for _, r in df.iterrows():
                tid = int(r["id"])
                src = r["source"]
                status = r["status"]
                text = r["text"]
                reason = r["fail_reason"] or ""

                status_icon = {"todo": "⏳", "success": "✅", "fail": "❌"}.get(status, "⏳")
                badge = "Habit" if src == "habit" else "Plan"

                st.markdown("<div class='task'>", unsafe_allow_html=True)
                top = st.columns([6, 1.2, 1.2, 1.0], gap="small")

                with top[0]:
                    st.markdown(f"**{status_icon} {text}**  <span class='pill'>{badge}</span>", unsafe_allow_html=True)
                    if status == "fail":
                        st.caption(f"실패 원인: {reason}")

                with top[1]:
                    if st.button("성공", key=f"s_{tid}", use_container_width=True):
                        update_task_status(user_id, tid, "success")
                        st.session_state.pop(f"show_fail_{tid}", None)
                        st.rerun()

                with top[2]:
                    if st.button("실패", key=f"f_{tid}", use_container_width=True):
                        st.session_state[f"show_fail_{tid}"] = True

                with top[3]:
                    if st.button("삭제", key=f"del_{tid}", use_container_width=True):
                        delete_task(user_id, tid)
                        st.session_state.pop(f"show_fail_{tid}", None)
                        st.rerun()

                if st.session_state.get(f"show_fail_{tid}", False):
                    reason_in = st.text_input("실패 원인(한 문장)", value=reason, key=f"r_{tid}")
                    a, b = st.columns([1, 4], gap="small")
                    with a:
                        if st.button("저장", key=f"save_fail_{tid}", use_container_width=True):
                            update_task_fail(user_id, tid, reason_in)
                            st.session_state[f"show_fail_{tid}"] = False
                            st.rerun()
                    with b:
                        st.caption("짧아도 좋아요. ‘무슨 조건 때문에’가 핵심이에요.")

                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
