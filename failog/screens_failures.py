# failog/screens_failures.py
from __future__ import annotations

from datetime import date, timedelta
import json

import altair as alt
import streamlit as st

from failog.date_utils import week_start
from failog.ui import section_title

# DB / data
from failog.habits_tasks import get_tasks_range, get_all_failures

# PDF
from failog.pdf_report import failures_by_dow, ensure_korean_font_downloaded, build_weekly_pdf_bytes

# Categorization
from failog.categorization import get_or_build_category_map, weekly_category_trend

# Consent / OpenAI prefs
from failog.consent import consent_value
from failog.openai_prefs import effective_openai_key, effective_openai_model

# LLM functions
from failog.coaching import llm_weekly_reason_analysis, llm_overall_coaching, llm_chat
from failog.coaching import normalize_reason, repeated_reason_flags, compute_user_signals

from failog.coaching import llm_weekly_experiment

# misc
from failog.prefs import ck_get

# pdf city label용 (있으면)
try:
    from failog.weather import geocode_city
except Exception:
    geocode_city = None


def screen_failures(user_id: str):
    # ✅ 요청: "Failure Report" 큰 제목 삭제 -> st.markdown("## Failure Report") 제거

    # ✅ failure report 화면에서만 추가 CSS 오버라이드:
    # - 탭 아래 검정 라인 제거
    # - 상단 날짜 네비(화살표/날짜박스) 더 작게 + 가운데 정렬 보장
    st.markdown(
        """
<style>
/* 탭 아래 길게 보이는 검정 라인 제거(이 화면에서만) */
[data-testid="stTabs"] [data-baseweb="tab-border"] {
  background: transparent !important;
}

/* 상단 주 이동 UI */
.small-nav {
  margin-top: 2px;
  margin-bottom: 10px;
}
.date-box {
  display: inline-block;
  padding: 6px 10px;            /* ✅ 조금 더 작게 */
  border: 1px solid rgba(17,17,17,0.55);
  background: #f3f4f6;
  font-weight: 900;
  font-size: 0.98rem;           /* ✅ 조금 더 작게 */
  line-height: 1.1;
  text-align: center;           /* ✅ 날짜 중앙 */
  width: 100%;                  /* ✅ column 안에서 정중앙 */
  box-sizing: border-box;
}
</style>
""",
        unsafe_allow_html=True,
    )

    if "fail_week_offset" not in st.session_state:
        st.session_state["fail_week_offset"] = 0

    offset = int(st.session_state["fail_week_offset"])
    base = date.today() - timedelta(days=7 * offset)
    ws = week_start(base)
    we = ws + timedelta(days=6)

    # ✅ 상단 주 이동 UI: 날짜 가운데 정렬 + 박스/버튼 작게
    st.markdown("<div class='small-nav'>", unsafe_allow_html=True)
    nav = st.columns([1.1, 5.4, 1.1], gap="large")
    with nav[0]:
        if st.button("〈", use_container_width=True, key="fw_prev"):
            st.session_state["fail_week_offset"] += 1
            st.rerun()
    with nav[1]:
        st.markdown(
            f"<div class='date-box'>{ws.isoformat()} ~ {we.isoformat()}</div>",
            unsafe_allow_html=True,
        )
    with nav[2]:
        if st.button("〉", use_container_width=True, key="fw_next", disabled=(offset == 0)):
            st.session_state["fail_week_offset"] = max(0, offset - 1)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    df = get_tasks_range(user_id, ws, we)
    if df.empty:
        st.info("이 주에는 기록이 없어요.")
        return

    df = df.copy()
    fails = df[df["status"] == "fail"].copy()

    tab1, tab2, tab3 = st.tabs(["대시보드", "주간 분석/코칭", "PDF 리포트"])

    # -------------------------
    # Dashboard
    # -------------------------
    with tab1:
        # 그래프 제목을 섹션 타이틀로(연회색 박스 + 볼드)
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
        st.altair_chart(c_dow, use_container_width=True)

        st.markdown("<hr/>", unsafe_allow_html=True)

        section_title("실패 원인 트렌드(주별, 카테고리)")

        # Consent gate
        if not consent_value():
            st.info("AI 기능 사용 동의가 필요해요. (Planner 화면 하단에서 동의)")
            return

        api_key = effective_openai_key()
        model = effective_openai_model()
        if not api_key:
            st.info("OpenAI 키가 설정되면 트렌드가 표시돼요. (Planner 화면 하단 OpenAI 설정)")
            return

        colA, colB = st.columns([1.2, 2.8])
        with colA:
            refresh = st.button("카테고리 맵 갱신", use_container_width=True, key="cat_map_refresh")
        with colB:
            st.caption("최근 12주 실패 원인을 다시 묶어(최대 7개) 카테고리 맵을 업데이트해요.")

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
                for cdef in categories[:7]:
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
            .properties(height=280)
        )
        st.altair_chart(c_trend, use_container_width=True)
        st.caption("X축: 주 시작일(월요일) · Y축: 그 주에 해당 카테고리로 기록된 실패 횟수")

    # -------------------------
    # Weekly analysis / coaching
    # -------------------------
    with tab2:
        if not consent_value():
            st.info("AI 기능 사용 동의가 필요해요. (Planner 화면 하단에서 동의)")
            return

        api_key = effective_openai_key()
        model = effective_openai_model()
        if not api_key:
            st.info("OpenAI 키가 설정되면 분석/코칭이 표시돼요. (Planner 화면 하단 OpenAI 설정)")
            return
            
 # --- 주간 1개 실험 (Behavioral Experiment) ---
        st.markdown("<hr/>", unsafe_allow_html=True)
        section_title("주간 1개 실험 (7일)")

        end4 = ws + timedelta(days=6)
        start4 = ws - timedelta(days=27)  # 4주(28일) 범위
        last4 = get_tasks_range(user_id, start4, end4)
        last4_fail = last4[last4["status"] == "fail"].copy()

        recent_texts = (
            last4_fail["fail_reason"].fillna("").map(lambda s: str(s).strip()).tolist()
            if not last4_fail.empty
            else []
        )
        recent_texts = [t for t in recent_texts if t][:24]  # 너무 길면 비용/품질 떨어져서 컷

        failure_summary = {
            "range": {"start": start4.isoformat(), "end": end4.isoformat()},
            "total_tasks": int(len(last4)),
            "total_failures": int(len(last4_fail)),
            "top_fail_reasons": (
                last4_fail["fail_reason"].fillna("").map(lambda s: str(s).strip()).value_counts().head(6).to_dict()
                if not last4_fail.empty
                else {}
            ),
        }

        top_patterns = []
        if not last4_fail.empty:
            vc = last4_fail["fail_reason"].fillna("").map(lambda s: str(s).strip()).value_counts().head(5)
            for reason, cnt in vc.items():
                if reason:
                    top_patterns.append({"pattern": reason, "count": int(cnt)})

        signals_28 = compute_user_signals(user_id, days=28)

        if st.button("주간 실험 생성/갱신", use_container_width=True, key="weekly_exp_btn"):
            try:
                with st.spinner("주간 실험 설계 중..."):
                    exp = llm_weekly_experiment(
                        api_key=api_key,
                        model=model,
                        failure_summary=failure_summary,
                        top_patterns=top_patterns,
                        signals=signals_28,
                        recent_fail_texts=recent_texts,
                    )
                st.session_state["weekly_experiment"] = exp
            except Exception as e:
                st.error(f"주간 실험 생성 실패: {type(e).__name__}")

        exp = st.session_state.get("weekly_experiment")
        if exp and isinstance(exp, dict):
            with st.container(border=True):
                st.markdown(f"**dominant_pattern**: {exp.get('dominant_pattern','')}")
                st.markdown(f"**experiment_rule**: {exp.get('experiment_rule','')}")
                st.markdown(f"**measurement_metric**: {exp.get('measurement_metric','')}")
                st.markdown(f"**expected_behavioral_shift**: {exp.get('expected_behavioral_shift','')}")

                if exp.get("error"):
                    st.caption(f"(debug) {exp.get('error')}")
        else:
            st.caption("버튼을 누르면 다음 7일 동안 적용할 ‘단 하나의 규칙’이 생성돼요.")
            
        # --- 원인 주간 분석 (버튼 누르면 바로 생성/갱신) ---
        weekly_reasons = [r for r in fails["fail_reason"].fillna("").tolist() if str(r).strip()]
        if len(weekly_reasons) == 0:
            st.write("이번 주에는 실패 원인 입력이 아직 없어요.")
        else:
            if st.button("원인 주간 분석 생성/갱신", use_container_width=True, key="weekly_analyze"):
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

        # --- 맞춤형 AI 코칭 (버튼 누르면 바로 생성/갱신) ---
        all_fail = get_all_failures(user_id, limit=350)
        if all_fail.empty:
            st.write("아직 실패 데이터가 없어요.")
            return

        flags = repeated_reason_flags(all_fail)
        items = []
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

        if st.button("맞춤형 AI 코칭 생성/갱신", use_container_width=True, key="overall_coach_btn"):
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
            st.caption("버튼을 눌러 코칭을 받아보세요.")

        st.markdown("<hr/>", unsafe_allow_html=True)

        # --- 코칭 챗봇 ---
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

    # -------------------------
    # PDF report
    # -------------------------
    with tab3:
        # 빈화면 이슈 방지: 항상 안내 먼저 출력
        st.caption("주간 PDF 리포트를 생성하고 다운로드할 수 있어요. (한글 폰트 포함)")

        city = ck_get("failog_city", "").strip()
        city_label = ""
        try:
            if city and geocode_city is not None:
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
