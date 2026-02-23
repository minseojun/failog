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
# Coaching prompts (원본 그대로)
# ============================================================
BASE_COACH_PROMPT = (
    "사용자의 계획 실패 이유 목록을 분석해 공통 원인을 3가지 이내로 분류하고, "
    "각 원인에 대해 실행 가능하고 현실적인 개선 조언을 제시해줘. "
    "앞에서 했던 실패가 2주 이상 반복된다면 창의적인 다른 조언을 제시해. "
    "톤은 비난 없이 코칭 중심으로 작성해."
)

COACH_SCHEMA = """
반드시 JSON만 출력해. (설명/마크다운 금지)
형식:
{
  "top_causes":[
    {
      "cause":"원인 카테고리(짧게)",
      "summary":"사용자 데이터(항목명/요일/패턴/원문 표현)를 반영한 2~4문장",
      "actionable_advice":[
        "이번 주에 바로 가능한 아주 구체적인 조언1",
        "조언2",
        "조언3"
      ],
      "creative_advice_when_repeated_2w":[
        "(2주+ 반복이면) 완전히 다른 접근의 창의적 대안1",
        "대안2"
      ]
    }
  ]
}
규칙:
- top_causes 최대 3개
- summary/advice는 반드시 '사용자 데이터'의 구체 요소를 최소 2개 이상 언급
- actionable_advice는 '작고 구체적'
- 비난/자책 유도 금지
- repeated_2w=true 항목이 하나라도 있으면 해당 원인에는 creative_advice_when_repeated_2w를 반드시 채워라
""".strip()


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
    client = openai_client(api_key)
    prompt = f"""
{BASE_COACH_PROMPT}

사용자 패턴 요약:
{json.dumps(signals, ensure_ascii=False, indent=2)}

실패 기록 샘플:
{json.dumps(fail_items, ensure_ascii=False, indent=2)}

{COACH_SCHEMA}
""".strip()

    resp = client.chat.completions.create(
        model=(model or "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "You are a supportive coaching assistant. Output must be valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.75,
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
    context 예:
      {
        "plan_text": "...",
        "risk_score": 78,
        "risk_reasons": [...],
        "recent_stats": {...}
      }
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
- rewrite는 원문과 의미가 이어져야 함(목표 유지)
- alternatives는 실행 가능하고 아주 작게
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



def _safe_json_loads(s: str) -> Optional[Dict[str, Any]]:
    """LLM이 JSON 외 텍스트를 섞어도 최대한 JSON만 추출해서 파싱."""
    if not s:
        return None
    s = s.strip()

    # 이미 JSON처럼 보이면 그대로 시도
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 앞/뒤 잡문 제거: 첫 '{' ~ 마지막 '}' 사이만 추출
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


def llm_weekly_experiment(
    api_key: str,
    model: str,
    failure_summary: Dict[str, Any],
    top_patterns: List[Dict[str, Any]],
    signals: Dict[str, Any],
    recent_fail_texts: List[str],
) -> Dict[str, Any]:
    """
    "주간 1개 실험" 생성기.
    - 반드시 JSON만 반환하도록 강제
    - 파싱 실패 시에도 안전한 fallback 반환
    """
    # ✅ 너가 유저 메시지로 준 프롬프트를 그대로 시스템 컨텍스트로 사용
    system_prompt = f"""
You are a behavioral design AI.

Your task is to design ONE weekly experiment to reduce the user's recurring failure pattern.

Context:
- Recent failure summary (last 4 weeks):
{json.dumps(failure_summary, ensure_ascii=False)}

- Top recurring failure patterns:
{json.dumps(top_patterns, ensure_ascii=False)}

- Behavioral signals:
{json.dumps(signals, ensure_ascii=False)}

- Recent failure examples (raw texts):
{json.dumps(recent_fail_texts, ensure_ascii=False)}

Instructions:

1. Identify the single most dominant behavioral pattern.
2. Design exactly ONE experiment for the next 7 days.
3. The experiment must:
   - Be specific and immediately actionable
   - Be measurable with a clear metric
   - Reduce friction rather than increase workload
   - Focus on limiting, simplifying, or restructuring behavior
   - Not include motivational language
   - Not include multiple suggestions

4. The experiment rule must follow ONE of these formats:
   - Time restriction (e.g., "No new tasks after 9 PM")
   - Quantity limit (e.g., "Maximum 3 tasks per day")
   - If-Then trigger (e.g., "If task takes >30 min, break into 10-min blocks")
   - Environmental change (e.g., "Work only at library for deep tasks")

Return ONLY valid JSON in the following format:

{{
  "dominant_pattern": "",
  "experiment_rule": "",
  "measurement_metric": "",
  "expected_behavioral_shift": ""
}}
""".strip()

    # ✅ llm_chat이 이미 레포에서 사용 중이므로, 같은 호출 경로를 재사용
    # llm_chat(api_key, model, system_context, messages) 가 있다고 가정
    try:
        text = llm_chat(
            api_key,
            model,
            system_prompt,
            [{"role": "user", "content": "Generate the JSON now."}],
        )
    except Exception as e:
        # 호출 자체 실패
        return {
            "dominant_pattern": "unknown",
            "experiment_rule": "",
            "measurement_metric": "",
            "expected_behavioral_shift": "",
            "error": f"OpenAI call failed: {type(e).__name__}",
        }

    obj = _safe_json_loads(str(text))
    if not obj:
        return {
            "dominant_pattern": "unknown",
            "experiment_rule": "",
            "measurement_metric": "",
            "expected_behavioral_shift": "",
            "error": "JSON parse failed",
            "raw": str(text)[:4000],
        }

    # ✅ 키 보정/검증: 누락되면 빈 문자열로 채움(화면에서 오류 방지)
    out = {
        "dominant_pattern": str(obj.get("dominant_pattern", "") or "").strip(),
        "experiment_rule": str(obj.get("experiment_rule", "") or "").strip(),
        "measurement_metric": str(obj.get("measurement_metric", "") or "").strip(),
        "expected_behavioral_shift": str(obj.get("expected_behavioral_shift", "") or "").strip(),
    }

    # 최소 방어: experiment_rule이 비어 있으면 fallback
    if not out["experiment_rule"]:
        out["dominant_pattern"] = out["dominant_pattern"] or "unknown"
        out["experiment_rule"] = "Maximum 3 tasks per day"
        out["measurement_metric"] = "Days (out of 7) where tasks added <= 3"
        out["expected_behavioral_shift"] = "Reduce over-commitment by limiting daily task intake"

    return out
