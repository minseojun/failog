# failog/screens_planner.py
from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

from failog.constants import KST
from failog.ui import inject_css

from failog.date_utils import month_grid, korean_dow, week_start
from failog.db import (
    add_plan_task,
    list_habits,
    add_habit,
    set_habit_active,
    delete_habit,
    ensure_week_habit_tasks,
    list_tasks_for_date,
    update_task_status,
    update_task_fail,
    delete_task,
    count_today_todos,
    get_habit_task_for_date,
)
from failog.prefs import ck_get, ck_set
from failog.reminder import parse_hhmm, should_remind
from failog.weather import weather_card

from failog.risk import risk_score_plan

from failog.consent import consent_value
from failog.openai_prefs import effective_openai_key, effective_openai_model
from failog.coaching import llm_plan_alternatives

# ✅ 퍼즐 자동 지급
from failog.puzzle import award_piece_if_eligible


def _maybe_award_puzzle(user_id: str, selected: date):
    """오늘 날짜에 기록을 남긴 경우 자동으로 퍼즐 조각 지급."""
    today = datetime.now(KST).date()
    if selected != today:
        return
    try:
        awarded, msg = award_piece_if_eligible(user_id, today)
        if awarded:
            st.toast("🧩 퍼즐 조각 1개가 공개됐어요!", icon="🧩")
    except Exception:
        # 퍼즐 기능이 아직 시작되지 않은 유저도 있으니 조용히 무시(에러로 앱 죽이지 않기)
        pass


def screen_planner(user_id: str):
    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = date.today()
    selected: date = st.session_state["selected_date"]

    inject_css(today=date.today(), selected=selected)

    st.markdown("<div class='section-title tight'>Planner</div>", unsafe_allow_html=True)

    if st_autorefresh is not None:
        st_autorefresh(interval=60_000, key="auto_refresh_planner")

    ws = week_start(selected)
    ensure_week_habit_tasks(user_id, ws)

    # Reminder settings
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

    left, right = st.columns([1.35, 1.65], gap="large")

    # =========================
    # LEFT
    # =========================
    with left:
        with st.container(border=True):
            st.markdown("<div class='section-title'>Month</div>", unsafe_allow_html=True)

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
                    f"<div style='text-align:center; font-weight:900; font-size:1.05rem;'>{y}.{m:02d}</div>",
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
                "<div class='cal-weekdays'>"
                + "".join([f"<div>{k}</div>" for k in ["월", "화", "수", "목", "금", "토", "일"]])
                + "</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div class='cal-grid'>", unsafe_allow_html=True)

            grid = month_grid(y, m)
            for row in grid:
                cols = st.columns(7, gap="small")
                for i, d in enumerate(row):
                    if d is None:
                        cols[i].markdown("<div style='height:38px;'></div>", unsafe_allow_html=True)
                        continue

                    label = str(d.day)
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

        with st.container(border=True):
            weather_card(selected)

    # =========================
    # RIGHT
    # =========================
    with right:
        with st.container(border=True):
            st.markdown(
                f"<div class='section-title'>"
                f"{selected.isoformat()} ({korean_dow(selected.weekday())})"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Plan add + Risk preview
            with st.form("plan_add_form", clear_on_submit=False):
                c1, c2, c3 = st.columns([4, 1.2, 1.2])
                with c1:
                    plan_text = st.text_input(
                        "계획 추가(1회성)",
                        placeholder="예: 독서 10분 / 이메일 정리",
                        key="plan_text_input",
                    )
                with c2:
                    preview = st.form_submit_button("위험도", use_container_width=True)
                with c3:
                    submitted = st.form_submit_button("추가", use_container_width=True)

            if preview:
                rr = risk_score_plan(user_id, selected, plan_text)
                st.session_state["__plan_risk__"] = {
                    "text": plan_text,
                    "date": selected.isoformat(),
                    "score": int(getattr(rr, "score", 0) or 0),
                    "reasons": getattr(rr, "reasons", []) or [],
                    "stats": getattr(rr, "stats", {}) or {},
                    "trigger": bool(getattr(rr, "repeated_trigger", False)),
                }
                st.session_state.pop("__ai_plan_alt__", None)

            pr = st.session_state.get("__plan_risk__")
            if pr:
                if (pr.get("text") or "").strip() != (plan_text or "").strip() or pr.get("date") != selected.isoformat():
                    st.session_state.pop("__plan_risk__", None)
                    st.session_state.pop("__ai_plan_alt__", None)
                    pr = None

            if pr:
                st.markdown("<hr/>", unsafe_allow_html=True)
                st.write(f"**위험도 점수: {pr['score']}/100**")

                # AI 대안(Rewrite 중심)
                if consent_value():
                    api_key = effective_openai_key()
                    model = effective_openai_model()
                    if api_key:
                        if st.button("AI Rewrite 받기", use_container_width=True, key="ai_alt_btn"):
                            ctx = {
                                "plan_text": (plan_text or "").strip(),
                                "risk_score": int(pr["score"]),
                                "risk_reasons": pr.get("reasons", []),
                                "recent_stats": pr.get("stats", {}),
                            }
                            try:
                                with st.spinner("AI Rewrite 생성 중..."):
                                    out = llm_plan_alternatives(api_key, model, ctx)
                                st.session_state["__ai_plan_alt__"] = out
                            except Exception as e:
                                st.error(f"AI Rewrite 생성 실패: {type(e).__name__}")

                out = st.session_state.get("__ai_plan_alt__")
                if out:
                    with st.container(border=True):
                        rw = (out.get("rewrite") or "").strip()
                        if rw:
                            st.write("**AI rewrite(추천 1개)**")
                            st.write(f"- {rw}")
                            if st.button(
                                "Rewrite로 저장",
                                use_container_width=True,
                                key=f"save_ai_rewrite_{selected.isoformat()}",
                            ):
                                add_plan_task(user_id, selected, rw)
                                _maybe_award_puzzle(user_id, selected)  # ✅ 저장하면 자동 지급
                                st.session_state.pop("__plan_risk__", None)
                                st.session_state.pop("__ai_plan_alt__", None)
                                st.success("Rewrite로 저장했어요.")
                                st.rerun()

            # 그냥 추가(원문 저장)
            if submitted:
                add_plan_task(user_id, selected, plan_text)
                _maybe_award_puzzle(user_id, selected)  # ✅ 기록 추가하면 자동 지급
                st.session_state.pop("__plan_risk__", None)
                st.session_state.pop("__ai_plan_alt__", None)
                st.rerun()

            # Habit manager
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
                        ensure_week_habit_tasks(user_id, week_start(selected))
                        _maybe_award_puzzle(user_id, selected)  # ✅ 오늘 습관 추가도 “기록”으로 인정
                        st.success("습관을 저장했어요.")
                        st.rerun()

                hdf = list_habits(user_id, active_only=False)
                if hdf.empty:
                    st.markdown("<div class='small'>아직 습관이 없어요.</div>", unsafe_allow_html=True)
                else:
                    for _, h in hdf.iterrows():
                        hid = int(h["id"])
                        title = str(h["title"])
                        mask = str(h["dow_mask"] or "0000000")
                        active = int(h["active"]) == 1
                        days_txt = " ".join([korean_dow(i) for i in range(7) if len(mask) == 7 and mask[i] == "1"]) or "—"

                        st.markdown("<hr/>", unsafe_allow_html=True)
                        st.markdown(f"**{title}**  ·  {days_txt}")

                        a, b, c = st.columns([1, 1, 1], gap="small")
                        with a:
                            if st.button("ON" if active else "OFF", key=f"hab_toggle_{hid}", use_container_width=True):
                                set_habit_active(user_id, hid, not active)
                                ensure_week_habit_tasks(user_id, week_start(selected))
                                st.rerun()
                        with b:
                            if st.button("삭제", key=f"hab_del_{hid}", use_container_width=True):
                                delete_habit(user_id, hid)
                                st.success("습관을 삭제했어요.")
                                st.rerun()
                        with c:
                            st.write("")

                        info = get_habit_task_for_date(user_id, selected, hid)
                        if info:
                            task_id, t_status, t_reason = info
                            st.caption(f"선택 날짜 상태: {t_status}")

                            x1, x2, x3 = st.columns([1, 1, 1], gap="small")
                            with x1:
                                if st.button("성공", key=f"hab_s_{task_id}", use_container_width=True):
                                    update_task_status(user_id, task_id, "success")
                                    _maybe_award_puzzle(user_id, selected)  # ✅ 성공 체크도 기록으로 인정
                                    st.session_state.pop(f"hab_show_fail_{task_id}", None)
                                    st.rerun()
                            with x2:
                                if st.button("실패", key=f"hab_f_{task_id}", use_container_width=True):
                                    st.session_state[f"hab_show_fail_{task_id}"] = True
                            with x3:
                                if st.button("삭제", key=f"hab_del_task_{task_id}", use_container_width=True):
                                    delete_task(user_id, task_id)
                                    st.session_state.pop(f"hab_show_fail_{task_id}", None)
                                    st.rerun()

                            if st.session_state.get(f"hab_show_fail_{task_id}", False):
                                r_in = st.text_input("실패 원인", value=t_reason, key=f"hab_reason_{task_id}")
                                y1, y2 = st.columns([1, 4], gap="small")
                                with y1:
                                    if st.button("원인 저장", key=f"hab_reason_save_{task_id}", use_container_width=True):
                                        update_task_fail(user_id, task_id, r_in)
                                        _maybe_award_puzzle(user_id, selected)  # ✅ 원인 기록도 기록으로 인정
                                        st.session_state[f"hab_show_fail_{task_id}"] = False
                                        st.rerun()
                                with y2:
                                    st.caption("짧아도 좋아요. ‘무슨 조건 때문에’가 핵심이에요.")
                        else:
                            st.caption("이 날짜에는 이 습관이 생성되지 않아요. (선택한 요일이 아닐 수 있어요)")

            st.markdown("<hr/>", unsafe_allow_html=True)

            df = list_tasks_for_date(user_id, selected)
            if df.empty:
                st.markdown("<div class='small'>아직 항목이 없어요.</div>", unsafe_allow_html=True)
            else:
                for _, r in df.iterrows():
                    tid = int(r["id"])
                    src = str(r["source"])
                    status = str(r["status"])
                    text = str(r["text"])
                    reason = str(r["fail_reason"] or "")

                    status_icon = {"todo": "⏳", "success": "✅", "fail": "❌"}.get(status, "⏳")
                    badge = "Habit" if src == "habit" else "Plan"

                    st.markdown("<div class='task'>", unsafe_allow_html=True)

                    top = st.columns([6, 1.2, 1.2, 1.2], gap="small")
                    with top[0]:
                        st.markdown(f"**{status_icon} {text}**  ({badge})")
                        if status == "fail" and reason.strip():
                            st.caption(f"실패 원인: {reason}")

                    with top[1]:
                        if st.button("성공", key=f"s_{tid}", use_container_width=True):
                            update_task_status(user_id, tid, "success")
                            _maybe_award_puzzle(user_id, selected)  # ✅ 성공 체크도 기록 인정
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
                                _maybe_award_puzzle(user_id, selected)  # ✅ 원인 저장도 기록 인정
                                st.session_state[f"show_fail_{tid}"] = False
                                st.rerun()
                        with b:
                            st.caption("짧아도 좋아요. ‘무슨 조건 때문에’가 핵심이에요.")

                    st.markdown("</div>", unsafe_allow_html=True)
