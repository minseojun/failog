# failog/habits_tasks.py
from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional, Tuple

import pandas as pd

from failog.db import conn, now_iso


# ============================================================
# Date helpers (screens_planner에서 주간 habit task 생성에 사용)
# ============================================================
def week_days(ws: date) -> List[date]:
    return [ws + timedelta(days=i) for i in range(7)]


# ============================================================
# Habits
# ============================================================
def list_habits(user_id: str, active_only: bool = True) -> pd.DataFrame:
    c = conn()
    q = "SELECT id, title, dow_mask, active FROM habits WHERE user_id=?"
    params = [user_id]
    if active_only:
        q += " AND active=1"
    q += " ORDER BY id DESC"
    df = pd.read_sql_query(q, c, params=params)
    c.close()
    return df


def add_habit(user_id: str, title: str, dows: List[int]):
    title = (title or "").strip()
    if not title:
        return

    mask = ["0"] * 7
    for i in dows:
        try:
            ii = int(i)
        except Exception:
            continue
        if 0 <= ii <= 6:
            mask[ii] = "1"
    dow_mask = "".join(mask)

    c = conn()
    c.execute(
        """
        INSERT INTO habits(user_id, title, dow_mask, active, created_at, updated_at)
        VALUES (?,?,?,1,?,?)
        """,
        (user_id, title, dow_mask, now_iso(), now_iso()),
    )
    c.commit()
    c.close()


def set_habit_active(user_id: str, habit_id: int, active: bool):
    c = conn()
    c.execute(
        "UPDATE habits SET active=?, updated_at=? WHERE user_id=? AND id=?",
        (1 if active else 0, now_iso(), user_id, int(habit_id)),
    )
    c.commit()
    c.close()


def delete_habit(user_id: str, habit_id: int):
    today = date.today().isoformat()
    c = conn()
    cur = c.cursor()

    # 미래/오늘 todo habit task 정리
    cur.execute(
        """
        DELETE FROM tasks
        WHERE user_id=? AND source='habit' AND habit_id=? AND task_date>=? AND status='todo'
        """,
        (user_id, int(habit_id), today),
    )

    # habit 삭제
    cur.execute("DELETE FROM habits WHERE user_id=? AND id=?", (user_id, int(habit_id)))

    c.commit()
    c.close()


# ============================================================
# Tasks (plan/habit)
# ============================================================
def ensure_week_habit_tasks(user_id: str, ws: date):
    habits = list_habits(user_id, active_only=True)
    if habits.empty:
        return

    days = week_days(ws)
    c = conn()
    cur = c.cursor()

    for _, h in habits.iterrows():
        hid = int(h["id"])
        title = str(h["title"])
        mask = str(h["dow_mask"] or "0000000")
        if len(mask) != 7:
            mask = "0000000"

        for d in days:
            wd = d.weekday()  # Mon=0
            if mask[wd] == "1":
                # UNIQUE(user_id, task_date, source, habit_id, text) 때문에 OR IGNORE 안전
                cur.execute(
                    """
                    INSERT OR IGNORE INTO tasks
                      (user_id, task_date, text, source, habit_id, status, fail_reason, created_at, updated_at)
                    VALUES (?,?,?,?,?,'todo',NULL,?,?)
                    """,
                    (user_id, d.isoformat(), title, "habit", hid, now_iso(), now_iso()),
                )

    c.commit()
    c.close()


def add_plan_task(user_id: str, d: date, text: str):
    text = (text or "").strip()
    if not text:
        return

    c = conn()
    # plan도 중복 방지(유니크 걸릴 수 있음) 위해 OR IGNORE
    c.execute(
        """
        INSERT OR IGNORE INTO tasks
          (user_id, task_date, text, source, habit_id, status, fail_reason, created_at, updated_at)
        VALUES (?,?,?,?,?,'todo',NULL,?,?)
        """,
        (user_id, d.isoformat(), text, "plan", None, now_iso(), now_iso()),
    )
    c.commit()
    c.close()


def delete_task(user_id: str, task_id: int):
    c = conn()
    c.execute("DELETE FROM tasks WHERE user_id=? AND id=?", (user_id, int(task_id)))
    c.commit()
    c.close()


def list_tasks_for_date(user_id: str, d: date) -> pd.DataFrame:
    c = conn()
    df = pd.read_sql_query(
        """
        SELECT id, task_date, text, source, habit_id, status, fail_reason
        FROM tasks
        WHERE user_id=? AND task_date=?
        ORDER BY source DESC, id DESC
        """,
        c,
        params=(user_id, d.isoformat()),
    )
    c.close()
    return df


def update_task_status(user_id: str, task_id: int, status: str):
    c = conn()
    c.execute(
        "UPDATE tasks SET status=?, updated_at=? WHERE user_id=? AND id=?",
        (status, now_iso(), user_id, int(task_id)),
    )
    if status != "fail":
        c.execute(
            "UPDATE tasks SET fail_reason=NULL, updated_at=? WHERE user_id=? AND id=?",
            (now_iso(), user_id, int(task_id)),
        )
    c.commit()
    c.close()


def update_task_fail(user_id: str, task_id: int, reason: str):
    reason = (reason or "").strip() or "이유 미기록"
    c = conn()
    c.execute(
        "UPDATE tasks SET status='fail', fail_reason=?, updated_at=? WHERE user_id=? AND id=?",
        (reason, now_iso(), user_id, int(task_id)),
    )
    c.commit()
    c.close()


def count_today_todos(user_id: str) -> int:
    today = date.today().isoformat()
    c = conn()
    row = c.execute(
        "SELECT COUNT(*) FROM tasks WHERE user_id=? AND task_date=? AND status='todo'",
        (user_id, today),
    ).fetchone()
    c.close()
    return int(row[0] if row else 0)


# ✅ screens_planner가 필요로 하는 함수 (지금 ImportError의 원인)
def get_habit_task_for_date(
    user_id: str, d: date, habit_id: int
) -> Optional[Tuple[int, str, str]]:
    """
    Returns (task_id, status, fail_reason) for a habit task on date d.
    If not found, returns None.
    """
    c = conn()
    row = c.execute(
        """
        SELECT id, status, COALESCE(fail_reason,'')
        FROM tasks
        WHERE user_id=? AND task_date=? AND source='habit' AND habit_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, d.isoformat(), int(habit_id)),
    ).fetchone()
    c.close()
    if not row:
        return None
    return (int(row[0]), str(row[1]), str(row[2] or ""))


# ============================================================
# Range / analytics helpers (Failure screen에서 사용)
# ============================================================
def get_tasks_range(user_id: str, start_d: date, end_d: date) -> pd.DataFrame:
    c = conn()
    df = pd.read_sql_query(
        """
        SELECT id, task_date, text, source, habit_id, status, fail_reason
        FROM tasks
        WHERE user_id=? AND task_date BETWEEN ? AND ?
        ORDER BY task_date ASC, id DESC
        """,
        c,
        params=(user_id, start_d.isoformat(), end_d.isoformat()),
    )
    c.close()
    return df


def get_all_failures(user_id: str, limit: int = 350) -> pd.DataFrame:
    c = conn()
    df = pd.read_sql_query(
        """
        SELECT task_date, text, source, habit_id, fail_reason
        FROM tasks
        WHERE user_id=? AND status='fail'
        ORDER BY task_date DESC
        LIMIT ?
        """,
        c,
        params=(user_id, int(limit)),
    )
    c.close()
    return df
