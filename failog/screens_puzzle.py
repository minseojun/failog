# failog/screens_puzzle.py
from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st
from PIL import Image

from failog.ui import section_title
from failog.puzzle import (
    CATEGORIES,
    ASSETS_DIR,
    init_puzzle_tables,
    get_or_create_progress,
    set_category,
    try_award_piece,
    load_gallery,
)


def _render_grid_placeholder(revealed_count: int, order: list[int]):
    """
    4x4 그리드
    - 공개된 조각: ✅
    - 미공개: 빈칸(흰 배경에 얇은 테두리)
    """
    revealed_set = set(order[: max(0, min(16, revealed_count))])

    for r in range(4):
        cols = st.columns(4, gap="small")
        for c in range(4):
            idx = r * 4 + c
            with cols[c]:
                if idx in revealed_set:
                    st.markdown(
                        "<div style='height:70px; border:1px solid #111; background:#e5e7eb; display:flex; align-items:center; justify-content:center; font-weight:900;'>✓</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<div style='height:70px; border:1px solid #111; background:#fff;'></div>",
                        unsafe_allow_html=True,
                    )


def screen_puzzle(user_id: str):
    init_puzzle_tables()

    section_title("🧩 퍼즐")

    # 1) 카테고리 선택
    with st.container(border=True):
        st.caption("동물을 고르면, 해당 카테고리 이미지가 랜덤으로 1장 선택돼요. (완성 전엔 원본 공개 없음)")

        cat = st.selectbox(
            "동물 카테고리",
            options=CATEGORIES,
            index=0,
            format_func=lambda x: {"bunny": "bunny", "guinea": "guinea", "puppy": "puppy", "seal": "seal"}.get(x, x),
            key="puzzle_cat",
        )

        if st.button("이 카테고리로 시작/변경", use_container_width=True, key="puzzle_set_cat"):
            pr, msg = set_category(user_id, cat)
            if pr:
                st.success("퍼즐을 시작했어요! 이제 Planner에서 기록을 남기면 자동으로 조각이 공개돼요.")
            else:
                st.error(msg)
            st.rerun()

    pr, msg = get_or_create_progress(user_id, st.session_state.get("puzzle_cat", "bunny"))
    if not pr:
        st.error(msg)
        st.caption(f"현재 assets 폴더: {ASSETS_DIR}")
        return

    # 2) 자동 지급(이 화면 들어와도 지급 시도해줌)
    awarded, award_msg = try_award_piece(user_id)
    if awarded:
        st.toast(award_msg)

        # 최신 progress 다시 로드(조각 증가 반영)
        pr, _ = get_or_create_progress(user_id, pr["category"])

    # 3) 퍼즐 렌더링 (원본 미리보기 없음)
    with st.container(border=True):
        st.markdown(f"**진행도: {pr['revealed_count']}/16**")
        _render_grid_placeholder(pr["revealed_count"], pr["order"])

        st.caption("조각 공개는 하루 1회 · Planner에서 계획 추가 또는 성공/실패 체크 시 자동 지급")

    # 4) 보관함
    section_title("보관함")
    gallery = load_gallery(user_id)
    if not gallery:
        st.caption("아직 완성한 동물이 없어요. 🧩")
        return

    for g in gallery[:12]:
        with st.container(border=True):
            st.write(f"**{g['category']}**")
            st.caption(f"완성: {g['completed_at']}")
            # 보관함은 완성 보상이니까 여기서는 보여줘도 OK
            try:
                img = Image.open(Path(g["image_file"]))
                st.image(img, use_container_width=True)
            except Exception:
                st.caption("(이미지를 불러오지 못했어요)")
