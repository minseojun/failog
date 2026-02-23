# failog/puzzle.py
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st
from PIL import Image, ImageDraw

from failog.db import conn, now_iso

# =========================================================
# Config
# =========================================================
GRID_N = 4
TILE_COUNT = GRID_N * GRID_N

REPO_ROOT = Path(__file__).resolve().parent.parent
ANIMALS_DIR = REPO_ROOT / "assets" / "animals"

CATEGORIES: Dict[str, List[str]] = {
    "bunny": ["bunny1.jpeg", "bunny2.jpeg", "bunny3.jpeg", "bunny4.jpeg"],
    "guinea": ["guinea1.jpeg", "guinea2.jpeg", "guinea3.jpeg"],
    "puppy": ["puppy1.jpeg", "puppy2.jpeg", "puppy3.jpeg"],
    "seal": ["seal1.jpeg", "seal2.jpeg"],
}


# =========================================================
# ✅ DB schema guard (기존 DB에도 자동 생성)
# =========================================================
def ensure_puzzle_tables():
    c = conn()
    cur = c.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_state (
          user_id TEXT PRIMARY KEY,
          category TEXT NOT NULL,
          image_path TEXT NOT NULL,
          seed INTEGER NOT NULL,
          revealed_json TEXT NOT NULL,
          last_award_date TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          completed_at TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_gallery (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          category TEXT NOT NULL,
          image_path TEXT NOT NULL,
          completed_at TEXT NOT NULL
        );
        """
    )

       # 기존 배포 DB(구버전 스키마) 마이그레이션: 누락 컬럼 보강
    state_cols = {row[1] for row in cur.execute("PRAGMA table_info(puzzle_state)").fetchall()}
    if "category" not in state_cols:
        cur.execute("ALTER TABLE puzzle_state ADD COLUMN category TEXT")
    if "image_path" not in state_cols:
        cur.execute("ALTER TABLE puzzle_state ADD COLUMN image_path TEXT")
    if "seed" not in state_cols:
        cur.execute("ALTER TABLE puzzle_state ADD COLUMN seed INTEGER DEFAULT 1")
    if "revealed_json" not in state_cols:
        cur.execute("ALTER TABLE puzzle_state ADD COLUMN revealed_json TEXT DEFAULT '[]'")
    if "last_award_date" not in state_cols:
        cur.execute("ALTER TABLE puzzle_state ADD COLUMN last_award_date TEXT")
    if "created_at" not in state_cols:
        cur.execute("ALTER TABLE puzzle_state ADD COLUMN created_at TEXT")
    if "updated_at" not in state_cols:
        cur.execute("ALTER TABLE puzzle_state ADD COLUMN updated_at TEXT")
    if "completed_at" not in state_cols:
        cur.execute("ALTER TABLE puzzle_state ADD COLUMN completed_at TEXT")

    gallery_cols = {row[1] for row in cur.execute("PRAGMA table_info(puzzle_gallery)").fetchall()}
    if "category" not in gallery_cols:
        cur.execute("ALTER TABLE puzzle_gallery ADD COLUMN category TEXT")
    if "image_path" not in gallery_cols:
        cur.execute("ALTER TABLE puzzle_gallery ADD COLUMN image_path TEXT")
    if "completed_at" not in gallery_cols:
        cur.execute("ALTER TABLE puzzle_gallery ADD COLUMN completed_at TEXT")

    c.commit()
    c.close()



# =========================================================
# Data models
# =========================================================
@dataclass
class PuzzleState:
    user_id: str
    category: str
    image_path: str
    seed: int
    revealed: List[int]
    last_award_date: Optional[str] = None
    completed_at: Optional[str] = None


# =========================================================
# Utilities
# =========================================================
def _safe_int_list(x) -> List[int]:
    if not isinstance(x, list):
        return []
    out: List[int] = []
    for v in x:
        try:
            iv = int(v)
            if 0 <= iv < TILE_COUNT:
                out.append(iv)
        except Exception:
            pass
    seen = set()
    uniq: List[int] = []
    for v in out:
        if v not in seen:
            uniq.append(v)
            seen.add(v)
    return uniq


def _list_available_images(category: str) -> List[Path]:
    if category not in CATEGORIES:
        return []
    paths: List[Path] = []
    for fn in CATEGORIES[category]:
        p = ANIMALS_DIR / fn
        if p.exists() and p.is_file():
            paths.append(p)
    return paths


def _choose_random_image(category: str) -> Path:
    imgs = _list_available_images(category)
    if not imgs:
        raise FileNotFoundError(f"assets/animals 경로를 확인해 주세요: {ANIMALS_DIR}")
    return random.choice(imgs)


def _make_placeholder_png(size: Tuple[int, int]) -> bytes:
    w, h = size
    img = Image.new("RGB", (w, h), (243, 244, 246))  # 연회색
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w - 1, h - 1], outline=(17, 17, 17), width=1)  # 얇은 테두리
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@st.cache_data(show_spinner=False)
def _tile_bytes_from_image(image_path_str: str, target_tile_px: int = 160) -> Tuple[List[bytes], bytes]:
    p = Path(image_path_str)
    im = Image.open(p).convert("RGB")

    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    im_sq = im.crop((left, top, left + side, top + side))

    full = target_tile_px * GRID_N
    im_sq = im_sq.resize((full, full))

    tiles: List[bytes] = []
    for r in range(GRID_N):
        for c in range(GRID_N):
            x0 = c * target_tile_px
            y0 = r * target_tile_px
            tile = im_sq.crop((x0, y0, x0 + target_tile_px, y0 + target_tile_px))
            buf = BytesIO()
            tile.save(buf, format="PNG")
            tiles.append(buf.getvalue())

    buf0 = BytesIO()
    im_sq.save(buf0, format="PNG")
    return tiles, buf0.getvalue()


def _tasks_exist_today(user_id: str, d: date) -> bool:
    """오늘 날짜로 task가 하나라도 있으면 '기록했다'로 간주"""
    day = d.isoformat()
    c = conn()
    row = c.execute(
        """
        SELECT 1
        FROM tasks
        WHERE user_id=? AND task_date=?
        LIMIT 1
        """,
        (user_id, day),
    ).fetchone()
    c.close()
    return bool(row)


# =========================================================
# DB: load/save
# =========================================================
def load_state(user_id: str) -> Optional[PuzzleState]:
    ensure_puzzle_tables()
    c = conn()
    row = c.execute(
        """
        SELECT user_id, category, image_path, seed, revealed_json, last_award_date, completed_at
        FROM puzzle_state
        WHERE user_id=?
        """,
        (user_id,),
    ).fetchone()
    c.close()

    if not row:
        return None

    try:
        revealed = _safe_int_list(json.loads(row[4] or "[]"))
    except Exception:
        revealed = []

    return PuzzleState(
        user_id=str(row[0]),
        category=str(row[1]),
        image_path=str(row[2]),
        seed=(int(row[3]) if row[3] is not None else 1),
        revealed=revealed,
        last_award_date=(str(row[5]) if row[5] else None),
        completed_at=(str(row[6]) if row[6] else None),
    )


def save_state(state: PuzzleState):
    ensure_puzzle_tables()
    c = conn()
    now = now_iso()
    revealed_json = json.dumps(_safe_int_list(state.revealed), ensure_ascii=False)

    c.execute(
        """
        INSERT INTO puzzle_state
          (user_id, category, image_path, seed, revealed_json, last_award_date, created_at, updated_at, completed_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
          category=excluded.category,
          image_path=excluded.image_path,
          seed=excluded.seed,
          revealed_json=excluded.revealed_json,
          last_award_date=excluded.last_award_date,
          updated_at=excluded.updated_at,
          completed_at=excluded.completed_at
        """,
        (
            state.user_id,
            state.category,
            state.image_path,
            int(state.seed),
            revealed_json,
            state.last_award_date,
            now,
            now,
            state.completed_at,
        ),
    )
    c.commit()
    c.close()


def add_to_gallery(user_id: str, category: str, image_path: str):
    ensure_puzzle_tables()
    c = conn()
    c.execute(
        """
        INSERT INTO puzzle_gallery(user_id, category, image_path, completed_at)
        VALUES (?,?,?,?)
        """,
        (user_id, category, image_path, now_iso()),
    )
    c.commit()
    c.close()


def load_gallery(user_id: str) -> List[Dict[str, str]]:
    ensure_puzzle_tables()
    c = conn()
    rows = c.execute(
        """
        SELECT category, image_path, completed_at
        FROM puzzle_gallery
        WHERE user_id=?
        ORDER BY completed_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    c.close()
    return [{"category": str(a), "image_path": str(b), "completed_at": str(ca)} for a, b, ca in rows]

def get_render_payload(user_id: str) -> Dict[str, object]:
    """퍼즐 화면 렌더링에 필요한 상태/보관함 데이터를 한 번에 반환."""
    return {
        "state": load_state(user_id),
        "gallery": load_gallery(user_id),
    }
# =========================================================
# Puzzle operations
# =========================================================
def start_new_puzzle(user_id: str, category: str) -> PuzzleState:
    img = _choose_random_image(category)
    stt = PuzzleState(
        user_id=user_id,
        category=category,
        image_path=str(img),
        seed=random.randint(1, 2_000_000_000),
        revealed=[],
        last_award_date=None,
        completed_at=None,
    )
    save_state(stt)
    return stt


def _pick_next_piece(state: PuzzleState) -> Optional[int]:
    remaining = [i for i in range(TILE_COUNT) if i not in set(state.revealed)]
    if not remaining:
        return None
    return random.SystemRandom().choice(remaining)


def award_piece_if_eligible(user_id: str, d: date) -> Tuple[bool, Optional[int], Optional[str]]:
    ensure_puzzle_tables()

    if not _tasks_exist_today(user_id, d):
        return (False, None, None)

    state = load_state(user_id)
    if state is None:
        return (False, None, "🧩 퍼즐을 먼저 시작해 주세요. (상단 🧩 메뉴)")

    if state.completed_at:
        return (False, None, None)

    today_str = d.isoformat()
    if state.last_award_date == today_str:
        return (False, None, None)

    piece = _pick_next_piece(state)
    if piece is None:
        return (False, None, None)

    state.revealed.append(int(piece))
    state.revealed = _safe_int_list(state.revealed)
    state.last_award_date = today_str

    if len(state.revealed) >= TILE_COUNT:
        state.completed_at = now_iso()
        save_state(state)
        add_to_gallery(user_id, state.category, state.image_path)
        return (True, piece, "🎉 퍼즐 완성! 보관함에 추가됐어요.")
    else:
        save_state(state)
        return (True, piece, "🧩 퍼즐 조각 1개가 공개됐어요!")


def build_tiles_for_state(state: PuzzleState, tile_px: int = 170) -> Tuple[List[bytes], bytes]:
    return _tile_bytes_from_image(state.image_path, target_tile_px=tile_px)


def placeholder_tile(tile_px: int = 170) -> bytes:
    return _make_placeholder_png((tile_px, tile_px))
