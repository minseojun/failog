# failog/puzzle.py
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import date
from typing import Any

from failog.prefs import ck_get, ck_set


ASSETS_DIR = os.path.join("assets", "animals")
CATEGORIES = ["bunny", "guinea", "puppy", "seal"]


@dataclass
class PuzzleState:
    category: str
    image_path: str
    progress: int  # 0..16
    reveal_order: list[int]  # permutation of 0..15
    last_award_date: str  # ISO date string, '' if never
    completed: bool = False


def _key(user_id: str) -> str:
    return f"failog_puzzle_state__{user_id}"


def _collection_key(user_id: str) -> str:
    return f"failog_puzzle_collection__{user_id}"


def list_images(category: str) -> list[str]:
    """
    assets/animals 안에서 {category}{n}.jpeg 같은 파일을 찾는다.
    """
    if category not in CATEGORIES:
        return []

    if not os.path.isdir(ASSETS_DIR):
        return []

    files = []
    for fn in os.listdir(ASSETS_DIR):
        low = fn.lower()
        if not low.endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        if low.startswith(category.lower()):
            files.append(os.path.join(ASSETS_DIR, fn))

    files.sort()
    return files


def _stable_shuffle_order(seed_text: str) -> list[int]:
    """
    랜덤 공개 순서지만, 같은 이미지면 항상 같은 랜덤 순서가 나오게(고정 랜덤).
    """
    r = random.Random(seed_text)
    order = list(range(16))
    r.shuffle(order)
    return order


def load_state(user_id: str) -> PuzzleState | None:
    raw = ck_get(_key(user_id), "")
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return PuzzleState(
            category=str(obj.get("category") or ""),
            image_path=str(obj.get("image_path") or ""),
            progress=int(obj.get("progress") or 0),
            reveal_order=list(obj.get("reveal_order") or list(range(16))),
            last_award_date=str(obj.get("last_award_date") or ""),
            completed=bool(obj.get("completed") or False),
        )
    except Exception:
        return None


def save_state(user_id: str, stt: PuzzleState) -> None:
    obj: dict[str, Any] = {
        "category": stt.category,
        "image_path": stt.image_path,
        "progress": int(max(0, min(16, stt.progress))),
        "reveal_order": stt.reveal_order,
        "last_award_date": stt.last_award_date or "",
        "completed": bool(stt.completed),
    }
    ck_set(_key(user_id), json.dumps(obj, ensure_ascii=False))


def start_new_puzzle(user_id: str, category: str) -> PuzzleState:
    imgs = list_images(category)
    if not imgs:
        # 비어있으면 안전하게 더미 상태 반환 (화면에서 에러 메시지 처리)
        stt = PuzzleState(
            category=category,
            image_path="",
            progress=0,
            reveal_order=list(range(16)),
            last_award_date="",
            completed=False,
        )
        save_state(user_id, stt)
        return stt

    image_path = random.choice(imgs)
    order = _stable_shuffle_order(os.path.basename(image_path))
    stt = PuzzleState(
        category=category,
        image_path=image_path,
        progress=0,
        reveal_order=order,
        last_award_date="",
        completed=False,
    )
    save_state(user_id, stt)
    return stt


def load_or_init(user_id: str, category_if_new: str = "bunny") -> PuzzleState:
    stt = load_state(user_id)
    if stt is None:
        return start_new_puzzle(user_id, category_if_new)
    return stt


def _add_to_collection_if_new(user_id: str, image_path: str) -> None:
    raw = ck_get(_collection_key(user_id), "[]")
    try:
        arr = json.loads(raw)
        if not isinstance(arr, list):
            arr = []
    except Exception:
        arr = []

    if image_path and image_path not in arr:
        arr.append(image_path)
        ck_set(_collection_key(user_id), json.dumps(arr, ensure_ascii=False))


def load_collection(user_id: str) -> list[str]:
    raw = ck_get(_collection_key(user_id), "[]")
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            return [str(x) for x in arr if str(x)]
        return []
    except Exception:
        return []


def award_piece_if_needed(user_id: str) -> tuple[bool, str]:
    """
    planner에서 기록 이벤트 발생 시 호출.
    - 하루 1회만 지급
    - 진행 중 퍼즐이 있을 때만 지급
    """
    stt = load_state(user_id)
    if stt is None:
        return (False, "no_puzzle")

    if not stt.image_path:
        return (False, "no_image")

    if stt.progress >= 16 or stt.completed:
        return (False, "already_completed")

    today = date.today().isoformat()
    if stt.last_award_date == today:
        return (False, "already_awarded_today")

    stt.progress = min(16, stt.progress + 1)
    stt.last_award_date = today

    if stt.progress >= 16:
        stt.completed = True
        _add_to_collection_if_new(user_id, stt.image_path)

    save_state(user_id, stt)
    return (True, "awarded")
