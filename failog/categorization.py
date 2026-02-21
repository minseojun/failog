# failog/categorization.py
import json
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from failog.openai_helpers import openai_client
from failog.habits_tasks import get_tasks_range
from failog.db import conn, now_iso
from failog.dates import week_start
from failog.constants import CATEGORY_MAP_WINDOW_WEEKS


# ============================================================
# OpenAI Categorization (Dashboard)
# ============================================================
CATEGORY_SCHEMA = """
반드시 JSON만 출력.
형식:
{
  "categories": [
    {
      "name": "카테고리명(짧게)",
      "definition": "이 카테고리에 포함되는 실패 원인의 특징(1문장)",
      "examples": ["원문 예시1","원문 예시2"]
    }
  ],
  "mapping": {
    "원문 실패원인": "카테고리명",
    "또다른 원문": "카테고리명"
  }
}
규칙:
- categories 최대 __MAX_CATEGORIES__개
- mapping의 키는 반드시 입력 원문 목록에 존재하는 문자열 그대로
- mapping 값은 categories[].name 중 하나
- 애매하면 '기타' 카테고리를 하나 포함해도 됨 (그 경우 name='기타')
""".strip()


def list_recent_failure_reasons(user_id: str, weeks: int) -> List[str]:
    end = date.today()
    start = end - timedelta(days=7 * weeks - 1)
    df = get_tasks_range(user_id, start, end)
    if df.empty:
        return []
    f = df[df["status"] == "fail"].copy()
    if f.empty:
        return []
    reasons = f["fail_reason"].fillna("").map(lambda v: str(v).strip())
    reasons = reasons[reasons != ""]
    if reasons.empty:
        return []
    vc = reasons.value_counts()
    return vc.index.tolist()


def llm_build_category_map(api_key: str, model: str, reasons: List[str], max_categories: int) -> Dict[str, Any]:
    client = openai_client(api_key)

    reasons_limited = reasons[:120]
    schema = CATEGORY_SCHEMA.replace("__MAX_CATEGORIES__", str(max_categories))

    prompt = f"""
너는 사용자의 '실패 원인' 텍스트들을 비슷한 것끼리 묶어 카테고리로 분류해.
목표:
- 사용자 표현이 다양해도 의미가 비슷하면 같은 카테고리로 묶기
- 카테고리명은 짧고 직관적으로
- 전체 카테고리는 최대 {max_categories}개
- 가능한 한 '기타'는 최소화하되, 정말 애매하면 '기타'를 포함해도 됨

실패 원인 원문 목록:
{json.dumps(reasons_limited, ensure_ascii=False, indent=2)}

출력 스키마:
{schema}
""".strip()

    resp = client.chat.completions.create(
        model=model,
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
        return json.loads(m.group(0)) if m else {"categories": [], "mapping": {}}


def db_get_latest_category_map(user_id: str) -> Optional[Dict[str, Any]]:
    c = conn()
    row = c.execute(
        """
        SELECT payload_json
        FROM category_maps
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    c.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def db_save_category_map(user_id: str, payload: Dict[str, Any], window_weeks: int, max_categories: int):
    c = conn()
    c.execute(
        """
        INSERT INTO category_maps(user_id, created_at, window_weeks, max_categories, payload_json)
        VALUES (?,?,?,?,?)
        """,
        (user_id, now_iso(), int(window_weeks), int(max_categories), json.dumps(payload, ensure_ascii=False)),
    )
    c.commit()
    c.close()


def get_or_build_category_map(
    user_id: str, api_key: str, model: str, force_refresh: bool = False, max_categories: int = 7
) -> Tuple[Optional[Dict[str, Any]], str]:
    if not force_refresh:
        cached = db_get_latest_category_map(user_id)
        if cached and isinstance(cached, dict) and isinstance(cached.get("mapping", None), dict) and cached.get("mapping"):
            return cached, "캐시된 카테고리 맵을 사용 중"

    reasons = list_recent_failure_reasons(user_id, weeks=CATEGORY_MAP_WINDOW_WEEKS)
    if len(reasons) < 4:
        return None, "최근 12주 실패 원인 텍스트가 부족해요(최소 4개 필요)."

    payload = llm_build_category_map(api_key, model, reasons, max_categories=max_categories)

    mapping = payload.get("mapping", {}) if isinstance(payload, dict) else {}
    if not isinstance(mapping, dict) or len(mapping) == 0:
        return None, "카테고리 맵 생성 결과가 비어 있어요. 다시 시도해 주세요."

    db_save_category_map(user_id, payload, window_weeks=CATEGORY_MAP_WINDOW_WEEKS, max_categories=max_categories)
    return payload, "카테고리 맵을 새로 만들었어요"


def apply_category_mapping(df_fail: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    x = df_fail.copy()
    x["reason_raw"] = x["fail_reason"].fillna("").map(lambda v: str(v).strip())
    x["category"] = x["reason_raw"].map(lambda r: mapping.get(r, "기타"))
    x.loc[x["reason_raw"] == "", "category"] = "기타"
    return x


def weekly_category_trend(user_id: str, weeks: int, topk: int, mapping: Dict[str, str]) -> pd.DataFrame:
    end = date.today()
    start = end - timedelta(days=7 * weeks - 1)
    df = get_tasks_range(user_id, start, end)
    if df.empty:
        return pd.DataFrame(columns=["week", "category", "count"])

    df = df.copy()
    df["task_date"] = pd.to_datetime(df["task_date"]).dt.date
    df = df[df["status"] == "fail"].copy()
    if df.empty:
        return pd.DataFrame(columns=["week", "category", "count"])

    df = apply_category_mapping(df, mapping)
    df["week"] = df["task_date"].map(lambda d: week_start(d).isoformat())

    totals = df.groupby("category").size().sort_values(ascending=False)
    top_categories = totals.head(topk).index.tolist()

    df = df[df["category"].isin(top_categories)].copy()
    out = df.groupby(["week", "category"]).size().reset_index(name="count")
    out["count"] = out["count"].astype(int)

    weeks_sorted = sorted(df["week"].unique().tolist())
    all_rows = []
    for w in weeks_sorted:
        for cat in top_categories:
            sub = out[(out["week"] == w) & (out["category"] == cat)]
            cnt = int(sub["count"].iloc[0]) if not sub.empty else 0
            all_rows.append({"week": w, "category": cat, "count": cnt})
    return pd.DataFrame(all_rows)
