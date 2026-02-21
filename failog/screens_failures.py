# failog/screens_failures.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from failog.ui import inject_css, section_title
from failog.consent import consent_value
from failog.openai_prefs import effective_openai_key, effective_openai_model

from failog.db import get_tasks_range, get_all_failures
from failog.pdf_report import failures_by_dow, ensure_korean_font_downloaded, build_weekly_pdf_bytes
from failog.categorization import get_or_build_category_map, weekly_category_trend
from failog.coaching import (
    repeated_reason_flags,
    normalize_reason,
    compute_user_signals,
    llm_weekly_reason_analysis,
    llm_overall_coaching,
    llm_chat,
)
from failog.prefs import ck_get
from failog.weather import geocode_city
from failog.date_utils import week_start, korean_dow


def _altair_gray_bg(chart: alt.Chart) -> alt.Chart:
    # 차트 배경을 강제로 연회색으로 고정
    return chart.configure(background="#f3f4f6").configure_view(fill="#f3f4f6", stroke=None)


def screen_failures(user_id: str):
    inject_css(today=date.today(), selected=date.today())

    section_title("Failure Report")

    if "fail_week_offset" not in st.session_state:
        st.session_state["fail_week_offset"] = 0

    offset = int(st.session_state["fail_week_offset"])
    base = date.today() - timedelta(days=7 * offset)
    ws = week_start(base)
    we = ws + timedelta(days=6)

    nav = st.columns([1, 3, 1])
    with nav[0]:
        if st.button("〈", use_container_width=True, key="fw_prev"):
            st.session_state["fail_week_offset"] += 1
            st.rerun()
    with nav[1]:
        section_title(f"{ws.isoformat()} ~ {we.isoformat()}")
    with nav[2]:
        if st.button("〉", use_container_width=True, key="fw_next", disabled=(offset == 0)):
            st.session_state["fail_week_offset"] = max(0, offset - 1)
            st.rerun()

    df = get_tasks_range(user_id, ws, we)
    if df.empty:
        st.info("이 주에는 기록이 없어요.")
        return

    df = df.copy()
    df["task_date"] = pd.to_datetime(df["task_date"]).dt.date
    fails = df[df["status"] == "fail"].copy()

    tab1, tab2, tab3 = st.tabs(["대시보드", "주간 분석/코칭", "PDF 리포트"])

    # -------------------------
    # Dashboard
    # -------------------------
    with tab1:
        section_title("대시보드")
        st.caption(
            "트렌드/카테고리 맵/그래프는 데이터와 동의/키 설정에 따라 표시됩니다."
        )

        section_title("이번 주 실패(요일 분포)")
        dow_df = failures_by_dow(df)
        c_dow = (
            alt.Chart(dow_df)
            .mark_bar()
            .encode(
                x=alt.X("dow:N", sort=["월", "화", "수", "목", "금", "토", "일"], title=None),
                y=alt.Y("fail_count:Q", title=None),
                tooltip=["dow", "fail_count"],
            )
            .properties(height=180)
        )
        st.altair_chart(_altair_gray_bg(c_dow), use_container_width=True)

        st.markdown("<hr/>", unsafe_allow_html=True)
        section_title("실패 원인 트렌드(주별, 카테고리)")

        if not consent_value():
            st.info("AI 기능 사용 동의가 필요해요. (Planner 화면 하단에서 동의 가능)")
            return

        api_key = effective_openai_key()
        model = effective_openai_model()
        if not api_key:
            st.info("OpenAI 키가 설정되면 ‘카테고리 트렌드’가 표시돼요. (Planner 화면에서 설정)")
            return

        colA, colB = st.columns([1.2, 2.8])
        with colA:
            refresh = st.button("카테고리 맵 갱신", use_container_width=True, key="cat_map_refresh")
        with colB:
            st.caption("갱신을 누르면 최근 실패 원인을 다시 묶어 카테고리 맵을 업데이트해요.")

        try:
            with st.spinner("카테고리 맵 확인 중..."):
                cat_map, msg = get_or_build_category_map(user_id, api_key, model, force_refresh=bool(refresh))
        except Exception as e:
            st.error(f"카테고리 맵 처리 실패: {type(e).__name__}")
            return

        st.caption(msg)

        if not cat_map:
            st.info("카테고리 맵이 아직 없어요. 실패 원인 텍스트가 더 쌓이면 만들 수 있어요.")
            return

        mapping = cat_map.get("mapping", {}) if isinstance(cat_map, dict) else {}
        categories = cat_map.get("categories", []) if isinstance(cat_map, dict) else []

        if isinstance(categories, list) and categories:
            with st.expander("카테고리 정의 보기", expanded=False):
                for cdef in categories:
                    name = str(cdef.get("name", "카테고리"))
                    definition = str(cdef.get("definition", ""))
                    examples = cdef.get("examples", []) or []
                    st.markdown(f"**• {name}**")
                    if definition:
                        st.write(definition)
                    if examples:
                        st.write("- 예시:", ", ".join([str(x) for x in examples[:3]]))

        trend = weekly_category_trend(user_id, weeks=8, topk=6, mapping=mapping)
        if trend.empty:
            st.info("최근 기간에 실패 원인 데이터가 부족해서 트렌드를 만들 수 없어요.")
            return

        y_axis = alt.Axis(title="실패 횟수", tickMinStep=1)
        c_trend = (
            alt.Chart(trend)
            .mark_line(point=True)
            .encode(
                x=alt.X("week:N", title="주 시작일(월)", sort=sorted(trend["week"].unique().tolist())),
                y=alt.Y("count:Q", title="실패 횟수", axis=y_axis),
                color=alt.Color("category:N", title="카테고리"),
                tooltip=["week", "category", "count"],
            )
            .properties(height=260)
        )
        st.altair_chart(_altair_gray_bg(c_trend), use_container_width=True)

    # -------------------------
    # Weekly analysis / coaching
    # -------------------------
    with tab2:
        section_title("주간 분석/코칭")

        if not consent_value():
            st.info("AI 기능 사용 동의가 필요해요. (Planner 화면 하단에서 동의 가능)")
            return

        api_key = effective_openai_key()
        model = effective_openai_model()

        section_title("원인 주간 분석")

        weekly_reasons = [r for r in fails["fail_reason"].fillna("").tolist() if str(r).strip()]
        if not api_key:
            st.info("OpenAI 키가 설정되면 분석이 표시돼요. (Planner 화면에서 키 입력)")
        elif len(weekly_reasons) == 0:
            st.write("이번 주에는 실패 원인 입력이 아직 없어요.")
        else:
            if st.button("분석 생성/갱신", use_container_width=True, key="weekly_analyze"):
                try:
                    st.session_state["weekly_analysis"] = llm_weekly_reason_analysis(api_key, model, weekly_reasons)
                except Exception as e:
                    st.error(f"분석 생성 실패: {type(e).__name__}")

            analysis = st.session_state.get("weekly_analysis")
            if analysis and isinstance(analysis, dict):
                groups = analysis.get("groups", []) or []
                for g in groups[:3]:
                    with st.container(border=True):
                        st.markdown(f"**{g.get('cause','원인')}**  ·  ~{g.get('estimated_count',0)}회")
                        st.write(g.get("description", ""))
                        for s in (g.get("examples") or [])[:3]:
                            st.write(f"- {s}")

        st.markdown("<hr/>", unsafe_allow_html=True)
        section_title("맞춤형 AI 코칭")

        if not api_key:
            st.info("OpenAI 키가 설정되면 코칭/챗봇이 표시돼요. (Planner 화면에서 키 입력)")
            return

        all_fail = get_all_failures(user_id, limit=350)
        if all_fail.empty:
            st.write("아직 실패 데이터가 없어요.")
            return

        flags = repeated_reason_flags(all_fail)
        items: List[Dict[str, Any]] = []
        for _, r in all_fail.head(90).iterrows():
            reason = str(r["fail_reason"] or "")
            rnorm = normalize_reason(reason)
            items.append(
                {
                    "date": str(r["task_date"]),
                    "task": str(r["text"]),
                    "type": str(r["source"]),
                    "reason": reason,
                    "repeated_2w": bool(flags.get(rnorm, False)),
                }
            )

        signals = compute_user_signals(user_id, days=28)

        if st.button("코칭 생성/갱신", use_container_width=True, key="overall_coach_btn"):
            try:
                st.session_state["overall_coach"] = llm_overall_coaching(api_key, model, items, signals)
            except Exception as e:
                st.error(f"코칭 생성 실패: {type(e).__name__}")

        coach = st.session_state.get("overall_coach")
        if coach and isinstance(coach, dict):
            top = coach.get("top_causes", []) or []
            if not top:
                st.caption("코칭 결과가 비어 있어요. 다시 생성해보세요.")
            for i, c in enumerate(top[:3], start=1):
                with st.container(border=True):
                    st.markdown(f"**{i}) {c.get('cause','원인')}**")
                    st.write(c.get("summary", ""))
                    st.markdown("**실행 조언**")
                    for tip in (c.get("actionable_advice") or [])[:3]:
                        st.write(f"- {tip}")
                    creative = c.get("creative_advice_when_repeated_2w") or []
                    if creative:
                        st.markdown("**2주+ 반복이면: 창의적 대안**")
                        for tip in creative[:3]:
                            st.write(f"- {tip}")
        else:
            st.caption("‘코칭 생성/갱신’을 눌러 코칭을 받아보세요.")

        st.markdown("<hr/>", unsafe_allow_html=True)
        section_title("코칭 챗봇")

        if "chat_messages" not in st.session_state:
            st.session_state["chat_messages"] = []

        for m in st.session_state["chat_messages"]:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        user_msg = st.chat_input("메시지를 입력하세요")
        if user_msg:
            st.session_state["chat_messages"].append({"role": "user", "content": user_msg})
            with st.chat_message("user"):
                st.write(user_msg)

            end = date.today
