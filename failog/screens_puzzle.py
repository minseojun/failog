# failog/screens_puzzle.py
from __future__ import annotations

import streamlit as st

from failog.ui import section_title
from failog.puzzle import (
    CATEGORIES,
    CATEGORY_FILES,
    create_new_puzzle,
    load_puzzle_state,
    award_piece_if_eligible,
    slice_image_4x4,
    get_gallery,
)


def screen_puzzle(user_id: str):
    section_title("Puzzle")

    # ✅ 퍼즐 화면에 들어와도 한 번 자동 지급 시도(Planner에서 놓쳐도 여기서 보정)
    awarded, msg = award_piece_if_eligible(user_id)
    # 메시지는 너무 시끄러울 수 있으니 “지급된 경우만” 알려줌
    if awarded:
        st.success(msg)

    ps = load_puzzle_state(user_id)

    # 퍼즐 시작 전: 카테고리 선택
    if not ps:
        st.caption("동물 카테고리를 고르면, 이미지가 랜덤으로 선택되고 퍼즐이 시작돼요.")
        cat = st.selectbox("카테고리", options=CATEGORIES, format_func=lambda x: x, key="puz_cat")
        if st.button("퍼즐 시작", use_container_width=True, key="puz_start"):
            try:
                create_new_puzzle(user_id, cat)
                st.rerun()
            except Exception as e:
                st.error(str(e))
        st.markdown("<hr/>", unsafe_allow_html=True)

        # 보관함
        section_title("보관함")
        gallery = get_gallery(user_id)
        if not gallery:
            st.caption("아직 완성한 퍼즐이 없어요.")
        else:
            cols = st.columns(4)
            for i, g in enumerate(gallery[:12]):
                with cols[i % 4]:
                    st.image(g["image_path"], use_container_width=True)
                    st.caption(f"{g['category']} · {g['completed_on']}")
        return

    # 진행 퍼즐 표시(원본 미리보기 없음)
    st.caption(f"카테고리: {ps.category}  ·  진행: {ps.revealed_mask.count('1')}/16")

    try:
        pieces = slice_image_4x4(ps.image_path, size=640)
    except Exception as e:
        st.error(f"이미지 로딩/자르기 실패: {type(e).__name__}")
        return

    # 4x4 그리드 렌더
    mask = ps.revealed_mask
    for r in range(4):
        cols = st.columns(4, gap="small")
        for c in range(4):
            idx = r * 4 + c
            with cols[c]:
                if mask[idx] == "1":
                    st.image(pieces[idx], use_container_width=True)
                else:
                    # 숨김 타일(회색)
                    st.markdown(
                        """
                        <div style="
                          width:100%;
                          aspect-ratio: 1 / 1;
                          border: 1px solid #111;
                          background: #e5e7eb;
                        "></div>
                        """,
                        unsafe_allow_html=True,
                    )

    st.markdown("<hr/>", unsafe_allow_html=True)

    # 보관함
    section_title("보관함")
    gallery = get_gallery(user_id)
    if not gallery:
        st.caption("아직 완성한 퍼즐이 없어요.")
    else:
        cols = st.columns(4)
        for i, g in enumerate(gallery[:12]):
            with cols[i % 4]:
                st.image(g["image_path"], use_container_width=True)
                st.caption(f"{g['category']} · {g['completed_on']}")
