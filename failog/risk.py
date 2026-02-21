# failog/risk.py
from __future__ import annotations

import json
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
    ai_score, ai_reasons = ai_feasibility_risk(text, target_date)

    if ai_score is not None:
        final_score = max(pattern_score, ai_score)
        reasons = ai_reasons or ["AI가 실행 가능성을 평가했지만 이유를 가져오지 못했어요."]
    else:
        final_score = pattern_score
        reasons = ["최근 실패 패턴 기반 위험도입니다. (AI 평가 없음)"]

    return RiskResult(
        score=int(final_score),
        reasons=reasons,
        pattern_score=int(pattern_score),
        ai_score=ai_score,
        repeated_trigger=bool(repeated_trigger),
        stats=stats,  # ✅ screens_planner.py가 rr.stats를 쓰므로 제공
    )
