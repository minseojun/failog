# failog/risk.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple

import pandas as pd

from failog.habits_tasks import get_tasks_range


def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    # 너무 공격적으로 지우면 매칭이 깨질 수 있어 최소만
    return s


@dataclass
class RiskResult:
    score: int
    reasons: List[str]
    stats: Dict[str, Any]
    repeated_trigger: bool


def _fail_rate(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 0.0
    fail = int((df["status"] == "fail").sum())
    total = int(len(df))
    return (fail / total) if total > 0 else 0.0


def _same_text_fail_rate(df: pd.DataFrame, text: str) -> Tuple[float, int, int]:
    """최근 데이터에서 동일 plan 텍스트의 실패율"""
    if df.empty:
        return 0.0, 0, 0
    nt = _norm_text(text)
    x = df[df["source"] == "plan"].copy()
    if x.empty:
        return 0.0, 0, 0
    x["nt"] = x["text"].fillna("").map(_norm_text)
    sub = x[x["nt"] == nt]
    if sub.empty:
        return 0.0, 0, 0
    total = int(len(sub))
    fail = int((sub["status"] == "fail").sum())
    return (fail / total) if total else 0.0, fail, total


def _dow_fail_rate(df: pd.DataFrame, dow: int) -> Tuple[float, int, int]:
    """해당 요일(dow=0..6)의 실패율"""
    if df.empty:
        return 0.0, 0, 0
    x = df.copy()
    x["task_date"] = pd.to_datetime(x["task_date"]).dt.date
    x["dow"] = x["task_date"].map(lambda d: d.weekday())
    sub = x[x["dow"] == int(dow)]
    if sub.empty:
        return 0.0, 0, 0
    total = int(len(sub))
    fail = int((sub["status"] == "fail").sum())
    return (fail / total) if total else 0.0, fail, total


def repeated_plan_trigger(user_id: str, text: str, lookback_days: int = 28, threshold: int = 3) -> bool:
    """최근 N일 동일 plan 텍스트 fail 횟수 >= threshold"""
    end = date.today()
    start = end - timedelta(days=lookback_days - 1)
    df = get_tasks_range(user_id, start, end)
    if df.empty:
        return False
    nt = _norm_text(text)
    x = df[df["source"] == "plan"].copy()
    if x.empty:
        return False
    x["nt"] = x["text"].fillna("").map(_norm_text)
    sub = x[(x["nt"] == nt) & (x["status"] == "fail")]
    return int(len(sub)) >= int(threshold)


def risk_score_plan(user_id: str, target_date: date, text: str) -> RiskResult:
    """
    룰 기반 리스크 점수(0~100)
    - 최근 14일 전체 실패율
    - 해당 요일 실패율
    - 동일 텍스트(plan) 실패율 (최근 56일)
    - 반복실패 트리거(최근 28일 동일 텍스트 fail>=3)
    """
    text = (text or "").strip()
    if not text:
        return RiskResult(score=0, reasons=["입력된 계획이 비어 있어요."], stats={}, repeated_trigger=False)

    # window들
    end14 = date.today()
    start14 = end14 - timedelta(days=13)
    df14 = get_tasks_range(user_id, start14, end14)

    end56 = date.today()
    start56 = end56 - timedelta(days=55)
    df56 = get_tasks_range(user_id, start56, end56)

    overall14 = _fail_rate(df14)  # 0~1
    dow_rate, dow_fail, dow_total = _dow_fail_rate(df56 if not df56.empty else df14, target_date.weekday())

    same_rate, same_fail, same_total = _same_text_fail_rate(df56, text)

    trig = repeated_plan_trigger(user_id, text, lookback_days=28, threshold=3)

    # 점수 구성 (가중치 합 100)
    score = 0
    reasons: List[str] = []

    # 전체 컨디션(최근14일)
    score += int(round(overall14 * 40))
    if overall14 >= 0.45:
        reasons.append(f"최근 14일 전체 실패 비율이 높은 편이에요 ({overall14*100:.0f}%).")

    # 요일 패턴
    score += int(round(dow_rate * 25))
    if dow_total >= 8 and dow_rate >= 0.45:
        reasons.append(f"해당 요일에 실패가 자주 발생했어요 ({dow_fail}/{dow_total}).")

    # 동일 계획 실패율
    score += int(round(same_rate * 25))
    if same_total >= 3 and same_rate >= 0.50:
        reasons.append(f"같은 계획이 최근에 자주 실패했어요 ({same_fail}/{same_total}).")

    # 반복 트리거
    if trig:
        score += 10
        reasons.append("이 계획은 최근 28일에 반복 실패 트리거가 걸렸어요(동일 계획 실패 누적).")

    score = max(0, min(100, score))

    if not reasons:
        if score >= 70:
            reasons.append("패턴상 실패 가능성이 높아 보여요. 더 작게/더 구체적으로 바꿔보면 좋아요.")
        elif score >= 40:
            reasons.append("크게 위험하진 않지만, 성공 확률을 높이려면 범위를 조금 줄여보는 걸 추천해요.")
        else:
            reasons.append("리스크가 낮은 편이에요. 지금 형태로도 충분히 가능해 보여요.")

    stats = {
        "overall14_fail_rate": overall14,
        "dow_fail_rate": dow_rate,
        "same_plan_fail_rate": same_rate,
        "same_plan_counts": {"fail": same_fail, "total": same_total},
        "dow_counts": {"fail": dow_fail, "total": dow_total},
        "target_date": target_date.isoformat(),
    }

    return RiskResult(score=score, reasons=reasons, stats=stats, repeated_trigger=trig)
