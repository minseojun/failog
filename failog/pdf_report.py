# failog/pdf_report.py
import io
import os
from datetime import date, datetime, timedelta
from typing import Any, List

import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from failog.constants import (
    FONTS_DIR,
    KOREAN_FONT_PATH,
    KOREAN_FONT_NAME,
    NANUM_TTF_URL,
    TEXT_DARK,
    KST,
)
from failog.db import get_tasks_range
from failog.dates import korean_dow


def ensure_korean_font_downloaded() -> bool:
    try:
        os.makedirs(FONTS_DIR, exist_ok=True)
        if os.path.exists(KOREAN_FONT_PATH) and os.path.getsize(KOREAN_FONT_PATH) > 50_000:
            return True

        r = requests.get(NANUM_TTF_URL, timeout=20)
        r.raise_for_status()
        with open(KOREAN_FONT_PATH, "wb") as f:
            f.write(r.content)
        return os.path.exists(KOREAN_FONT_PATH) and os.path.getsize(KOREAN_FONT_PATH) > 50_000
    except Exception:
        return False


def register_korean_font() -> str:
    if st.session_state.get("__pdf_font_registered__", False):
        return st.session_state.get("__pdf_font_name__", "Helvetica")

    ok = ensure_korean_font_downloaded()
    if ok:
        try:
            pdfmetrics.registerFont(TTFont(KOREAN_FONT_NAME, KOREAN_FONT_PATH))
            st.session_state["__pdf_font_registered__"] = True
            st.session_state["__pdf_font_name__"] = KOREAN_FONT_NAME
            return KOREAN_FONT_NAME
        except Exception:
            pass

    st.session_state["__pdf_font_registered__"] = True
    st.session_state["__pdf_font_name__"] = "Helvetica"
    return "Helvetica"


def failures_by_dow(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame({"dow": ["월", "화", "수", "목", "금", "토", "일"], "fail_count": [0] * 7})
    x = df.copy()
    x["task_date"] = pd.to_datetime(x["task_date"]).dt.date
    x = x[x["status"] == "fail"]
    rows = []
    for i in range(7):
        dname = korean_dow(i)
        rows.append({"dow": dname, "fail_count": int((x["task_date"].map(lambda d: d.weekday()) == i).sum())})
    return pd.DataFrame(rows)


def top_reasons(df: pd.DataFrame, topk: int = 8) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["reason", "count"])
    x = df[df["status"] == "fail"].copy()
    s = x["fail_reason"].fillna("").map(lambda v: str(v).strip())
    s = s[s != ""]
    vc = s.value_counts().head(topk)
    return pd.DataFrame({"reason": vc.index.tolist(), "count": vc.values.tolist()})


def make_matplotlib_bar_png(data: pd.DataFrame, xcol: str, ycol: str, title: str) -> bytes:
    fig = plt.figure(figsize=(6.2, 2.4), dpi=160)
    ax = fig.add_subplot(111)
    ax.bar(data[xcol].tolist(), data[ycol].tolist())
    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel("")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def build_weekly_pdf_bytes(user_id: str, ws: date, city_label: str = "") -> bytes:
    we = ws + timedelta(days=6)
    df = get_tasks_range(user_id, ws, we)

    counts = {
        "total": int(len(df)),
        "success": int((df["status"] == "success").sum()) if not df.empty else 0,
        "fail": int((df["status"] == "fail").sum()) if not df.empty else 0,
        "todo": int((df["status"] == "todo").sum()) if not df.empty else 0,
    }

    font_name = register_korean_font()
    styles = getSampleStyleSheet()
    base = ParagraphStyle(name="Base", parent=styles["Normal"], fontName=font_name, fontSize=10.5, leading=14)
    h1 = ParagraphStyle(name="H1", parent=styles["Heading1"], fontName=font_name, fontSize=16, leading=20, spaceAfter=8)
    h2 = ParagraphStyle(name="H2", parent=styles["Heading2"], fontName=font_name, fontSize=12.5, leading=16, spaceBefore=8, spaceAfter=6)
    small = ParagraphStyle(name="Small", parent=styles["Normal"], fontName=font_name, fontSize=9.5, leading=12, textColor=colors.HexColor("#444444"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="FAILOG Weekly Report",
    )

    story: List[Any] = []
    story.append(Paragraph("FAILOG · Weekly Report", h1))
    story.append(Paragraph(f"기간: {ws.isoformat()} ~ {we.isoformat()} (KST)", base))
    if city_label.strip():
        story.append(Paragraph(f"날씨 기준 도시: {city_label}", small))
    story.append(Paragraph(f"생성 시각: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} (KST)", small))
    story.append(Spacer(1, 10))

    story.append(Paragraph("요약", h2))
    tdata = [["Total", "Success", "Fail", "Todo"], [str(counts["total"]), str(counts["success"]), str(counts["fail"]), str(counts["todo"])]]
    table = Table(tdata, colWidths=[35 * mm, 35 * mm, 35 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(TEXT_DARK)),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#BBD7F6")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("실패 분포(요일)", h2))
    dow_df = failures_by_dow(df)
    png1 = make_matplotlib_bar_png(dow_df, "dow", "fail_count", "Failures by Day of Week")
    story.append(RLImage(io.BytesIO(png1), width=170 * mm, height=58 * mm))
    story.append(Spacer(1, 8))

    story.append(Paragraph("실패 원인 TOP", h2))
    tr = top_reasons(df, topk=8)
    if tr.empty:
        story.append(Paragraph("이번 주에는 실패 원인 텍스트가 없어요.", base))
    else:
        rdata = [["원인", "횟수"]] + [[row["reason"], str(int(row["count"]))] for _, row in tr.iterrows()]
        rtable = Table(rdata, colWidths=[140 * mm, 25 * mm])
        rtable.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3FF")),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.8),
                    ("ALIGN", (1, 1), (1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBD7F6")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(rtable)

    story.append(Spacer(1, 10))
    story.append(Paragraph("실패 목록", h2))
    if df.empty:
        story.append(Paragraph("이번 주에는 기록이 없어요.", base))
    else:
        f = df[df["status"] == "fail"].copy()
        if f.empty:
            story.append(Paragraph("이번 주에는 실패가 없어요. 🎉", base))
        else:
            f["task_date"] = pd.to_datetime(f["task_date"]).dt.date
            f = f.sort_values(["task_date", "id"], ascending=[True, True]).head(80)
            for _, row in f.iterrows():
                d0 = row["task_date"]
                dtxt = f"{d0.isoformat()} ({korean_dow(d0.weekday())})"
                task = str(row["text"])
                src = "Habit" if row["source"] == "habit" else "Plan"
                reason = str(row["fail_reason"] or "").strip()
                story.append(Paragraph(f"• {dtxt} · [{src}] {task}", base))
                if reason:
                    story.append(Paragraph(f"&nbsp;&nbsp;↳ 이유: {reason}", small))
                story.append(Spacer(1, 2))

    doc.build(story)
    buf.seek(0)
    return buf.read()
