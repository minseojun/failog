# failog/constants.py
import os
from zoneinfo import ZoneInfo

# Optional autorefresh
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# Optional cookie manager (prefs only; NOT used for user_id)
try:
    import extra_streamlit_components as stx
except Exception:
    stx = None

# OpenAI SDK
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# -------------------------
# Constants
# -------------------------
KST = ZoneInfo("Asia/Seoul")
DB_PATH = "planner.db"

# Theme / colors
ACCENT_BLUE = "#A0C4F2"
TEXT_DARK = "#1f2430"

# Dashboard fixed params (per your request)
DASH_TREND_WEEKS = 8
DASH_TOPK = 6
CATEGORY_MAX = 7
CATEGORY_MAP_WINDOW_WEEKS = 12

# PDF font
FONTS_DIR = "fonts"
KOREAN_FONT_PATH = os.path.join(FONTS_DIR, "NanumGothic-Regular.ttf")
KOREAN_FONT_NAME = "NanumGothicRegular"
NANUM_TTF_URL = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"

# Consent (privacy/AI usage)
CONSENT_COOKIE_KEY = "failog_ai_consent"  # "true"/"false"
