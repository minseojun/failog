# failog/strategy.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class StrategySuggestion:
    name: str
    description: str
    texts: List[str]


def _clean_text(t: str) -> str:
    return (t or "").strip()


def suggest_strategies_for_plan(plan_text: str) -> List[StrategySuggestion]:
    """
    입력한 계획(plan_text)을 "바로 저장 가능한" 더 실행하기 쉬운 형태로 쪼개거나
    실패 위험을 낮추는 표현으로 바꾸는 전략을 제안한다.

    반환:
      List[StrategySuggestion]
      - texts: add_plan_task로 그대로 저장할 문자열 리스트
    """
    p = _clean_text(plan_text)
    if not p:
        return []

    # 아주 단순하지만 실사용에 효과적인 기본 전략들
    suggestions: List[StrategySuggestion] = []

    # 1) 최소화(MVP) 전략
    suggestions.append(
        StrategySuggestion(
            name="최소 버전(2분 시작)",
            description="오늘은 ‘완료’보다 ‘시작’을 목표로. 2분만 해도 성공 처리할 수 있게 줄여요.",
            texts=[f"{p} (2분만 시작)"],
        )
    )

    # 2) 시간/트리거 고정 전략
    suggestions.append(
        StrategySuggestion(
            name="시간 고정(캘린더 락)",
            description="언제 할지 모르면 실패 확률이 커져요. 시간을 박아 넣어서 의사결정을 줄여요.",
            texts=[f"[21:00] {p}", f"[21:10] {p} (정리/마감 3분)"],
        )
    )

    # 3) 사전 준비물/환경 세팅
    suggestions.append(
        StrategySuggestion(
            name="환경 세팅(장벽 낮추기)",
            description="실패의 대부분은 ‘시작 장벽’이에요. 준비를 태스크로 분리해요.",
            texts=[f"{p} 준비물/환경 세팅(3분)", p],
        )
    )

    # 4) If-Then 실행 장치
    suggestions.append(
        StrategySuggestion(
            name="If-Then 방어 플랜",
            description="방해요인이 생길 때 대체 행동을 정해두면 연쇄 실패를 막기 쉬워요.",
            texts=[f"If(피곤/늦음) Then: {p}는 ‘최소 버전(2분)’으로만 하기"],
        )
    )

    # 너무 길면 UX 안 좋으니 상위 4개만
    return suggestions[:4]
