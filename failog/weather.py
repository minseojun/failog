# failog/weather.py
from datetime import date
from typing import Any, Dict, Optional

import requests
import streamlit as st

from failog.cookies import ck_get, ck_set
from failog.dates import korean_dow


WEATHER_CODE_KO = {
    0: "맑음",
    1: "대체로 맑음",
    2: "부분적으로 흐림",
    3: "흐림",
    45: "안개",
    48: "서리 안개",
    51: "이슬비(약)",
    53: "이슬비(중)",
    55: "이슬비(강)",
    61: "비(약)",
    63: "비(중)",
    65: "비(강)",
    71: "눈(약)",
    73: "눈(중)",
    75: "눈(강)",
    80: "소나기(약)",
    81: "소나기(중)",
    82: "소나기(강)",
    95: "뇌우",
}


@st.cache_data(ttl=60 * 60, show_spinner=False)
def geocode_city(city_name: str) -> Optional[Dict[str, Any]]:
    city_name = (city_name or "").strip()
    if not city_name:
        return None
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1, "language": "ko", "format": "json"}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    js = r.json()
    results = js.get("results") or []
    return results[0] if results else None


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_daily_weather(lat: float, lon: float, d: date, tz: str = "Asia/Seoul") -> Optional[Dict[str, Any]]:
    base = "https://archive-api.open-meteo.com/v1/archive" if d <= date.today() else "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": float(lat),
        "longitude": float(lon),
        "timezone": tz,
        "start_date": d.isoformat(),
        "end_date": d.isoformat(),
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
    }
    r = requests.get(base, params=params, timeout=10)
    r.raise_for_status()
    js = r.json()
    daily = js.get("daily") or {}
    times = daily.get("time") or []
    if not times:
        return None

    idx = 0
    code = (daily.get("weathercode") or [None])[idx]
    tmax = (daily.get("temperature_2m_max") or [None])[idx]
    tmin = (daily.get("temperature_2m_min") or [None])[idx]
    psum = (daily.get("precipitation_sum") or [None])[idx]
    pprob = (daily.get("precipitation_probability_max") or [None])[idx]

    return {
        "date": d.isoformat(),
        "weathercode": code,
        "desc": WEATHER_CODE_KO.get(int(code), f"code {code}") if code is not None else "—",
        "tmax": tmax,
        "tmin": tmin,
        "precip_sum": psum,
        "precip_prob": pprob,
    }


def weather_card(selected: date):
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### 🌤️ Weather (Open-Meteo)")

    default_city = ck_get("failog_city", "Seoul")
    city = st.text_input("도시/지역", value=default_city, key="weather_city_input", help="예: Seoul, Busan, Tokyo")

    colA, colB = st.columns([1, 1])
    with colA:
        if st.button("도시 저장", use_container_width=True, key="weather_save_city"):
            ck_set("failog_city", (city or "Seoul").strip())
            st.success("저장됐어요.")
            st.rerun()
    with colB:
        show = st.toggle("표시", value=(ck_get("failog_weather_show", "true") == "true"), key="weather_show_toggle")
        ck_set("failog_weather_show", "true" if show else "false")

    if ck_get("failog_weather_show", "true") != "true":
        st.markdown("<div class='small'>날씨 표시가 꺼져 있어요.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    try:
        geo = geocode_city(city)
        if not geo:
            st.warning("도시를 찾지 못했어요. 다른 이름으로 시도해보세요.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        lat, lon = geo["latitude"], geo["longitude"]
        label = f"{geo.get('name','')} · {geo.get('country','')}"
        w = fetch_daily_weather(lat, lon, selected, tz="Asia/Seoul")
        if not w:
            st.info("해당 날짜의 날씨 데이터가 없어요.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        st.markdown(
            f"<span class='pill pill-strong'>{label}</span> "
            f"<span class='pill'>{selected.isoformat()} ({korean_dow(selected.weekday())})</span>",
            unsafe_allow_html=True,
        )
        st.write("")
        c1, c2, c3 = st.columns(3)
        c1.metric("상태", w["desc"])
        tmax = w["tmax"]
        tmin = w["tmin"]
        c2.metric("기온", f"{tmin:.0f}° ~ {tmax:.0f}°" if tmin is not None and tmax is not None else "—")
        pp = w.get("precip_prob")
        ps = w.get("precip_sum")
        c3.metric("강수", f"{pp}% / {ps}mm" if pp is not None and ps is not None else "—")
        st.caption("데이터 출처: Open-Meteo")
    except Exception as e:
        st.error(f"날씨 로딩 실패: {type(e).__name__}")
    finally:
        st.markdown("</div>", unsafe_allow_html=True)
