# failog/screens_failures.py
import json
from datetime import date, timedelta
from typing import Any, Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from failog.constants import (
    DASH_TREND_WEEKS,
    DASH_TOPK,
    CATEGORY_MAX,
    CATEGORY_MAP_WINDOW_WEEKS,
)
from failog.consent import consent_value
from failog.openai_helpers import effective_openai_key, effective_openai_model
from failog.habits_tasks import get_tasks_range, get_all_failures
from failog.dates import week_start, korean_dow
from failog.pdf_report import failures_by_dow, ensure_korean_font_downloaded, build_weekly_pdf_bytes
from failog.weather import geocode_city
from failog.cookies import ck_get
from failog.categorization import get_or_build_category_map, weekly_category_trend
from failog.coaching import (
    llm_weekly_reason_analysis,
    llm_overall_coaching,
    llm_chat,
)
from failog.coaching import repeated_reason_flags, normalize_reason, compute_user_signals


def screen_failures(user_id: str):
    st.markdown("## Failure Report")

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
        st.markdown(
            f"<div style='text-align:center; font-weight:800;'>{ws.isoformat()} ~ {we.isoformat()}</div>",
            unsafe_allow_html=True,
        )
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
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("### 📊 Dashboard")

        st.caption(
            f"트렌드: 최근 {DASH_TREND_WEEKS}주 · 표시: TOP {DASH_TOPK} 카테고리 · "
            f"카테고리 맵: 최근 {CATEGORY_MAP_WINDOW_WEEKS}주 기반 (최대 {CATEGORY_MAX}개)"
        )

        # Fail by DOW (this week)
        st.markdown("**이번 주 실패(요일 분포)**")
        dow_df = failures_by_dow(df)
        c_dow = (
            alt.Chart(dow_df)
            .mark_bar()
            .encode(
                x=alt.X("dow:N", sort=["월", "화", "수", "목", "금", "토", "일"], title=None),
                y=alt.Y("fail_count:Q", title=None),
                tooltip=["dow", "fail_count"],
            )
            .properties(height=160)
        )
        st.altair_chart(c_dow, use_container_width=True)

        st.markdown("<hr/>", unsafe_allow_html=True)
        st.markdown("**실패 원인 트렌드(주별, 카테고리)**")

        # Consent gate for AI features
        if not consent_value():
            st.info("AI 기능 사용 동의가 필요해요. (하단 ‘데이터/AI 안내 및 동의’에서 체크)")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        api_key = effective_openai_key()
        model = effective_openai_model()
        if not api_key:
            st.info("OpenAI 키가 설정되면 ‘카테고리 트렌드’가 표시돼요. (하단 OpenAI 설정)")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        colA, colB = st.columns([1.2, 2.8])
        with colA:
            refresh = st.button("카테고리 맵 갱신", use_container_width=True, key="cat_map_refresh")
        with colB:
            st.caption("갱신을 누르면 최근 12주 실패 원인을 다시 묶어(최대 7개) 카테고리 맵을 업데이트해요.")

        try:
            with st.spinner("카테고리 맵 확인 중..."):
                cat_map, msg = get_or_build_category_map(user_id, api_key, model, force_refresh=bool(refresh), max_categories=CATEGORY_MAX)
        except Exception as e:
            st.error(f"카테고리 맵 처리 실패: {type(e).__name__}")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        st.caption(msg)

        if not cat_map:
            st.info("카테고리 맵이 아직 없어요. 실패 원인 텍스트가 더 쌓이면 자동으로 만들 수 있어요.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        mapping = cat_map.get("mapping", {}) if isinstance(cat_map, dict) else {}
        categories = cat_map.get("categories", []) if isinstance(cat_map, dict) else []

        if isinstance(categories, list) and categories:
            with st.expander("카테고리 정의 보기", expanded=False):
                for cdef in categories[:CATEGORY_MAX]:
                    name = str(cdef.get("name", "카테고리"))
                    definition = str(cdef.get("definition", ""))
                    examples = cdef.get("examples", []) or []
                    st.markdown(f"**• {name}**")
                    if definition:
                        st.write(definition)
                    if examples:
                        st.write("- 예시:", ", ".join([str(x) for x in examples[:3]]))

        trend = weekly_category_trend(user_id, weeks=DASH_TREND_WEEKS, topk=DASH_TOPK, mapping=mapping)
        if trend.empty:
            st.info("최근 기간에 실패 원인 데이터가 부족해서 트렌드를 만들 수 없어요.")
            st.markdown("</div>", unsafe_allow_html=True)
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
        st.altair_chart(c_trend, use_container_width=True)
        st.caption("X축: 주 시작일(월요일) · Y축: 그 주에 해당 카테고리로 기록된 실패 원인 횟수(실제 횟수)")

        st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------
    # Weekly analysis / coaching
    # (변경점 #1: 주간 실패 차트 제거)
    # -------------------------
    with tab2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("### 주간 분석 / 코칭")

        # Consent gate for AI features
        if not consent_value():
            st.info("AI 기능 사용 동의가 필요해요. (하단 ‘데이터/AI 안내 및 동의’에서 체크)")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        api_key = effective_openai_key()
        model = effective_openai_model()

        st.markdown("#### 원인 주간 분석")

        weekly_reasons = [r for r in fails["fail_reason"].fillna("").tolist() if str(r).strip()]
        if not api_key:
            st.info("OpenAI 키가 설정되면 분석이 표시돼요. (하단에서 키 입력)")
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
        st.markdown("#### 맞춤형 AI코칭")

        if not api_key:
            st.info("OpenAI 키가 설정되면 코칭/챗봇이 표시돼요. (하단에서 키 입력)")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        all_fail = get_all_failures(user_id, limit=350)
        if all_fail.empty:
            st.write("아직 실패 데이터가 없어요.")
            st.markdown("</div>", unsafe_allow_html=True)
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
        st.markdown("#### 코칭 챗봇")

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

            end = date.today()
            start = end - timedelta(days=13)
            last14 = get_tasks_range(user_id, start, end)
            last14_fail = last14[last14["status"] == "fail"]
            top_reasons_14 = (
                last14_fail["fail_reason"].fillna("").map(lambda s: s.strip()).value_counts().head(6).to_dict()
                if not last14_fail.empty
                else {}
            )

            system_context = f"""
너는 FAILOG의 코칭 챗봇이야.
원칙:
- 비난/자책 유도 금지, 코칭 톤
- 실행 가능하고 현실적인 조언(작게, 구체적으로)
- 사용자의 패턴(요일/항목/plan-habit 특성/연속성)을 근거로 개인화
- 반복 실패(2주+)가 보이면, 다른 각도의 창의적 대안을 최소 1개 포함

사용자 요약:
- 최근 14일 실패 이유 상위: {json.dumps(top_reasons_14, ensure_ascii=False)}
- 최근 28일 패턴 요약: {json.dumps(signals, ensure_ascii=False)}
- 누적 실패 샘플(최근 8개): {json.dumps(items[:8], ensure_ascii=False)}
""".strip()

            try:
                assistant_text = llm_chat(api_key, model, system_context, st.session_state["chat_messages"][-14:])
            except Exception as e:
                assistant_text = f"(OpenAI 호출 오류: {type(e).__name__}) 키/모델을 확인해 주세요."

            st.session_state["chat_messages"].append({"role": "assistant", "content": assistant_text})
            with st.chat_message("assistant"):
                st.write(assistant_text)

        st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------
    # PDF report
    # -------------------------
    with tab3:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("### 🧾 Weekly PDF 리포트 (한글 폰트 포함)")

        st.caption("가장 확실한 방법: fonts/NanumGothic-Regular.ttf 를 레포에 포함하면(커밋) 네모(■) 깨짐이 100% 사라져요.")

        city = ck_get("failog_city", "").strip()
        city_label = ""
        try:
            if city:
                g = geocode_city(city)
                if g:
                    city_label = f"{g.get('name','')} · {g.get('country','')}"
        except Exception:
            city_label = city

        font_ready = ensure_korean_font_downloaded()
        if not font_ready:
            st.warning("폰트 다운로드가 막힌 환경이면 PDF 한글이 깨질 수 있어요. (레포에 폰트 파일 포함 권장)")
        else:
            st.success("PDF 한글 폰트 준비 완료")

        c1, c2, c3 = st.columns([1.1, 1.1, 2.2])
        with c1:
            target_ws = st.date_input("주 시작(월)", value=ws, key="pdf_ws")
            target_ws = week_start(target_ws)
        with c2:
            filename = st.text_input("파일명", value=f"failog_week_{target_ws.isoformat()}.pdf", key="pdf_name")
        with c3:
            st.write("")
            st.write("")
            gen = st.button("PDF 생성", use_container_width=True, key="pdf_gen")

        if gen:
            with st.spinner("PDF 생성 중..."):
                try:
                    pdf_bytes = build_weekly_pdf_bytes(user_id, target_ws, city_label=city_label)
                    st.session_state["__latest_pdf__"] = (filename, pdf_bytes)
                    st.success("PDF가 생성됐어요.")
                except Exception as e:
                    st.error(f"PDF 생성 실패: {type(e).__name__}")

        if st.session_state.get("__latest_pdf__"):
            fn, bts = st.session_state["__latest_pdf__"]
            st.download_button("PDF 다운로드", data=bts, file_name=fn, mime="application/pdf", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)
