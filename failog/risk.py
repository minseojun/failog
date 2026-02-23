# failog/risk.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd

from failog.habits_tasks import get_tasks_range
from failog.consent import consent_value
from failog.openai_prefs import effective_openai_key, effective_openai_model
from failog.coaching import openai_client


@dataclass
class RiskResult:
    score: int
    reasons: List[str]
    pattern_score: int
    ai_score: Optional[int]
    repeated_trigger: bool
    stats: Dict[str, Any]   # ✅ screens_planner.py가 rr.stats를 쓰니까 반드시 제공


# -------------------------------------------------
# 패턴 기반 위험도
# -------------------------------------------------
def _fail_rate(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float((df["status"] == "fail").mean())


def _same_text_fail_count(df: pd.DataFrame, text: str) -> int:
    if df.empty:
        return 0
    x = df[(df["source"] == "plan") & (df["text"] == text) & (df["status"] == "fail")]
    return len(x)


def pattern_risk(user_id: str, text: str) -> tuple[int, bool, Dict[str, Any]]:
    end = date.today()
    start = end - timedelta(days=27)
    df = get_tasks_range(user_id, start, end)

    overall_fail = _fail_rate(df)
    same_fail_cnt = _same_text_fail_count(df, text)

    score = 0
    score += int(overall_fail * 40)

    if same_fail_cnt >= 3:
        score += 30

    repeated_trigger = same_fail_cnt >= 3

    stats = {
        "window_days": 28,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "overall_fail_rate": round(float(overall_fail), 3),
        "same_text_fail_count": int(same_fail_cnt),
        "total_tasks_28d": int(len(df)),
        "fail_28d": int((df["status"] == "fail").sum()) if not df.empty else 0,
        "success_28d": int((df["status"] == "success").sum()) if not df.empty else 0,
        "todo_28d": int((df["status"] == "todo").sum()) if not df.empty else 0,
    }

    return min(score, 70), repeated_trigger, stats

# -------------------------------------------------
# 규칙 기반 실행가능성(Feasibility) 위험도 보정
# -------------------------------------------------
def heuristic_feasibility_risk(plan_text: str) -> tuple[int, List[str]]:
    text = (plan_text or "").strip().lower()
    if not text:
        return 0, []

    score_floor = 0
    reasons: List[str] = []

    # 연속 시간 과다 계획 탐지 (예: 필라테스 4시간, 공부 6시간)
    hour_vals: List[float] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*시간", text):
        try:
            hour_vals.append(float(m.group(1)))
        except Exception:
            continue

    if hour_vals:
        max_hours = max(hour_vals)
        if max_hours >= 5:
            score_floor = max(score_floor, 85)
            reasons.append("하루 일정으로는 5시간 이상 연속 수행 계획이라 과부하 위험이 높아요.")
        elif max_hours >= 3:
            score_floor = max(score_floor, 70)
            reasons.append("3시간 이상 연속 수행 계획은 피로/일정 충돌로 실패 위험이 커요.")

    # 과도한 표현 탐지
    overload_tokens = ["종일", "하루종일", "밤새", "철야", "all night", "all-night"]
    if any(tok in text for tok in overload_tokens):
        score_floor = max(score_floor, 80)
        reasons.append("'종일/밤새' 같은 과도한 계획 표현이 있어 실행 가능성이 낮아요.")

    # 과도한 분량 탐지 (아주 러프한 룰)
    vol = re.search(r"(\d+)\s*(페이지|장|개|km|킬로|시간)", text)
    if vol:
        n = int(vol.group(1))
        unit = vol.group(2)
        if unit in {"페이지", "장"} and n >= 100:
            score_floor = max(score_floor, 75)
            reasons.append("하루에 처리하기엔 분량이 커서 더 작은 단위로 쪼개는 게 좋아요.")
        elif unit in {"km", "킬로"} and n >= 20:
            score_floor = max(score_floor, 80)
            reasons.append("이동/운동 거리가 커서 하루 실행 가능성이 낮아요.")

    return min(100, score_floor), reasons[:3]


# -------------------------------------------------
# AI 기반 실행가능성(Feasibility) 위험도
# -------------------------------------------------
def ai_feasibility_risk(plan_text: str, target_date: date) -> tuple[Optional[int], List[str]]:
    if not consent_value():
        return None, []

    api_key = effective_openai_key()
    model = effective_openai_model()
    if not api_key:
        return None, []

    client = openai_client(api_key)

    prompt = f"""
사용자의 오늘 날짜는 {target_date.isoformat()} 입니다.

계획: "{plan_text}"

다음을 JSON으로만 출력하세요:

{{
  "risk_score": 0~100 정수,
  "reasons": ["왜 위험한지 1~3줄"]
}}

판단 기준:
- 오늘 하루 안에 실행 가능한가?
- 물리적/시간적/경제적으로 현실적인가?
- 지나치게 추상적이거나 과도한가?
- 분해가 필요한 대규모 목표인가?

특히 "3시간 이상 연속 수행", "종일/밤샘", "과도한 분량"이면 위험도를 높게(최소 70+) 보세요.
실행 불가능하거나 비현실적이면 80 이상.
보통 난이도면 50 전후.
아주 구체적이고 현실적이면 30 이하.
"""

    try:
        resp = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = (resp.choices[0].message.content or "").strip()
        data = json.loads(content)

        score = int(data.get("risk_score", 50))
        reasons = data.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = []

        return max(0, min(100, score)), [str(x) for x in reasons][:4]
    except Exception:
        return None, []


# -------------------------------------------------
# 최종 위험도 통합
# -------------------------------------------------
def risk_score_plan(user_id: str, target_date: date, text: str) -> RiskResult:
    if not (text or "").strip():
        return RiskResult(
            score=0,
            reasons=["계획이 비어 있어요."],
            pattern_score=0,
            ai_score=None,
            repeated_trigger=False,
            stats={},
        )

    pattern_score, repeated_trigger, stats = pattern_risk(user_id, text)
    heuristic_score, heuristic_reasons = heuristic_feasibility_risk(text)
    ai_score, ai_reasons = ai_feasibility_risk(text, target_date)

    if ai_score is not None:
        final_score = max(pattern_score, heuristic_score, ai_score)
        reasons = ai_reasons or heuristic_reasons or ["AI가 실행 가능성을 평가했지만 이유를 가져오지 못했어요."]
    else:
        final_score = max(pattern_score, heuristic_score)
        reasons = heuristic_reasons or ["최근 실패 패턴 기반 위험도입니다. (AI 평가 없음)"]

    stats = {**stats, "heuristic_score": int(heuristic_score)}

    return RiskResult(
        score=int(final_score),
        reasons=reasons,
        pattern_score=int(pattern_score),
        ai_score=ai_score,
        repeated_trigger=bool(repeated_trigger),
        stats=stats,  # ✅ screens_planner.py가 rr.stats를 쓰므로 제공
    )
