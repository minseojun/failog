# failog/screens_puzzle.py
from __future__ import annotations

import os
from typing import List

import streamlit as st
from PIL import Image

from failog.ui import section_title
from failog.puzzle import (
    CATEGORIES,
    ASSETS_DIR,
    list_images,
    load_or_init,
    load_state,
    save_state,
    start_new_puzzle,
    load_collection,
    PuzzleState,
)


def _tile_images(img: Image.Image, grid: int = 4) -> List[Image.Image]:
    """
    이미지를 4x4로 자른 타일 리스트(16개)를 반환
    """
    w, h = img.size
    tw = w // grid
    th = h // grid
    tiles: List[Image.Image] = []
    for r in range(grid):
        for c in range(grid):
            left = c * tw
            top = r * th
            right = (c + 1) * tw if c < grid - 1 else w
            bottom = (r + 1) * th if r < grid - 1 else h
            tiles.append(img.crop((left, top, right, bottom)))
    return tiles


def _placeholder(size: tuple[int, int]) -> Image.Image:
    return Image.new("RGB", size, (243, 244, 246))  # 연회색(#f3f4f6)


def screen_puzzle(user_id: str):
    section_title("🧩 Puzzle")

    # assets 폴더 존재 체크
    if not os.path.isdir(ASSETS_DIR):
        st.error(f"`{ASSETS_DIR}` 폴더가 없어요. 레포에 assets/animals 폴더가 있는지 확인해 주세요.")
        return

    stt = load_or_init(user_id, "bunny")

    # 카테고리 선택: "고르기만 하면 랜덤 이미지 고정"
    # - 진행 중(progress>0)이면 카테고리 바꾸면 퍼즐이 바뀌는게 혼란이므로:
    #   progress==0 or completed일 때만 자동 변경/새 퍼즐 시작을 허용(버튼으로).
    cur_cat = stt.category if stt.category in CATEGORIES else "bunny"

    top = st.columns([2.2, 1.2, 2.6], gap="large")

    with top[0]:
        cat = st.selectbox(
            "동물 카테고리",
            options=CATEGORIES,
            index=CATEGORIES.index(cur_cat),
            key="puz_cat",
        )

    with top[1]:
        can_auto_switch = (stt.progress == 0) or stt.completed or (not stt.image_path)
        if st.button("새 퍼즐 시작", use_container_width=True, key="puz_new"):
            stt = start_new_puzzle(user_id, cat)
            st.rerun()

    with top[2]:
        # 카테고리만 바꿨을 때: 진행 중이면 자동 변경하지 않음
        if cat != cur_cat and ((stt.progress == 0) or stt.completed or (not stt.image_path)):
            stt = start_new_puzzle(user_id, cat)
            st.rerun()

        st.caption(
            f"진행도: **{stt.progress}/16** · "
            f"{'✅ 완성!' if stt.completed else '오늘 기록하면 자동으로 1조각 공개'}"
        )

    imgs = list_images(stt.category)
    if not imgs:
        st.error(
            "assets/animals 에 동물 이미지가 없어요. 파일 경로/파일명을 확인해 주세요.\n\n"
            "필요 파일 예시:\n"
            "- bunny1.jpeg~bunny4.jpeg\n"
            "- guinea1.jpeg~guinea3.jpeg\n"
            "- puppy1.jpeg~puppy3.jpeg\n"
            "- seal1.jpeg~seal2.jpeg"
        )
        return

    if not stt.image_path or (not os.path.isfile(stt.image_path)):
        # 상태에 이미지 경로가 잘못 저장된 경우 방어
        stt = start_new_puzzle(user_id, stt.category)
        if not stt.image_path:
            st.error("퍼즐 이미지를 선택할 수 없어요. assets/animals 폴더를 확인해 주세요.")
            return

    # 원본 미리보기는 '절대' 안 보여주고, 타일만 노출
    try:
        img = Image.open(stt.image_path).convert("RGB")
    except Exception:
        st.error("이미지 파일을 열 수 없어요. 파일이 손상되었거나 포맷이 지원되지 않을 수 있어요.")
        return

    # 그리드 타일 생성
    # 너무 큰 이미지면 화면이 과하게 커지므로 적당히 리사이즈(기능 영향 없음)
    max_w = 900
    if img.size[0] > max_w:
        ratio = max_w / img.size[0]
        img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)))

    tiles = _tile_images(img, grid=4)
    ph = _placeholder(tiles[0].size)

    # 공개된 타일 인덱스 집합
    reveal_count = max(0, min(16, int(stt.progress)))
    revealed_idx = set(stt.reveal_order[:reveal_count])

    # 4x4 출력
    for r in range(4):
        cols = st.columns(4, gap="small")
        for c in range(4):
            idx = r * 4 + c
            with cols[c]:
                if idx in revealed_idx:
                    st.image(tiles[idx], use_container_width=True)
                else:
                    st.image(ph, use_container_width=True)

    st.markdown("<hr/>", unsafe_allow_html=True)

    # 보관함(완성본만 표시)
    section_title("보관함")
    col = load_collection(user_id)
    if not col:
        st.caption("아직 완성한 동물이 없어요. 16일 기록하면 1장을 완성할 수 있어요.")
        return

    # 완성본 갤러리
    gcols = st.columns(4, gap="small")
    for i, path in enumerate(col):
        j = i % 4
        with gcols[j]:
            try:
                im = Image.open(path).convert("RGB")
                st.image(im, use_container_width=True)
                st.caption(os.path.basename(path))
            except Exception:
                st.caption("(이미지 로드 실패)")
