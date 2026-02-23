# failog/puzzle.py
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

from failog.db import conn, now_iso

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "animals"  # /mount/src/failog/assets/animals


CATEGORIES = ["bunny", "guinea", "puppy", "seal"]


def _list_category_images(category: str) -> List[Path]:
    """
    ✅ 너 레포 구조(assets/animals/bunny1.jpeg ...)에 맞춰서
    prefix로 파일을 고른다.
    """
    category = (category or "").strip().lower()
    if category not in CATEGORIES:
        return []

    if not ASSETS_DIR.exists():
        return []

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    imgs = []
    for p in ASSETS_DIR.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        # bunny1.jpeg 같은 prefix 매칭
        if p.name.lower().startswith(category):
            imgs.append(p)

    imgs.sort()
    return imgs


def init_puzzle_tables():
    c = conn()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_progress (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          category TEXT NOT NULL,
          image_file TEXT NOT NULL,
          order_json TEXT NOT NULL,
          revealed_count INTEGER NOT NULL DEFAULT 0,
          last_reward_date TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(user_id)
        );
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_gallery (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          category TEXT NOT NULL,
          image_file TEXT NOT NULL,
          completed_at TEXT NOT NULL
        );
        """
    )
    c.commit()
    c.close()


def get_or_create_progress(user_id: str, category: str) -> Tuple[Optional[dict], str]:
    """
    선택한 category로 퍼즐 진행상태를 보장해서 가져온다.
    - 이미 progress가 있으면 그걸 반환
    - 없으면 이미지 랜덤 선택 + 공개순서 랜덤 생성 후 생성
    """
    category = (category or "").strip().lower()
    if category not in CATEGORIES:
        return None, "카테고리가 올바르지 않아요."

    imgs = _list_category_images(category)
    if not imgs:
        return None, f"assets/animals 에서 '{category}*.jpeg' 이미지를 찾지 못했어요."

    c = conn()
    row = c.execute(
        "SELECT user_id, category, image_file, order_json, revealed_count, last_reward_date FROM puzzle_progress WHERE user_id=?",
        (user_id,),
    ).fetchone()

    if row:
        progress = {
            "user_id": row[0],
            "category": row[1],
            "image_file": row[2],
            "order": json.loads(row[3]),
            "revealed_count": int(row[4]),
            "last_reward_date": row[5],
        }
        c.close()
        return progress, "OK"

    # 없으면 새로 생성
    chosen = random.choice(imgs)
    order = list(range(16))
    random.shuffle(order)

    c.execute(
        """
        INSERT INTO puzzle_progress(user_id, category, image_file, order_json, revealed_count, last_reward_date, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            user_id,
            category,
            str(chosen),
            json.dumps(order, ensure_ascii=False),
            0,
            None,
            now_iso(),
            now_iso(),
        ),
    )
    c.commit()
    c.close()

    progress = {
        "user_id": user_id,
        "category": category,
        "image_file": str(chosen),
        "order": order,
        "revealed_count": 0,
        "last_reward_date": None,
    }
    return progress, "OK"


def set_category(user_id: str, category: str) -> Tuple[Optional[dict], str]:
    """
    카테고리 바꾸면 진행은 새로 시작(보상 컨셉상 자연스러움).
    """
    category = (category or "").strip().lower()
    imgs = _list_category_images(category)
    if not imgs:
        return None, f"assets/animals 에서 '{category}*.jpeg' 이미지를 찾지 못했어요."

    chosen = random.choice(imgs)
    order = list(range(16))
    random.shuffle(order)

    c = conn()
    c.execute("DELETE FROM puzzle_progress WHERE user_id=?", (user_id,))
    c.execute(
        """
        INSERT INTO puzzle_progress(user_id, category, image_file, order_json, revealed_count, last_reward_date, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (user_id, category, str(chosen), json.dumps(order, ensure_ascii=False), 0, None, now_iso(), now_iso()),
    )
    c.commit()
    c.close()

    return get_or_create_progress(user_id, category)


def _has_user_logged_today(user_id: str) -> bool:
    """
    ✅ '오늘 기록 남김' 판정(자동 지급용)
    - 오늘 날짜(task_date=today)에
      - plan 항목이 하나라도 있거나
      - habit/plan 중 success/fail로 체크한 게 하나라도 있으면 True
    """
    today = date.today().isoformat()
    c = conn()
    row = c.execute(
        """
        SELECT COUNT(*)
        FROM tasks
        WHERE user_id=?
          AND task_date=?
          AND (
            source='plan'
            OR status IN ('success','fail')
          )
        """,
        (user_id, today),
    ).fetchone()
    c.close()
    return int(row[0] if row else 0) > 0


def try_award_piece(user_id: str) -> Tuple[bool, str]:
    """
    오늘 기록이 있으면 자동으로 1조각 지급(하루 1회).
    """
    c = conn()
    row = c.execute(
        "SELECT category, image_file, order_json, revealed_count, last_reward_date FROM puzzle_progress WHERE user_id=?",
        (user_id,),
    ).fetchone()
    if not row:
        c.close()
        return False, "퍼즐이 아직 시작되지 않았어요. (🧩에서 카테고리 선택)"

    category, image_file, order_json, revealed_count, last_reward_date = row
    revealed_count = int(revealed_count or 0)
    today = date.today().isoformat()

    if last_reward_date == today:
        c.close()
        return False, "오늘은 이미 조각을 받았어요."

    if not _has_user_logged_today(user_id):
        c.close()
        return False, "오늘 기록이 아직 감지되지 않았어요. (계획 추가 또는 성공/실패 체크)"

    # 지급
    revealed_count = min(16, revealed_count + 1)
    c.execute(
        "UPDATE puzzle_progress SET revealed_count=?, last_reward_date=?, updated_at=? WHERE user_id=?",
        (revealed_count, today, now_iso(), user_id),
    )
    c.commit()

    # 완성 처리
    if revealed_count >= 16:
        c.execute(
            "INSERT INTO puzzle_gallery(user_id, category, image_file, completed_at) VALUES (?,?,?,?)",
            (user_id, category, image_file, now_iso()),
        )
        c.execute("DELETE FROM puzzle_progress WHERE user_id=?", (user_id,))
        c.commit()
        c.close()
        return True, "🎉 퍼즐 완성! 보관함에 추가됐어요."

    c.close()
    return True, "🧩 퍼즐 조각 1개가 공개됐어요!"


def load_gallery(user_id: str) -> List[dict]:
    c = conn()
    rows = c.execute(
        """
        SELECT category, image_file, completed_at
        FROM puzzle_gallery
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (user_id,),
    ).fetchall()
    c.close()
    return [{"category": r[0], "image_file": r[1], "completed_at": r[2]} for r in rows]
