# failog/db.py
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from failog.constants import DB_PATH, KST


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

    # Category map cache (per user) — keep as original
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS category_maps (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          window_weeks INTEGER NOT NULL,
          max_categories INTEGER NOT NULL,
          payload_json TEXT NOT NULL
        );
        """
    )

    c.commit()
    c.close()


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


def add_habit(user_id: str, title: str, dows: List[int]) -> None:
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
    원래 단일파일과 동일:
    - 오늘 이후의 'todo' habit task 삭제
    - habits row 삭제
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
def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_days(ws: date) -> List[date]:
    return [ws + timedelta(days=i) for i in range(7)]


def ensure_week_habit_tasks(user_id: str, ws: date) -> None:
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
            if len(mask) == 7 and mask[d.weekday()] == "1":
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
# NEW: Requirement #5 helper (habit manager can update selected-day habit task)
# =========================================================
def get_habit_task_for_date(
    user_id: str,
    d: date,
    habit_id: int,
) -> Optional[Tuple[int, str, str]]:
    """
    Returns (task_id, status, fail_reason) for habit task on date d, if exists.
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


# =========================================================
# (Dashboard/AI uses these) — keep originals available
# =========================================================
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


def db_get_latest_category_map(user_id: str) -> Optional[Dict[str, Any]]:
    c = conn()
    row = c.execute(
        """
        SELECT payload_json
        FROM category_maps
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    c.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def db_save_category_map(user_id: str, payload: Dict[str, Any], window_weeks: int, max_categories: int) -> None:
    c = conn()
    c.execute(
        """
        INSERT INTO category_maps(user_id, created_at, window_weeks, max_categories, payload_json)
        VALUES (?,?,?,?,?)
        """,
        (user_id, now_iso(), int(window_weeks), int(max_categories), json.dumps(payload, ensure_ascii=False)),
    )
    c.commit()
    c.close()
