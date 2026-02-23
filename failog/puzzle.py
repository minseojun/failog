# failog/puzzle.py
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Tuple

from PIL import Image

from failog.constants import KST
from failog.db import conn, now_iso


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets", "animals")

CATEGORIES = ["bunny", "guinea", "puppy", "seal"]

CATEGORY_FILES = {
    "bunny": ["bunny1.jpeg", "bunny2.jpeg", "bunny3.jpeg", "bunny4.jpeg"],
    "guinea": ["guinea1.jpeg", "guinea2.jpeg", "guinea3.jpeg"],
    "puppy": ["puppy1.jpeg", "puppy2.jpeg", "puppy3.jpeg"],
    "seal": ["seal1.jpeg", "seal2.jpeg"],
}


@dataclass
class PuzzleState:
    user_id: str
    category: str
    image_path: str
    reveal_order: List[int]      # length 16
    revealed_mask: str           # length 16, '0'/'1'
    last_award_date: Optional[str]


def _today_kst() -> date:
    return datetime.now(KST).date()


def _mask_count(mask: str) -> int:
    return sum(1 for ch in (mask or "") if ch == "1")


def _all_assets_exist(category: str) -> List[str]:
    files = CATEGORY_FILES.get(category, [])
    return [os.path.join(ASSETS_DIR, category, fn) for fn in files]


def pick_random_image_path(user_id: str, category: str) -> str:
    paths = _all_assets_exist(category)
    existing = [p for p in paths if os.path.exists(p)]
    if not existing:
        raise FileNotFoundError(
            f"assets/animals/{category} 에 이미지가 없어요. "
            f"경로 확인: {os.path.join(ASSETS_DIR, category)}"
        )

    seed = abs(hash(f"{user_id}:{category}:image")) % (2**31 - 1)
    rng = random.Random(seed)
    return rng.choice(existing)


def create_new_puzzle(user_id: str, category: str) -> PuzzleState:
    image_path = pick_random_image_path(user_id, category)

    seed = abs(hash(f"{user_id}:{category}:{image_path}:order")) % (2**31 - 1)
    rng = random.Random(seed)
    order = list(range(16))
    rng.shuffle(order)

    mask = "0" * 16
    ts = now_iso()

    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO puzzle_state
        (user_id, category, image_path, reveal_order, revealed_mask, last_award_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (user_id, category, image_path, json.dumps(order), mask, None, ts, ts),
    )
    c.commit()
    c.close()

    return PuzzleState(
        user_id=user_id,
        category=category,
        image_path=image_path,
        reveal_order=order,
        revealed_mask=mask,
        last_award_date=None,
    )


def load_puzzle_state(user_id: str) -> Optional[PuzzleState]:
    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        SELECT user_id, category, image_path, reveal_order, revealed_mask, last_award_date
        FROM puzzle_state
        WHERE user_id = ?;
        """,
        (user_id,),
    )
    row = cur.fetchone()
    c.close()

    if not row:
        return None

    order = json.loads(row[3]) if row[3] else list(range(16))
    mask = row[4] or ("0" * 16)
    return PuzzleState(
        user_id=row[0],
        category=row[1],
        image_path=row[2],
        reveal_order=order,
        revealed_mask=mask,
        last_award_date=row[5],
    )


def _save_state(ps: PuzzleState):
    ts = now_iso()
    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        UPDATE puzzle_state
        SET revealed_mask = ?, last_award_date = ?, updated_at = ?
        WHERE user_id = ?;
        """,
        (ps.revealed_mask, ps.last_award_date, ts, ps.user_id),
    )
    c.commit()
    c.close()


def user_has_activity_today(user_id: str, d: date) -> bool:
    """
    ✅ 출석/기록 기준을 'task_date=오늘'이 아니라,
    '오늘(created_at/updated_at)에 무언가 기록/수정이 있었는지'로 잡음.

    - 계획 추가: created_at 오늘
    - 성공/실패 체크: updated_at 오늘
    - 실패원인 저장: updated_at 오늘
    - (선택날짜가 과거여도) 오늘 앱에서 기록하면 출석 인정
    """
    iso = d.isoformat()

    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        SELECT COUNT(1)
        FROM tasks
        WHERE user_id = ?
          AND (
            substr(created_at, 1, 10) = ?
            OR substr(updated_at, 1, 10) = ?
          );
        """,
        (user_id, iso, iso),
    )
    n = int(cur.fetchone()[0] or 0)
    c.close()
    return n > 0


def award_piece_if_eligible(user_id: str, d: Optional[date] = None) -> Tuple[bool, str]:
    """
    ✅ 하루 1번, '오늘 활동이 있으면' 퍼즐 조각 1개 자동 공개.
    """
    d = d or _today_kst()
    today_iso = d.isoformat()

    ps = load_puzzle_state(user_id)
    if not ps:
        return (False, "퍼즐이 아직 시작되지 않았어요. (카테고리 먼저 선택)")

    if _mask_count(ps.revealed_mask) >= 16:
        return (False, "이미 퍼즐이 완성됐어요.")

    # ✅ 오늘 활동이 없으면 지급 안함
    if not user_has_activity_today(user_id, d):
        return (False, "오늘 기록/수정 활동이 아직 없어서 조각을 지급하지 않았어요.")

    # ✅ 오늘 이미 지급했으면 중복 지급 방지
    if ps.last_award_date == today_iso:
        return (False, "오늘은 이미 퍼즐 조각을 받았어요.")

    mask = list(ps.revealed_mask)
    next_idx = None
    for idx in ps.reveal_order:
        if 0 <= idx < 16 and mask[idx] == "0":
            next_idx = idx
            break

    if next_idx is None:
        return (False, "공개할 조각이 없어요(이미 다 공개된 것 같아요).")

    mask[next_idx] = "1"
    ps.revealed_mask = "".join(mask)
    ps.last_award_date = today_iso
    _save_state(ps)

    # 완성 시 보관함 저장 + 진행퍼즐 초기화
    if _mask_count(ps.revealed_mask) >= 16:
        ts = now_iso()
        c = conn()
        cur = c.cursor()
        cur.execute(
            """
            INSERT INTO puzzle_gallery(user_id, category, image_path, completed_on, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (user_id, ps.category, ps.image_path, today_iso, ts),
        )
        cur.execute("DELETE FROM puzzle_state WHERE user_id = ?;", (user_id,))
        c.commit()
        c.close()
        return (True, "퍼즐이 완성됐어요! 🎉 보관함에 저장했어요.")

    return (True, "퍼즐 조각 1개를 공개했어요! 🧩")


def get_gallery(user_id: str) -> List[dict]:
    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        SELECT category, image_path, completed_on
        FROM puzzle_gallery
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 50;
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    c.close()

    return [{"category": cat, "image_path": path, "completed_on": day} for cat, path, day in rows]


def slice_image_4x4(image_path: str, size: int = 640) -> List[Image.Image]:
    img = Image.open(image_path).convert("RGB")
    img = img.resize((size, size))
    tile = size // 4
    pieces: List[Image.Image] = []
    for r in range(4):
        for c in range(4):
            left = c * tile
            top = r * tile
            pieces.append(img.crop((left, top, left + tile, top + tile)))
    return pieces
