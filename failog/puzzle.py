# failog/puzzle.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
import random

from PIL import Image

from failog.db import conn, now_iso
from failog.puzzle_assets import get_animal_assets

# "오늘 기록 남김" 판단을 위해 Planner가 쓰는 함수 재사용
# (너 레포에 이미 있음: failog.db.list_tasks_for_date)
from failog.db import list_tasks_for_date


GRID = 4
PIECES = GRID * GRID


@dataclass
class PuzzleRun:
    id: int
    user_id: str
    image_key: str
    unlocked_mask: str  # length 16, '0'/'1'
    started_at: str
    completed_at: str | None
    last_reward_date: str | None


def _mask_normalize(mask: str | None) -> str:
    m = (mask or "").strip()
    if len(m) != PIECES or any(ch not in "01" for ch in m):
        return "0" * PIECES
    return m


def _today_iso(d: date | None = None) -> str:
    return (d or date.today()).isoformat()


def ensure_puzzle_tables():
    c = conn()
    cur = c.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          image_key TEXT NOT NULL,
          unlocked_mask TEXT NOT NULL,
          started_at TEXT NOT NULL,
          completed_at TEXT,
          last_reward_date TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_collection (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          image_key TEXT NOT NULL,
          completed_at TEXT NOT NULL,
          UNIQUE(user_id, image_key)
        );
        """
    )

    c.commit()
    c.close()


def get_active_run(user_id: str) -> PuzzleRun | None:
    ensure_puzzle_tables()
    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        SELECT id, user_id, image_key, unlocked_mask, started_at, completed_at, last_reward_date
        FROM puzzle_runs
        WHERE user_id = ? AND completed_at IS NULL
        ORDER BY id DESC
        LIMIT 1;
        """,
        (user_id,),
    )
    row = cur.fetchone()
    c.close()
    if not row:
        return None
    return PuzzleRun(
        id=int(row[0]),
        user_id=str(row[1]),
        image_key=str(row[2]),
        unlocked_mask=_mask_normalize(row[3]),
        started_at=str(row[4]),
        completed_at=row[5],
        last_reward_date=row[6],
    )


def start_new_run(user_id: str, image_key: str) -> PuzzleRun:
    ensure_puzzle_tables()

    # 동시에 1개만: 기존 active가 있으면 그대로 반환
    existing = get_active_run(user_id)
    if existing:
        return existing

    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        INSERT INTO puzzle_runs(user_id, image_key, unlocked_mask, started_at, completed_at, last_reward_date)
        VALUES(?, ?, ?, ?, NULL, NULL);
        """,
        (user_id, image_key, "0" * PIECES, now_iso()),
    )
    c.commit()
    rid = int(cur.lastrowid)
    c.close()

    return get_active_run(user_id) or PuzzleRun(
        id=rid,
        user_id=user_id,
        image_key=image_key,
        unlocked_mask="0" * PIECES,
        started_at=now_iso(),
        completed_at=None,
        last_reward_date=None,
    )


def _update_run_mask(run_id: int, mask: str, last_reward_date: str | None):
    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        UPDATE puzzle_runs
        SET unlocked_mask = ?, last_reward_date = ?
        WHERE id = ?;
        """,
        (mask, last_reward_date, run_id),
    )
    c.commit()
    c.close()


def _complete_run(run: PuzzleRun):
    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        UPDATE puzzle_runs
        SET completed_at = ?
        WHERE id = ?;
        """,
        (now_iso(), run.id),
    )
    # 보관함 저장(이미 있으면 무시)
    cur.execute(
        """
        INSERT OR IGNORE INTO puzzle_collection(user_id, image_key, completed_at)
        VALUES(?, ?, ?);
        """,
        (run.user_id, run.image_key, now_iso()),
    )
    c.commit()
    c.close()


def get_collection(user_id: str) -> list[dict]:
    ensure_puzzle_tables()
    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        SELECT image_key, completed_at
        FROM puzzle_collection
        WHERE user_id = ?
        ORDER BY completed_at DESC;
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    c.close()
    out: list[dict] = []
    for k, t in rows:
        out.append({"image_key": str(k), "completed_at": str(t)})
    return out


def checkin_eligible(user_id: str, d: date | None = None) -> bool:
    """A안: 오늘 tasks가 1개라도 있으면 출석 인정"""
    dd = d or date.today()
    try:
        df = list_tasks_for_date(user_id, dd)
        return (df is not None) and (not df.empty)
    except Exception:
        # 혹시 함수가 내부에서 에러나면 안전하게 false
        return False


def reward_piece_if_possible(user_id: str, d: date | None = None) -> tuple[bool, str]:
    """
    반환: (지급여부, 메시지)
    - 하루 1개만 지급
    - 동시에 1개 퍼즐만 진행
    """
    dd = d or date.today()
    today = _today_iso(dd)

    run = get_active_run(user_id)
    if not run:
        return False, "진행 중인 퍼즐이 없어요. 먼저 퍼즐을 시작해 주세요."

    if not checkin_eligible(user_id, dd):
        return False, "오늘 아직 기록이 없어요. Planner에서 항목을 하나라도 추가하면 조각을 받을 수 있어요."

    if run.last_reward_date == today:
        return False, "오늘 조각은 이미 받았어요. 내일 또 받을 수 있어요."

    mask = list(run.unlocked_mask)
    locked = [i for i, ch in enumerate(mask) if ch == "0"]
    if not locked:
        # 이미 완성 상태인데 completed_at만 안찍힌 케이스 방지
        _complete_run(run)
        return False, "이미 퍼즐이 완성돼 있어요! 보관함을 확인해 주세요."

    # 조각 선택: 랜덤(더 게임같음)
    idx = random.choice(locked)
    mask[idx] = "1"
    new_mask = "".join(mask)

    _update_run_mask(run.id, new_mask, today)

    # 완성 체크
    if "0" not in new_mask:
        run.unlocked_mask = new_mask
        _complete_run(run)
        return True, "🎉 퍼즐 완성! 보관함에 저장했어요."

    return True, "🧩 퍼즐 조각 1개를 받았어요!"


def _asset_path_by_key(image_key: str) -> Path | None:
    for a in get_animal_assets():
        if a.key == image_key:
            return a.path
    return None


def _crop_to_square(im: Image.Image) -> Image.Image:
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def build_puzzle_tiles_png_bytes(image_key: str, size: int = 720) -> list[bytes]:
    """
    이미지 -> 정사각 크롭 -> resize -> 4x4 타일 -> PNG bytes list (16개)
    """
    p = _asset_path_by_key(image_key)
    if p is None or (not p.exists()):
        raise FileNotFoundError(f"Puzzle asset not found for key={image_key}")

    im = Image.open(p).convert("RGB")
    im = _crop_to_square(im)
    im = im.resize((size, size))

    tile = size // GRID
    tiles: list[bytes] = []

    for r in range(GRID):
        for c in range(GRID):
            x0 = c * tile
            y0 = r * tile
            x1 = x0 + tile
            y1 = y0 + tile
            piece = im.crop((x0, y0, x1, y1))

            buf = BytesIO()
            piece.save(buf, format="PNG")
            tiles.append(buf.getvalue())

    return tiles
