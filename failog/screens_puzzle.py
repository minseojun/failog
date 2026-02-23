# failog/screens_puzzle.py
from __future__ import annotations

from datetime import date

import streamlit as st

from failog.ui import inject_css, section_title
from failog.puzzle_assets import get_animal_assets
from failog.puzzle import (
    get_active_run,
    start_new_run,
    reward_piece_if_possible,
    build_puzzle_tiles_png_bytes,
    get_collection,
)


@st.cache_data(show_spinner=False)
def _cached_tiles(image_key: str) -> list[bytes]:
    # 타일은 동일 이미지면 매번 만들 필요 없음
    return build_puzzle_tiles_png_bytes(image_key=image_key, size=720)


def screen_puzzle(user_id: str):
    inject_css(today=date.today(), selected=None)

    st.markdown("<div class='section-title tight'>🧩 Puzzle</div>", unsafe_allow_html=True)

    assets = get_animal_assets()
    if not assets:
        st.error("assets/animals 에 동물 이미지가 없어요. 파일 경로/파일명을 확인해 주세요.")
        return

    run = get_active_run(user_id)

    # -------------------------
    # 1) 시작 UI (active run 없을 때)
    # -------------------------
    if not run:
        section_title("퍼즐 시작하기")

        options = {f"{a.label} ({a.key})": a.key for a in assets}
        choice_label = st.selectbox("동물을 고르세요", list(options.keys()))
        picked_key = options[choice_label]

        c1, c2 = st.columns([1.2, 2.8])
        with c1:
            if st.button("퍼즐 시작", use_container_width=True, key="puz_start"):
                start_new_run(user_id, picked_key)
                st.rerun()
        with c2:
            st.caption("동시에 1개의 퍼즐만 진행돼요. 16일 출석(기록)하면 완성!")

        st.markdown("<hr/>", unsafe_allow_html=True)

    # -------------------------
    # 2) 진행 퍼즐 UI
    # -------------------------
    run = get_active_run(user_id)
    if run:
        # 제목
        label = next((a.label for a in assets if a.key == run.image_key), run.image_key)
        section_title(f"진행 중: {label} 퍼즐")

        # 출석 보상 처리: 버튼 없이 자동 지급해도 되지만,
        # UX상 "지급 상태"를 보여주면서, 새로고침/방문 시 자동 지급되는 형태로 구현
        got, msg = reward_piece_if_possible(user_id)
        if got:
            st.success(msg)
            # 지급 후 마스크 갱신을 위해 rerun
            st.rerun()
        else:
            st.info(msg)

        # 최신 run 다시 로드(지급으로 바뀌었을 수 있음)
        run = get_active_run(user_id)

        # 퍼즐 그리드
        mask = run.unlocked_mask
        opened = sum(1 for ch in mask if ch == "1")
        st.caption(f"진행도: {opened}/16  ·  하루 1조각(오늘 기록 있으면 자동 지급)")

        tiles = _cached_tiles(run.image_key)

        # 4x4 보여주기
        for r in range(4):
            cols = st.columns(4, gap="small")
            for c in range(4):
                idx = r * 4 + c
                if mask[idx] == "1":
                    cols[c].image(tiles[idx], use_container_width=True)
                else:
                    # 잠긴 조각(회색 블록)
                    cols[c].markdown(
                        """
                        <div style="
                          width:100%;
                          aspect-ratio: 1 / 1;
                          background:#e5e7eb;
                          border:1px solid #111111;
                        "></div>
                        """,
                        unsafe_allow_html=True,
                    )

        st.markdown("<hr/>", unsafe_allow_html=True)

    # -------------------------
    # 3) 보관함
    # -------------------------
    section_title("보관함(완성한 동물)")
    col = get_collection(user_id)
    if not col:
        st.caption("아직 완성한 퍼즐이 없어요. 16조각을 모으면 여기에 저장돼요.")
        return

    # 썸네일 그리드 (2~4개씩 보기)
    rows = []
    for item in col:
        rows.append(item)

    per_row = 3
    for i in range(0, len(rows), per_row):
        chunk = rows[i : i + per_row]
        cols = st.columns(per_row, gap="large")
        for j, it in enumerate(chunk):
            k = it["image_key"]
            done = it["completed_at"]
            label = next((a.label for a in assets if a.key == k), k)

            with cols[j]:
                # 첫 타일(좌상단)로 대표 썸네일
                try:
                    tiles = _cached_tiles(k)
                    cols[j].image(tiles[0], use_container_width=True)
                except Exception:
                    pass
                st.markdown(f"**{label}**")
                st.caption(f"완성: {done[:10]}")
