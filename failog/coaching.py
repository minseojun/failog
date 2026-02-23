# failog/coaching.py
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

# OpenAI SDK
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from failog.habits_tasks import get_tasks_range, get_all_failures


# ============================================================
# OpenAI client
# ============================================================
def openai_client(api_key: str):
    if OpenAI is None:
        raise RuntimeError("openai 패키지가 설치되지 않았어요. pip install openai")
    if not (api_key or "").strip():
        raise RuntimeError("OpenAI API Key가 비어 있어요.")
    return OpenAI(api_key=(api_key or "").strip())


# ============================================================
# Coaching prompts (업그레이드)
# ============================================================
# 핵심: "패턴 → 원인 → 행동"을 자연스럽게 연결하고, 뻔한 조언(운동하세요/일찍 자세요)을 방지
BASE_COACH_PROMPT = """
너는 사용자의 '실패 기록'을 바탕으로 다음 주의 행동을 바꾸게 만드는 코치야.

목표:
- 실패를 비난하지 않는다.
- '사용자 데이터에 근거한' 공통 원인을 최대 3개로 묶는다.
- 각 원인별로 이번 주 바로 실행 가능한 "작고 구체적인 행동"을 제시한다.
- 같은 실패가 2주 이상 반복되는 원인은, 기존 조언과 결이 다른 '완전히 다른 접근'의 대안을 추가한다.

금지:
- 뻔한 상투어(의지만 가지세요/힘내세요/열심히 하세요) 금지
- 추상적 조언(관리해보세요/줄여보세요) 금지
- 사용자의 데이터 언급 없이 일반론만 말하기 금지
""".strip()

COACH_SCHEMA = """
반드시 JSON만 출력해. (설명/마크다운 금지)

형식:
{
  "top_causes":[
    {
      "cause":"원인 카테고리(짧게, 3~10자)",
      "why_this_cause":"사용자 데이터 근거 1줄 (요일/반복/원문표현/항목 유형 등 구체 단서 포함)",
      "summary":"2~4문장. 사용자 데이터 단서 2개 이상을 섞어서 '패턴→원인'을 자연스럽게 설명",
      "actionable_advice":[
        "이번 주에 바로 가능한 아주 구체적인 조언1 (1문장, 조건/시간/수치 포함 권장)",
        "조언2",
        "조언3"
      ],
      "creative_advice_when_repeated_2w":[
        "(2주+ 반복인 경우) 기존 조언과 다른 접근의 창의적 대안1",
        "대안2"
      ]
    }
  ]
}

규칙:
- top_causes 최대 3개
- 각 cause에는 actionable_advice를 2~3개만 채워라(너무 길게 금지)
- actionable_advice는 '행동 규칙' 형태를 우선: 시간 제한 / 수량 제한 / If-Then / 환경 변화 중 하나
- why_this_cause에는 사용자 데이터 단서가 반드시 1개 이상 들어가야 함(예: '최근 4주 중 월/수에 실패가 집중' 같은 표현)
- repeated_2w=true인 실패 원인이 하나라도 있으면 해당 cause의 creative_advice_when_repeated_2w는 반드시 1~2개 채워라
- 비난/자책 유도 금지
""".strip()


# ============================================================
# Utils
# ============================================================
def normalize_reason(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\s가-힣]", "", t)
    return t


def repeated_reason_flags(df_fail: pd.DataFrame) -> Dict[str, bool]:
    if df_fail.empty:
        return {}
    x = df_fail.copy()
    x["task_date"] = pd.to_datetime(x["task_date"]).dt.date
    x["rnorm"] = x["fail_reason"].fillna("").map(normalize_reason)
    flags: Dict[str, bool] = {}
    for rnorm, g in x.groupby("rnorm"):
        if not rnorm:
            continue
        dates = sorted(g["task_date"].tolist())
        if len(dates) >= 2 and (dates[-1] - dates[0]).days >= 14:
            flags[rnorm] = True
    return flags


def compute_user_signals(user_id: str, days: int = 28) -> Dict[str, Any]:
    end = date.today()
    start = end - timedelta(days=days - 1)
    df = get_tasks_range(user_id, start, end)
    if df.empty:
        return {
            "has_data": False,
            "window_days": days,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
        }

    df = df.copy()
    df["task_date"] = pd.to_datetime(df["task_date"]).dt.date
    df["dow"] = df["task_date"].map(lambda d: d.weekday())
    df["is_fail"] = df["status"].eq("fail")
    df["is_success"] = df["status"].eq("success")

    def korean_dow(i: int) -> str:
        return ["월", "화", "수", "목", "금", "토", "일"][i]

    fail_by_dow = (
        df[df["is_fail"]]
        .groupby("dow")["is_fail"]
        .sum()
        .reindex(range(7), fill_value=0)
        .to_dict()
    )
    fail_by_dow = {korean_dow(int(k)): int(v) for k, v in fail_by_dow.items()}

    top_failed = (
        df[df["is_fail"]]
        .groupby(["text", "source"])["is_fail"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    top_failed_items = [
        {"item": r["text"], "type": r["source"], "fail_count": int(r["is_fail"])}
        for _, r in top_failed.iterrows()
    ]

    reasons = df[df["is_fail"]]["fail_reason"].fillna("").map(lambda s: str(s).strip())
    top_reasons = reasons[reasons != ""].value_counts().head(10).to_dict()

    return {
        "has_data": True,
        "window_days": days,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "counts": {
            "total": int(len(df)),
            "success": int(df["is_success"].sum()),
            "fail": int(df["is_fail"].sum()),
            "todo": int((df["status"] == "todo").sum()),
        },
        "fail_by_dow": fail_by_dow,
        "top_failed_items": top_failed_items,
        "top_reasons": top_reasons,
    }


def _safe_json_loads(s: str) -> Optional[Dict[str, Any]]:
    """LLM이 JSON 외 텍스트를 섞어도 최대한 JSON만 추출해서 파싱."""
    if not s:
        return None
    s = s.strip()

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    try:
        i = s.find("{")
        j = s.rfind("}")
        if i != -1 and j != -1 and j > i:
            sub = s[i : j + 1]
            obj = json.loads(sub)
            if isinstance(obj, dict):
                return obj
    except Exception:
        return None

    return None


# ============================================================
# LLM calls
# ============================================================
def llm_weekly_reason_analysis(api_key: str, model: str, reasons: List[str]) -> Dict[str, Any]:
    client = openai_client(api_key)
    prompt = f"""
너는 사용자의 실패 이유를 읽고, '이번 주' 관점에서 공통 원인을 최대 3개로 묶어 요약해.

실패 이유 목록:
{json.dumps(reasons, ensure_ascii=False)}

출력은 JSON만.
형식:
{{
  "groups":[
    {{"cause":"원인","description":"요약 1~2문장","examples":["예시1","예시2"],"estimated_count": 0}}
  ]
}}
규칙:
- groups 최대 3개
""".strip()

    resp = client.chat.completions.create(
        model=(model or "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
    )
    text = (resp.choices[0].message.content or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        return json.loads(m.group(0)) if m else {"groups": []}


def llm_overall_coaching(
    api_key: str,
    model: str,
    fail_items: List[Dict[str, Any]],
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    """
    맞춤형 AI 코칭 (업그레이드):
    - 'why_this_cause'를 추가해 근거 1줄을 강제 → 내용 퀄리티 상승
    - 조언을 '행동 규칙' 형태로 유도 → 실용성 상승
    """
    client = openai_client(api_key)

    prompt = f"""
{BASE_COACH_PROMPT}

사용자 패턴 요약(JSON):
{json.dumps(signals, ensure_ascii=False, indent=2)}

실패 기록 샘플(JSON):
{json.dumps(fail_items, ensure_ascii=False, indent=2)}

반드시 아래 스키마를 지켜 JSON만 출력해:
{COACH_SCHEMA}
""".strip()

    resp = client.chat.completions.create(
        model=(model or "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": "You are a precise, practical coaching assistant. Output must be valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,  # 0.75 -> 0.6: 덜 흔들리고 더 일관된 조언
    )

    text = (resp.choices[0].message.content or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        return json.loads(m.group(0)) if m else {"top_causes": []}


def llm_chat(api_key: str, model: str, system_context: str, msgs: List[Dict[str, str]]) -> str:
    client = openai_client(api_key)
    resp = client.chat.completions.create(
        model=(model or "gpt-4o-mini"),
        messages=[{"role": "system", "content": system_context}] + msgs,
        temperature=0.7,
    )
    return (resp.choices[0].message.content or "").strip()


def llm_plan_alternatives(api_key: str, model: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    작성 시점 plan 대안 제시용
    """
    client = openai_client(api_key)
    prompt = f"""
너는 사용자의 계획이 실패할 위험이 높을 때, 성공 확률을 높이는 대안을 제시하는 코치야.
반드시 JSON만 출력해.

입력 컨텍스트:
{json.dumps(context, ensure_ascii=False, indent=2)}

출력 형식:
{{
  "rewrite": "원문을 더 작고 구체적으로 바꾼 1개 문장",
  "alternatives": ["대안1","대안2","대안3"],
  "if_then": ["만약 (실패조건) 이면 (대응행동)","만약 ..."]
}}
규칙:
- rewrite는 원문과 목표가 이어져야 함(목표 유지)
- alternatives는 실행 가능하고 아주 작게(수치/시간 포함 권장)
- if_then은 원인/패턴에 맞게 구체적으로
""".strip()

    resp = client.chat.completions.create(
        model=(model or "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )
    text = (resp.choices[0].message.content or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        return json.loads(m.group(0)) if m else {"rewrite": "", "alternatives": [], "if_then": []}


def llm_weekly_experiment(
    api_key: str,
    model: str,
    failure_summary: Dict[str, Any],
    top_patterns: List[Dict[str, Any]],
    signals: Dict[str, Any],
    recent_fail_texts: List[str],
) -> Dict[str, Any]:
    """
    ✅ 주간 실험 생성기 (요구사항 반영):
    - 결과 형식: 한국어로 깔끔하게
      - experiment: "이번 주 실험: ..."
      - reason: "추천 이유: ..." (한 줄)
    - JSON만 반환(파싱 안정)
    """
    client = openai_client(api_key)

    # 핵심: 출력 형태를 '딱 2필드'로 고정하고, 한국어 한 줄 이유를 강제
    prompt = f"""
너는 사용자의 실패 기록을 바탕으로 "이번 주에 시도할 실험 1개"를 추천하는 코치야.

컨텍스트:
- 최근 4주 요약:
{json.dumps(failure_summary, ensure_ascii=False)}

- 반복 패턴(top):
{json.dumps(top_patterns, ensure_ascii=False)}

- 사용자 신호:
{json.dumps(signals, ensure_ascii=False)}

- 최근 실패 원문(참고):
{json.dumps(recent_fail_texts, ensure_ascii=False)}

요구사항:
1) 실험은 반드시 1개만.
2) 실험 문장은 한국어로 짧고 명확하게(규칙/제약 형태 권장: 시간 제한, 수량 제한, If-Then, 환경 변화 중 하나).
3) 추천 이유는 한국어 "한 줄"로만. (데이터 단서 1개 이상 포함: 예 '최근 4주 중 월/수 실패가 많음', '상위 실패 원인이 ~', '특정 유형 계획이 반복 실패' 등)
4) 조언/대안 여러 개 금지. 동기부여 문장 금지.

반드시 JSON만 출력해(설명/마크다운 금지). 형식은 아래와 같아:

{{
  "experiment": "이번 주 실험: ...",
  "reason": "추천 이유: ..."
}}
""".strip()

    resp = client.chat.completions.create(
        model=(model or "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.45,  # 너무 창의적으로 튀지 않게
    )

    text = (resp.choices[0].message.content or "").strip()
    obj = _safe_json_loads(text)

    if not obj:
        return {
            "experiment": "이번 주 실험: 하루 계획을 3개 이하로 제한하기",
            "reason": "추천 이유: 최근 실패가 누적될수록 늘어나는 경향이 있어 과부하를 먼저 줄이는 게 효과적이기 때문이에요.",
            "error": "JSON parse failed",
            "raw": str(text)[:2000],
        }

    experiment = str(obj.get("experiment", "") or "").strip()
    reason = str(obj.get("reason", "") or "").strip()

    # 최소 방어
    if not experiment:
        experiment = "이번 주 실험: 하루 계획을 3개 이하로 제한하기"
    if not reason:
        reason = "추천 이유: 최근 실패 패턴에서 '과도한 계획' 신호가 보여 먼저 계획량을 줄이는 게 효과적이기 때문이에요."

    return {"experiment": experiment, "reason": reason}
