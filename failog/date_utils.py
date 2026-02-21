# failog/date_utils.py
from datetime import date, timedelta
from typing import List, Optional

def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())

def korean_dow(i: int) -> str:
    return ["월", "화", "수", "목", "금", "토", "일"][i]

def month_grid(year: int, month: int) -> List[List[Optional[date]]]:
    first = date(year, month, 1)
    first_wd = first.weekday()
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = nxt - timedelta(days=1)

    grid: List[List[Optional[date]]] = []
    row: List[Optional[date]] = [None] * 7
    day = 1
    idx = first_wd

    while day <= last.day:
        row[idx] = date(year, month, day)
        day += 1
        idx += 1
        if idx == 7:
            grid.append(row)
            row = [None] * 7
            idx = 0

    if any(x is not None for x in row):
        grid.append(row)
    return grid
