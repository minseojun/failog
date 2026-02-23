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

    # =========================================================
    # 🧩 PUZZLE TABLES (없으면 보관함/상태 로드에서 터짐)
    # =========================================================
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_state (
          user_id TEXT PRIMARY KEY,
          category TEXT NOT NULL,
          image_path TEXT NOT NULL,
          seed INTEGER NOT NULL,
          revealed_json TEXT NOT NULL,
          last_award_date TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          completed_at TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_gallery (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          category TEXT NOT NULL,
          image_path TEXT NOT NULL,
          completed_at TEXT NOT NULL
        );
        """
    )

    c.commit()
    c.close()
