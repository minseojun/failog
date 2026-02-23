# failog/screens_puzzle.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import random
import streamlit as st

from failog.ui import section_title
from failog.prefs import ck_get, ck_set


ANIMALS = ["bunny", "guinea", "puppy", "seal"]
# 퍼즐은 4x4 = 16조각
PUZZLE_SIZE = 4
PUZZLE_PIECES = PUZZLE_SIZE * PUZZLE_SIZE


@dataclass
class AnimalImage:
    animal: str
    path: Path


def _repo_root() -> Path:
    """
    screens_puzzle.py 위치: failog/screens_puzzle.py
    repo root = failog 폴더의 부모
    """
    return Path(__file__).resolve().parents[1]


def _assets_animals_dir() -> Path:
    return _repo_root() / "assets" / "animals"


def _load_animal_images() -> dict[str, list[AnimalImage]]:
    """
    너가 말한 구조: assets/animals/bunny1.jpeg ... 처럼
    animals 폴더 바로 아래에 파일들이 있는 구조를 지원.
    """
    base = _assets_animals_dir()
    exts = [".jpeg", ".jpg", ".png", ".webp"]

    found: dict[str, list[AnimalImage]] = {a: [] for a in ANIMALS}
    if not base.exists():
        return found

    # 케이스: bunny1.jpeg, bunny2.jpeg ...
    for a in ANIMALS:
        for p in sorted(base.glob(f"{a}*")):
            if p.is_file() and p.suffix.lower() in exts:
                found[a].append(AnimalImage(animal=a, path=p))

    return found


def _today_key() -> str:
    return date.today().isoformat()


def _attendance_key() -> str:
    # 출석(기록) 기반 퍼즐 보상 누적 카운트
    return "failog_puzzle_attendance_count"


def _vault_key() -> str:
    # 완성한 동물 이미지 보관함 (csv string)
    return "failog_puzzle_vault"


def _selected_animal_key() -> str:
    return "failog_puzzle_selected_animal"


def _selected_img_key(animal: str) -> str:
    return f"failog_puzzle_selected_img_{animal}"


def _progress_key(animal: str, img_name: str) -> str:
    # 특정 동물 특정 이미지의 진행도(0~16)
    return f"failog_puzzle_progress_{animal}_{img_name}"


def _daily_claim_key() -> str:
    # 하루에 1조각만 지급(중복 클릭 방지)
    return f"failog_puzzle_claimed_{_today_key()}"


def _get_int_pref(key: str, default: int = 0) -> int:
    try:
        return int(ck_get(key, str(default)) or str(default))
    except Exception:
        return default


def _set_int_pref(key: str, val: int):
    ck_set(key, str(int(val)))


def _get_vault_list() -> list[str]:
    raw = (ck_get(_vault_key(), "") or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _add_to_vault(item: str):
    items = _get_vault_list()
    if item not in items:
        items.append(item)
        ck_set(_vault_key(), ",".join(items))


def _ensure_selection(images_by_animal: dict[str, list[AnimalImage]]):
    """
    선택된 동물/이미지가 없으면 합리적으로 초기값 설정
    """
    cur_animal = (ck_get(_selected_animal_key(), "") or "").strip()
    if cur_animal not in ANIMALS:
        cur_animal = "bunny"
        ck_set(_selected_animal_key(), cur_animal)

    # 해당 동물 이미지가 아예 없으면, 있는 동물로 옮김
    if not images_by_animal.get(cur_animal):
        for a in ANIMALS:
            if images_by_animal.get(a):
                cur_animal = a
                ck_set(_selected_animal_key(), cur_animal)
                break

    # 선택된 이미지
    img_list = images_by_animal.get(cur_animal, [])
    if img_list:
        sel = (ck_get(_selected_img_key(cur_animal), "") or "").strip()
        names = [x.path.name for x in img_list]
        if sel not in names:
            ck_set(_selected_img_key(cur_animal), names[0])


def _give_one_piece(images_by_animal: dict[str, list[AnimalImage]]):
    """
    '오늘 기록 남김' -> 퍼즐 조각 1개 지급
    - 하루 1회 지급 제한
    - 진행도가 16이 되면 완성 -> 보관함에 추가 + 진행도 리셋(다음 이미지로 넘어가게)
    """
    if ck_get(_daily_claim_key(), "false") == "true":
        st.info("오늘은 이미 퍼즐 조각을 받았어요 🙂")
        return

    animal = (ck_get(_selected_animal_key(), "") or "bunny").strip()
    img_list = images_by_animal.get(animal, [])
    if not img_list:
        st.error("선택한 동물 이미지가 없어서 퍼즐을 진행할 수 없어요.")
        return

    sel_name = (ck_get(_selected_img_key(animal), "") or "").strip()
    if not sel_name:
        sel_name = img_list[0].path.name
        ck_set(_selected_img_key(animal), sel_name)

    # 해당 파일 객체 찾기
    sel_obj = None
    for x in img_list:
        if x.path.name == sel_name:
            sel_obj = x
            break
    if sel_obj is None:
        sel_obj = img_list[0]
        ck_set(_selected_img_key(animal), sel_obj.path.name)
        sel_name = sel_obj.path.name

    prog_key = _progress_key(animal, sel_name)
    prog = _get_int_pref(prog_key, 0)

    prog = min(PUZZLE_PIECES, prog + 1)
    _set_int_pref(prog_key, prog)

    # 출석 누적도 같이 증가 (선택사항)
    att = _get_int_pref(_attendance_key(), 0)
    _set_int_pref(_attendance_key(), att + 1)

    # 오늘 지급 처리
    ck_set(_daily_claim_key(), "true")

    if prog >= PUZZLE_PIECES:
        # 완성
        vault_item = f"{animal}:{sel_name}"
        _add_to_vault(vault_item)
        st.success("🎉 퍼즐 완성! 보관함에 추가했어요.")
        # 다음 이미지로 넘어가도록 진행도 리셋 + 다음 이미지 선택
        _set_int_pref(prog_key, 0)

        # 다음 이미지 선택(있으면 다음, 없으면 랜덤)
        names = [x.path.name for x in img_list]
        if sel_name in names and len(names) > 1:
            idx = names.index(sel_name)
            next_name = names[(idx + 1) % len(names)]
            ck_set(_selected_img_key(animal), next_name)
    else:
        st.success(f"🧩 퍼즐 조각 +1! ({prog}/{PUZZLE_PIECES})")


def _render_puzzle_grid(progress: int):
    """
    4x4 퍼즐 진행도 표시(가림막)
    """
    # 16칸 중 progress만큼 "오픈"
    opened = set(range(progress))
    st.markdown("<div style='border:1px solid #111; padding:10px;'>", unsafe_allow_html=True)

    idx = 0
    for r in range(PUZZLE_SIZE):
        cols = st.columns(PUZZLE_SIZE, gap="small")
        for c in range(PUZZLE_SIZE):
            with cols[c]:
                if idx in opened:
                    st.markdown(
                        "<div style='height:50px;border:1px solid #111;background:#e5e7eb;'></div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<div style='height:50px;border:1px solid #111;background:#fff;'></div>",
                        unsafe_allow_html=True,
                    )
            idx += 1

    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("연회색 칸 = 획득한 퍼즐 조각(열린 칸) · 흰색 칸 = 아직 못 받은 조각")


def screen_puzzle(user_id: str):
    # user_id는 현재는 사용 안하지만, 향후 DB로 옮길 때 대비해서 받음

    section_title("🧩 Puzzle")

    images_by_animal = _load_animal_images()
    _ensure_selection(images_by_animal)

    base = _assets_animals_dir()

    # --- 에러 메시지를 더 정확하게 ---
    # 모든 동물 이미지가 하나도 없으면 경로/파일명 진단을 자세히 보여줌
    total = sum(len(v) for v in images_by_animal.values())
    if total == 0:
        st.error("assets/animals 에 동물 이미지가 없어요. 파일 경로/파일명을 확인해 주세요.")
        st.write("지금 앱이 찾는 폴더:", str(base))
        st.write("기대 파일명 예시:")
        st.write("- bunny1.jpeg ~ bunny4.jpeg")
        st.write("- guinea1.jpeg ~ guinea3.jpeg")
        st.write("- puppy1.jpeg ~ puppy3.jpeg")
        st.write("- seal1.jpeg ~ seal2.jpeg")
        st.caption("해결 팁: Streamlit Cloud에서는 리포지토리에 assets 폴더가 실제로 커밋되어 있어야 해요.")
        return

    # --- 동물 선택 UI ---
    cur_animal = (ck_get(_selected_animal_key(), "bunny") or "bunny").strip()

    # 이미지가 없는 동물은 선택지에서 제외(빈 선택하면 또 오류나서)
    available_animals = [a for a in ANIMALS if images_by_animal.get(a)]
    if cur_animal not in available_animals:
        cur_animal = available_animals[0]
        ck_set(_selected_animal_key(), cur_animal)

    cols = st.columns([2.2, 3.8], gap="large")

    with cols[0]:
        st.markdown("**동물 선택**")
        animal = st.selectbox(
            "카테고리",
            options=available_animals,
            index=available_animals.index(cur_animal),
            key="puzzle_animal_select",
        )
        if animal != cur_animal:
            ck_set(_selected_animal_key(), animal)

        img_list = images_by_animal.get(animal, [])
        img_names = [x.path.name for x in img_list]

        sel_name = (ck_get(_selected_img_key(animal), "") or "").strip()
        if sel_name not in img_names:
            sel_name = img_names[0]
            ck_set(_selected_img_key(animal), sel_name)

        st.markdown("**사진 선택**")
        chosen = st.selectbox(
            "이미지",
            options=img_names,
            index=img_names.index(sel_name),
            key=f"puzzle_img_select_{animal}",
        )
        if chosen != sel_name:
            ck_set(_selected_img_key(animal), chosen)

        st.markdown("<hr/>", unsafe_allow_html=True)

        # 출석/기록 버튼(하루 1조각)
        if st.button("오늘 기록 남김 → 퍼즐 조각 받기", use_container_width=True, key="puzzle_claim"):
            _give_one_piece(images_by_animal)
            st.rerun()

        # 오늘 이미 받았는지 표시
        if ck_get(_daily_claim_key(), "false") == "true":
            st.caption("✅ 오늘 퍼즐 조각을 이미 받았어요.")
        else:
            st.caption("⬜ 오늘은 아직 퍼즐 조각을 받지 않았어요.")

        # 누적 출석(옵션)
        att = _get_int_pref(_attendance_key(), 0)
        st.caption(f"누적 기록(출석) 횟수: {att}")

    with cols[1]:
        # 진행도 표시
        animal = (ck_get(_selected_animal_key(), available_animals[0]) or available_animals[0]).strip()
        img_list = images_by_animal.get(animal, [])
        img_names = [x.path.name for x in img_list]
        sel_name = (ck_get(_selected_img_key(animal), img_names[0]) or img_names[0]).strip()
        if sel_name not in img_names:
            sel_name = img_names[0]
            ck_set(_selected_img_key(animal), sel_name)

        prog_key = _progress_key(animal, sel_name)
        prog = _get_int_pref(prog_key, 0)

        st.markdown(f"**진행도: {prog}/{PUZZLE_PIECES}**")
        _render_puzzle_grid(prog)

        # 미리보기 이미지
        st.markdown("<hr/>", unsafe_allow_html=True)
        st.markdown("**원본 이미지 미리보기(완성 보상)**")
        # 실제 이미지 표시
        img_path = None
        for x in img_list:
            if x.path.name == sel_name:
                img_path = x.path
                break
        if img_path is not None and img_path.exists():
            st.image(str(img_path), use_container_width=True)
        else:
            st.warning("선택한 이미지 파일을 찾지 못했어요. 파일명을 다시 확인해 주세요.")

    # --- 보관함 ---
    st.markdown("<hr/>", unsafe_allow_html=True)
    section_title("보관함")

    vault = _get_vault_list()
    if not vault:
        st.caption("아직 완성한 퍼즐이 없어요. 16일 출석하면 한 장을 획득해요!")
        return

    # 보관함 아이템 표시: animal:filename
    # 가능한 경우 이미지도 표시
    for item in vault[::-1][:24]:
        try:
            a, fn = item.split(":", 1)
        except Exception:
            a, fn = "unknown", item

        st.markdown(f"- **{a}** · {fn}")

        p = _assets_animals_dir() / fn
        # 혹시 subfolder 구조로 바뀐 경우도 대비(assets/animals/<animal>/<fn>)
        if not p.exists():
            p2 = _assets_animals_dir() / a / fn
            if p2.exists():
                p = p2

        if p.exists():
            st.image(str(p), width=240)
