# failog/screens_puzzle.py
from __future__ import annotations

from datetime import date

import streamlit as st

from failog.ui import section_title
from failog.puzzle import (
    CATEGORIES,
    TILE_COUNT,
    award_piece_if_eligible,
    build_tiles_for_state,
    get_render_payload,
    placeholder_tile,
    start_new_puzzle,
)


def screen_puzzle(user_id: str):
    section_title("🧩 퍼즐")

    # (중요) 퍼즐 화면에서도 한 번 호출해두면, 사용자가 Planner에서 기록하고
    # 바로 🧩로 넘어왔을 때도 지급 메시지를 볼 수 있음
    awarded, _, msg = award_piece_if_eligible(user_id, date.today())
    if msg:
        # msg는 "퍼즐 먼저 시작" 같은 안내도 올 수 있음
        st.toast(msg)

    # =========================
    # 시작/변경 UI
    # =========================
    top = st.columns([2.4, 1.2], gap="small")
    with top[0]:
        cat = st.selectbox(
            "동물 카테고리 선택(선택하면 이미지가 랜덤으로 정해져요)",
            options=list(CATEGORIES.keys()),
            format_func=lambda x: {
                "bunny": "bunny",
                "guinea": "guinea",
                "puppy": "puppy",
                "seal": "seal",
            }.get(x, x),
            key="pz_category",
        )
    with top[1]:
        st.write("")
        st.write("")
        if st.button("퍼즐 시작/바꾸기", use_container_width=True, key="pz_start"):
            try:
                start_new_puzzle(user_id, cat)
                st.success("새 퍼즐을 시작했어요. (원본 미리보기는 숨겨져요)")
                st.rerun()
            except Exception as e:
                st.error(str(e))
                return

    payload = get_render_payload(user_id)
    state = payload["state"]
    gallery = payload["gallery"]

    if state is None:
        st.info("아직 퍼즐이 없어요. 위에서 카테고리를 선택하고 '퍼즐 시작/바꾸기'를 눌러 시작해 주세요.")
        return

    # =========================
    # 퍼즐 진행 상황
    # =========================
    revealed = list(state.revealed or [])
    progress = min(1.0, len(revealed) / float(TILE_COUNT))
    st.caption(f"진행도: {len(revealed)}/{TILE_COUNT} 조각 공개")
    st.progress(progress)

    # 타일 생성
    tile_px = 170
    try:
        tiles, _ = build_tiles_for_state(state, tile_px=tile_px)
    except Exception as e:
        st.error(f"이미지 로드 실패: {type(e).__name__} (경로: {state.image_path})")
        return

    ph = placeholder_tile(tile_px=tile_px)

    # =========================
    # 4x4 퍼즐 렌더 (원본 미리보기 없음)
    # =========================
    st.markdown(
        """
<style>
/* 퍼즐 영역에서 column padding/gap 최소화 */
.puzzle-wrap [data-testid="stHorizontalBlock"] { gap: 0px !important; }
.puzzle-wrap [data-testid="column"] { padding-left: 0px !important; padding-right: 0px !important; }
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='puzzle-wrap'>", unsafe_allow_html=True)
    idx = 0
    for r in range(4):
        cols = st.columns(4, gap="small")
        for c in range(4):
            show = (idx in revealed)
            img_bytes = tiles[idx] if show else ph
            # caption/preview 완전 제거: 그냥 타일만 보여줌
            cols[c].image(img_bytes, use_container_width=True)
            idx += 1
    st.markdown("</div>", unsafe_allow_html=True)

    if state.completed_at:
        st.success("🎉 이 퍼즐은 완성됐어요! 보관함에 들어가 있어요. 새 퍼즐을 시작해 보세요.")

    st.markdown("<hr/>", unsafe_allow_html=True)

    # =========================
    # 보관함 (완성본은 여기서만)
    # =========================
    section_title("보관함")

    if not gallery:
        st.caption("아직 완성한 퍼즐이 없어요.")
        return

    # 한 줄에 4개씩
    per_row = 4
    for i in range(0, len(gallery), per_row):
        row = gallery[i : i + per_row]
        cols = st.columns(per_row, gap="small")
        for j, item in enumerate(row):
            # 완성본은 보관함에서만 보여줌
            cols[j].caption(f"{item['category']} · {item['completed_at'][:10]}")
            try:
                cols[j].image(item["image_path"], use_container_width=True)
            except Exception:
                cols[j].warning("이미지 로드 실패")
