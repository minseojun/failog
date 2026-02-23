# failog/db.py
import sqlite3
from datetime import datetime

from failog.constants import DB_PATH, KST


def conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("PRAGMA foreign_keys = ON;")
    return c


def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def init_db():
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

    # ✅ 퍼즐 상태 테이블: 유저당 1개의 진행 퍼즐을 가정(원하면 여러개로 확장 가능)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_state (
          user_id TEXT PRIMARY KEY,
          category TEXT NOT NULL,
          image_path TEXT NOT NULL,
          reveal_order TEXT NOT NULL,   -- JSON list[int] length 16
          revealed_mask TEXT NOT NULL,  -- "0100..." length 16
          last_award_date TEXT,         -- "YYYY-MM-DD"
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )

    # ✅ 완성본 보관함(갤러리)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_gallery (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          category TEXT NOT NULL,
          image_path TEXT NOT NULL,
          completed_on TEXT NOT NULL,  -- "YYYY-MM-DD"
          created_at TEXT NOT NULL
        );
        """
    )

    c.commit()
    c.close()
