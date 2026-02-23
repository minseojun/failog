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

import sqlite3
import json
from datetime import date

from failog.db import conn, now_iso


def _table_exists(c, name: str) -> bool:
    row = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _has_column(c, table: str, col: str) -> bool:
    try:
        cols = c.execute(f"PRAGMA table_info({table})").fetchall()
        return any(r[1] == col for r in cols)
    except Exception:
        return False


def ensure_puzzle_schema():
    """
    퍼즐 관련 테이블이 없으면 생성하고,
    과거 버전 테이블이 있더라도 최소한 조회가 깨지지 않도록 컬럼을 보정한다.
    """
    c = conn()
    cur = c.cursor()

    # 1) 보관함 테이블 (완성한 이미지 컬렉션)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_gallery (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          category TEXT NOT NULL,
          image_path TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )

    # 2) 현재 퍼즐 진행 상태 테이블 (있는 경우에만 쓸 수도 있지만, 안전하게 같이 보장)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_state (
          user_id TEXT PRIMARY KEY,
          category TEXT NOT NULL,
          image_path TEXT NOT NULL,
          revealed_json TEXT NOT NULL,
          last_award_date TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )

    # (선택) 예전 스키마 호환: 컬럼명이 다르게 존재하는 케이스 방어
    # gallery 테이블에 category/image_path/created_at 중 하나라도 없으면 추가
    if _table_exists(c, "puzzle_gallery"):
        if not _has_column(c, "puzzle_gallery", "category"):
            cur.execute("ALTER TABLE puzzle_gallery ADD COLUMN category TEXT")
        if not _has_column(c, "puzzle_gallery", "image_path"):
            cur.execute("ALTER TABLE puzzle_gallery ADD COLUMN image_path TEXT")
        if not _has_column(c, "puzzle_gallery", "created_at"):
            cur.execute("ALTER TABLE puzzle_gallery ADD COLUMN created_at TEXT")

    c.commit()
    c.close()
    
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


def load_gallery(user_id: str):
    """
    보관함(완성 이미지) 목록 조회.
    스키마가 없거나/다르면 먼저 생성/보정 후 조회한다.
    """
    ensure_puzzle_schema()

    c = conn()
    try:
        rows = c.execute(
            """
            SELECT category, image_path, created_at
            FROM puzzle_gallery
            WHERE user_id=?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        # 혹시라도 테이블/컬럼 문제면 한 번 더 스키마 보정 후 재시도
        c.close()
        ensure_puzzle_schema()
        c = conn()
        rows = c.execute(
            """
            SELECT category, image_path, created_at
            FROM puzzle_gallery
            WHERE user_id=?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    finally:
        c.close()

    # 화면에서 쓰기 쉬운 형태로 변환
    out = []
    for cat, path, created_at in rows:
        out.append(
            {
                "category": str(cat or ""),
                "image_path": str(path or ""),
                "created_at": str(created_at or ""),
            }
        )
    return out

def award_piece_if_eligible(user_id: str):
    """
    screens_planner에서 쓰던 이름 호환용.
    내부적으로 try_award_piece를 호출한다.

    Returns:
      (awarded: bool, msg: str)
    """
    return try_award_piece(user_id)
