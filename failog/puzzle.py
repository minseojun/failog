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
GRID_N = 4  # 4x4 = 16
TILE_COUNT = GRID_N * GRID_N

# failog/puzzle.py 위치: /mount/src/failog/failog/puzzle.py
# assets: /mount/src/failog/assets/animals
REPO_ROOT = Path(__file__).resolve().parent.parent
ANIMALS_DIR = REPO_ROOT / "assets" / "animals"


CATEGORIES: Dict[str, List[str]] = {
    "bunny": ["bunny1.jpeg", "bunny2.jpeg", "bunny3.jpeg", "bunny4.jpeg"],
    "guinea": ["guinea1.jpeg", "guinea2.jpeg", "guinea3.jpeg"],
    "puppy": ["puppy1.jpeg", "puppy2.jpeg", "puppy3.jpeg"],
    "seal": ["seal1.jpeg", "seal2.jpeg"],
}


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
    out = []
    for v in x:
        try:
            iv = int(v)
            if 0 <= iv < TILE_COUNT:
                out.append(iv)
        except Exception:
            pass
    # unique preserve
    seen = set()
    uniq = []
    for v in out:
        if v not in seen:
            uniq.append(v)
            seen.add(v)
    return uniq


def _list_available_images(category: str) -> List[Path]:
    # 폴더 구조가 assets/animals 안에 파일들이 "바로" 존재하는 전제
    if category not in CATEGORIES:
        return []
    paths = []
    for fn in CATEGORIES[category]:
        p = ANIMALS_DIR / fn
        if p.exists() and p.is_file():
            paths.append(p)
    return paths


def _choose_random_image(category: str) -> Path:
    imgs = _list_available_images(category)
    if not imgs:
        raise FileNotFoundError(
            f"assets/animals 에 '{category}' 이미지가 없어요. 경로/파일명을 확인해 주세요: {ANIMALS_DIR}"
        )
    return random.choice(imgs)


def _make_placeholder_png(size: Tuple[int, int]) -> bytes:
    """연회색 단색 + 얇은 테두리 placeholder"""
    w, h = size
    img = Image.new("RGB", (w, h), (243, 244, 246))  # #f3f4f6
    draw = ImageDraw.Draw(img)
    # border (thin)
    draw.rectangle([0, 0, w - 1, h - 1], outline=(17, 17, 17), width=1)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@st.cache_data(show_spinner=False)
def _tile_bytes_from_image(image_path_str: str, target_tile_px: int = 160) -> Tuple[List[bytes], bytes]:
    """
    원본 이미지를 4x4로 잘라 16개 타일 PNG bytes로 반환.
    - 원본 미리보기는 화면에서 쓰지 않지만, 완성본/갤러리에 필요하면 쓸 수 있게 원본 bytes도 같이 반환.
    캐시 키: image_path_str
    """
    p = Path(image_path_str)
    im = Image.open(p).convert("RGB")

    # 정사각형으로 중앙 크롭 후 리사이즈 (퍼즐이 예쁘게 맞게)
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    im_sq = im.crop((left, top, left + side, top + side))

    # 전체 크기를 TILE_PX * GRID_N 로 맞추기
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
    """
    '오늘 기록을 남겼다'를 DB에서 감지:
    - 오늘 날짜(task_date)에 해당하는 항목 중
      created_at 또는 updated_at이 오늘(YYYY-MM-DD)로 시작하면 기록이 있었다고 판단.
    """
    day = d.isoformat()
    c = conn()
    row = c.execute(
        """
        SELECT 1
        FROM tasks
        WHERE user_id=?
          AND task_date=?
          AND (
            created_at LIKE ? || '%'
            OR updated_at LIKE ? || '%'
          )
        LIMIT 1
        """,
        (user_id, day, day, day),
    ).fetchone()
    c.close()
    return bool(row)


# =========================================================
# DB: load/save
# =========================================================
def load_state(user_id: str) -> Optional[PuzzleState]:
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

    revealed = []
    try:
        revealed = _safe_int_list(json.loads(row[4] or "[]"))
    except Exception:
        revealed = []

    return PuzzleState(
        user_id=str(row[0]),
        category=str(row[1]),
        image_path=str(row[2]),
        seed=int(row[3]),
        revealed=revealed,
        last_award_date=(str(row[5]) if row[5] else None),
        completed_at=(str(row[6]) if row[6] else None),
    )


def save_state(state: PuzzleState):
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
    out = []
    for cat, path, ts in rows:
        out.append({"category": str(cat), "image_path": str(path), "completed_at": str(ts)})
    return out


# =========================================================
# Puzzle operations
# =========================================================
def start_new_puzzle(user_id: str, category: str) -> PuzzleState:
    """
    카테고리를 고르면 이미지가 랜덤으로 결정되고,
    revealed는 비어있는 상태로 시작(원본 미리보기 없음).
    """
    img = _choose_random_image(category)
    # seed: 유저/이미지 기반 + 랜덤성
    seed = random.randint(1, 2_000_000_000)
    stt = PuzzleState(
        user_id=user_id,
        category=category,
        image_path=str(img),
        seed=seed,
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
    # 랜덤 순서 공개: 완전 랜덤(매번 award 시 랜덤 선택)
    return random.SystemRandom().choice(remaining)


def award_piece_if_eligible(user_id: str, d: date) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Planner에서 자동 호출하는 함수.
    - 오늘 기록이 있으면(생성/업데이트) 하루에 1번만 조각 지급.
    returns: (awarded?, piece_index, message)
    """
    # 오늘 기록이 없으면 지급 X
    if not _tasks_exist_today(user_id, d):
        return (False, None, None)

    state = load_state(user_id)
    if state is None:
        # 퍼즐을 아직 시작 안 했으면 지급할 수 없으니 안내만
        return (False, None, "🧩 퍼즐을 먼저 시작해 주세요. (상단 🧩 메뉴)")

    # 이미 완료한 퍼즐이면 더 이상 지급 안 함
    if state.completed_at:
        return (False, None, None)

    today_str = d.isoformat()
    if state.last_award_date == today_str:
        return (False, None, None)  # 이미 오늘 지급함

    piece = _pick_next_piece(state)
    if piece is None:
        return (False, None, None)

    state.revealed.append(int(piece))
    state.revealed = _safe_int_list(state.revealed)
    state.last_award_date = today_str

    # 완료 체크
    if len(state.revealed) >= TILE_COUNT:
        state.completed_at = now_iso()
        save_state(state)
        add_to_gallery(user_id, state.category, state.image_path)
        return (True, piece, "🎉 퍼즐 완성! 보관함에 추가됐어요.")
    else:
        save_state(state)
        return (True, piece, "🧩 퍼즐 조각 1개가 공개됐어요!")


def get_render_payload(user_id: str) -> Dict[str, object]:
    """
    화면 렌더에 필요한 데이터 묶어서 반환.
    """
    state = load_state(user_id)
    payload: Dict[str, object] = {
        "state": state,
        "gallery": load_gallery(user_id),
    }
    return payload


def build_tiles_for_state(state: PuzzleState, tile_px: int = 170) -> Tuple[List[bytes], bytes]:
    tiles, full = _tile_bytes_from_image(state.image_path, target_tile_px=tile_px)
    return tiles, full


def placeholder_tile(tile_px: int = 170) -> bytes:
    return _make_placeholder_png((tile_px, tile_px))
