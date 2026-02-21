# failog/habits_tasks.py
from datetime import date
from typing import List, Optional

import pandas as pd

from failog.db import conn, now_iso
from failog.dates import week_days


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
        if 0 <= i <= 6:
            mask[i] = "1"
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
        (1 if active else 0, now_iso(), user_id, habit_id),
    )
    c.commit()
    c.close()


def delete_habit(user_id: str, habit_id: int):
    today = date.today().isoformat()
    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        DELETE FROM tasks
        WHERE user_id=? AND source='habit' AND habit_id=? AND task_date>=? AND status='todo'
        """,
        (user_id, habit_id, today),
    )
    cur.execute("DELETE FROM habits WHERE user_id=? AND id=?", (user_id, habit_id))
    c.commit()
    c.close()


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
        for d in days:
            if mask[d.weekday()] == "1":
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
    c.execute(
        """
        INSERT INTO tasks
          (user_id, task_date, text, source, habit_id, status, fail_reason, created_at, updated_at)
        VALUES (?,?,?,?,?,'todo',NULL,?,?)
        """,
        (user_id, d.isoformat(), text, "plan", None, now_iso(), now_iso()),
    )
    c.commit()
    c.close()


def delete_task(user_id: str, task_id: int):
    c = conn()
    c.execute("DELETE FROM tasks WHERE user_id=? AND id=?", (user_id, task_id))
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
        (status, now_iso(), user_id, task_id),
    )
    if status != "fail":
        c.execute(
            "UPDATE tasks SET fail_reason=NULL, updated_at=? WHERE user_id=? AND id=?",
            (now_iso(), user_id, task_id),
        )
    c.commit()
    c.close()


def update_task_fail(user_id: str, task_id: int, reason: str):
    reason = (reason or "").strip() or "이유 미기록"
    c = conn()
    c.execute(
        "UPDATE tasks SET status='fail', fail_reason=?, updated_at=? WHERE user_id=? AND id=?",
        (reason, now_iso(), user_id, task_id),
    )
    c.commit()
    c.close()


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
        params=(user_id, limit),
    )
    c.close()
    return df


def count_today_todos(user_id: str) -> int:
    today = date.today().isoformat()
    c = conn()
    row = c.execute(
        "SELECT COUNT(*) FROM tasks WHERE user_id=? AND task_date=? AND status='todo'",
        (user_id, today),
    ).fetchone()
    c.close()
    return int(row[0] if row else 0)
