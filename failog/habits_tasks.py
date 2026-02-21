from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
from zoneinfo import ZoneInfo

# ---- Constants (keep same as original single-file) ----
KST = ZoneInfo("Asia/Seoul")
DB_PATH = "planner.db"


# =========================================================
# Core DB helpers
# =========================================================
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("PRAGMA foreign_keys = ON;")
    return c


def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def init_db() -> None:
    """
    Keep schema identical to your original single-file app.
    This module covers habits/tasks only.
    """
    c = conn()
    cur = c.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS habits (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          title TEXT NOT NULL,
          dow_mask TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          task_date TEXT NOT NULL,
          text TEXT NOT NULL,
          source TEXT NOT NULL CHECK(source IN ('plan','habit')),
          habit_id INTEGER,
          status TEXT NOT NULL CHECK(status IN ('todo','success','fail')) DEFAULT 'todo',
          fail_reason TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(user_id, task_date, source, habit_id, text)
        );
        """
    )

    c.commit()
    c.close()


# =========================================================
# Date helpers (minimal)
# =========================================================
def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_days(ws: date):
    return [ws + timedelta(days=i) for i in range(7)]


# =========================================================
# Habits
# =========================================================
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


def add_habit(user_id: str, title: str, dows: list[int]) -> None:
    title = (title or "").strip()
    if not title:
        return

    mask = ["0"] * 7
    for i in dows:
        if 0 <= int(i) <= 6:
            mask[int(i)] = "1"
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


def set_habit_active(user_id: str, habit_id: int, active: bool) -> None:
    c = conn()
    c.execute(
        "UPDATE habits SET active=?, updated_at=? WHERE user_id=? AND id=?",
        (1 if active else 0, now_iso(), user_id, int(habit_id)),
    )
    c.commit()
    c.close()


def delete_habit(user_id: str, habit_id: int) -> None:
    """
    Same as original:
    - delete future todo habit tasks for this habit
    - delete habit row
    """
    today = date.today().isoformat()
    c = conn()
    cur = c.cursor()
    cur.execute(
        """
        DELETE FROM tasks
        WHERE user_id=? AND source='habit' AND habit_id=? AND task_date>=? AND status='todo'
        """,
        (user_id, int(habit_id), today),
    )
    cur.execute("DELETE FROM habits WHERE user_id=? AND id=?", (user_id, int(habit_id)))
    c.commit()
    c.close()


# =========================================================
# Habit → weekly task materialization
# =========================================================
def ensure_week_habit_tasks(user_id: str, ws: date) -> None:
    """
    Create habit tasks for the given week (Mon-Sun) for all active habits.
    Uses INSERT OR IGNORE to avoid duplicates.
    """
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


# =========================================================
# Tasks
# =========================================================
def add_plan_task(user_id: str, d: date, text: str) -> None:
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


def delete_task(user_id: str, task_id: int) -> None:
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


def update_task_status(user_id: str, task_id: int, status: str) -> None:
    """
    status in ('todo','success','fail')
    - If status != 'fail', clear fail_reason
    """
    status = (status or "").strip()
    if status not in ("todo", "success", "fail"):
        return

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


def update_task_fail(user_id: str, task_id: int, reason: str) -> None:
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


# =========================================================
# NEW (for requirement #5):
# habit manager can operate on the habit-task of selected date
# =========================================================
def get_habit_task_for_date(
    user_id: str,
    d: date,
    habit_id: int,
) -> Optional[Tuple[int, str, str]]:
    """
    Returns (task_id, status, fail_reason) for the habit task on date d, if exists.
    - Used by Habit manager UI to allow success/fail/reason updates directly.
    """
    c = conn()
    row = c.execute(
        """
        SELECT id, status, COALESCE(fail_reason,'')
        FROM tasks
        WHERE user_id=? AND task_date=? AND source='habit' AND habit_id=?
        LIMIT 1
        """,
        (user_id, d.isoformat(), int(habit_id)),
    ).fetchone()
    c.close()

    if not row:
        return None
    return int(row[0]), str(row[1]), str(row[2] or "")


def ensure_habit_task_for_date(
    user_id: str,
    d: date,
    habit_id: int,
) -> Optional[int]:
    """
    Optional helper:
    - Ensures a habit-task exists for (user_id, d, habit_id) IF the habit is active and scheduled on that weekday.
    - Returns task_id if created/found, else None.

    You don't strictly need this if your app already calls ensure_week_habit_tasks().
    But it's handy when UI wants to be robust.
    """
    # 1) load habit
    c = conn()
    row = c.execute(
        """
        SELECT title, dow_mask, active
        FROM habits
        WHERE user_id=? AND id=?
        """,
        (user_id, int(habit_id)),
    ).fetchone()

    if not row:
        c.close()
        return None

    title, dow_mask, active = str(row[0]), str(row[1] or "0000000"), int(row[2])
    if active != 1:
        c.close()
        return None

    if len(dow_mask) != 7 or dow_mask[d.weekday()] != "1":
        c.close()
        return None

    # 2) insert or ignore
    c.execute(
        """
        INSERT OR IGNORE INTO tasks
          (user_id, task_date, text, source, habit_id, status, fail_reason, created_at, updated_at)
        VALUES (?,?,?,?,?,'todo',NULL,?,?)
        """,
        (user_id, d.isoformat(), title, "habit", int(habit_id), now_iso(), now_iso()),
    )
    c.commit()

    # 3) fetch id
    row2 = c.execute(
        """
        SELECT id FROM tasks
        WHERE user_id=? AND task_date=? AND source='habit' AND habit_id=?
        LIMIT 1
        """,
        (user_id, d.isoformat(), int(habit_id)),
    ).fetchone()
    c.close()

    return int(row2[0]) if row2 else None


# failog/habits_tasks.py 에 반드시 포함되어야 하는 함수들

from __future__ import annotations

from datetime import date
import pandas as pd

from failog.db import conn


def get_tasks_range(user_id: str, start_d: date, end_d: date) -> pd.DataFrame:
    """
    단일파일 버전과 동일:
    tasks 테이블에서 user_id 기준으로 start_d~end_d(포함) 범위를 조회
    """
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
    """
    단일파일 버전과 동일:
    status='fail'만 최근 날짜순으로 limit개 조회
    """
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
