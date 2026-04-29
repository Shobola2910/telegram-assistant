"""
database.py — SQLite database for all bot features
Tasks, Reminders, Notes, Habits, Finance, Plans
"""

import sqlite3
import logging
from datetime import datetime
import pytz
from config import TIMEZONE

logger = logging.getLogger(__name__)
DB_FILE = "lifepilot.db"
tz = pytz.timezone(TIMEZONE)


def now_str():
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")


def today_str():
    return datetime.now(tz).strftime("%Y-%m-%d")


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        priority TEXT DEFAULT 'normal',
        status TEXT DEFAULT 'pending',
        deadline TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        remind_at TEXT NOT NULL,
        repeat TEXT DEFAULT 'none',
        sent INTEGER DEFAULT 0,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        frequency TEXT DEFAULT 'daily',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS habit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER,
        date TEXT,
        done INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL,
        category TEXT DEFAULT 'Other',
        description TEXT,
        date TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person TEXT,
        amount REAL,
        type TEXT,
        note TEXT,
        settled INTEGER DEFAULT 0,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        content TEXT,
        created_at TEXT
    );
    """)
    conn.commit()
    conn.close()
    logger.info("Database ready ✅")


# ── TASKS ─────────────────────────────────────
def task_add(title, priority="normal", deadline=None):
    conn = get_conn()
    conn.execute("INSERT INTO tasks (title,priority,deadline,created_at) VALUES (?,?,?,?)",
                 (title, priority, deadline, now_str()))
    conn.commit(); conn.close()

def task_list(status="pending"):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def task_done(tid):
    conn = get_conn()
    conn.execute("UPDATE tasks SET status='done' WHERE id=?", (tid,))
    conn.commit(); conn.close()

def task_delete(tid):
    conn = get_conn()
    conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
    conn.commit(); conn.close()

def task_stats():
    conn = get_conn()
    rows = conn.execute("SELECT status, COUNT(*) c FROM tasks GROUP BY status").fetchall()
    conn.close(); return {r["status"]: r["c"] for r in rows}


# ── REMINDERS ─────────────────────────────────
def reminder_add(text, remind_at, repeat="none"):
    conn = get_conn()
    conn.execute("INSERT INTO reminders (text,remind_at,repeat,created_at) VALUES (?,?,?,?)",
                 (text, remind_at, repeat, now_str()))
    conn.commit(); conn.close()

def reminder_due():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM reminders WHERE sent=0 AND remind_at<=?", (now_str(),)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def reminder_sent(rid):
    conn = get_conn()
    conn.execute("UPDATE reminders SET sent=1 WHERE id=?", (rid,))
    conn.commit(); conn.close()

def reminder_list(limit=10):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM reminders WHERE sent=0 ORDER BY remind_at ASC LIMIT ?", (limit,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def reminder_delete(rid):
    conn = get_conn()
    conn.execute("DELETE FROM reminders WHERE id=?", (rid,))
    conn.commit(); conn.close()


# ── NOTES ─────────────────────────────────────
def note_add(content, title="", category="general"):
    conn = get_conn()
    conn.execute("INSERT INTO notes (title,content,category,created_at) VALUES (?,?,?,?)",
                 (title, content, category, now_str()))
    conn.commit(); conn.close()

def note_list(category=None, limit=10):
    conn = get_conn()
    if category:
        rows = conn.execute("SELECT * FROM notes WHERE category=? ORDER BY created_at DESC LIMIT ?",
                            (category, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def note_search(query):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM notes WHERE content LIKE ? OR title LIKE ? ORDER BY created_at DESC",
                        (f"%{query}%", f"%{query}%")).fetchall()
    conn.close(); return [dict(r) for r in rows]

def note_delete(nid):
    conn = get_conn()
    conn.execute("DELETE FROM notes WHERE id=?", (nid,))
    conn.commit(); conn.close()


# ── HABITS ────────────────────────────────────
def habit_add(name, frequency="daily"):
    conn = get_conn()
    conn.execute("INSERT INTO habits (name,frequency,created_at) VALUES (?,?,?)",
                 (name, frequency, now_str()))
    conn.commit(); conn.close()

def habit_list():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM habits ORDER BY created_at").fetchall()
    conn.close(); return [dict(r) for r in rows]

def habit_log(habit_id, done=1):
    conn = get_conn()
    today = today_str()
    exists = conn.execute("SELECT id FROM habit_logs WHERE habit_id=? AND date=?", (habit_id, today)).fetchone()
    if exists:
        conn.execute("UPDATE habit_logs SET done=? WHERE habit_id=? AND date=?", (done, habit_id, today))
    else:
        conn.execute("INSERT INTO habit_logs (habit_id,date,done) VALUES (?,?,?)", (habit_id, today, done))
    conn.commit(); conn.close()

def habit_progress(habit_id, days=7):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM habit_logs WHERE habit_id=? ORDER BY date DESC LIMIT ?",
                        (habit_id, days)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def habit_delete(hid):
    conn = get_conn()
    conn.execute("DELETE FROM habits WHERE id=?", (hid,))
    conn.execute("DELETE FROM habit_logs WHERE habit_id=?", (hid,))
    conn.commit(); conn.close()


# ── EXPENSES ──────────────────────────────────
def expense_add(amount, category, description, date=None):
    conn = get_conn()
    conn.execute("INSERT INTO expenses (amount,category,description,date,created_at) VALUES (?,?,?,?,?)",
                 (amount, category, description, date or today_str(), now_str()))
    conn.commit(); conn.close()

def expense_monthly(month=None, year=None):
    now = datetime.now(tz)
    m = month or now.month; y = year or now.year
    prefix = f"{y}-{m:02d}"
    conn = get_conn()
    rows = conn.execute("SELECT * FROM expenses WHERE date LIKE ?", (f"{prefix}%",)).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]
    total = sum(r["amount"] for r in rows)
    by_cat = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["amount"]
    return {"total": total, "by_category": by_cat, "rows": rows}

def expense_recent(n=5):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM expenses ORDER BY created_at DESC LIMIT ?", (n,)).fetchall()
    conn.close(); return [dict(r) for r in rows]


# ── DEBTS ─────────────────────────────────────
def debt_add(person, amount, dtype, note=""):
    conn = get_conn()
    conn.execute("INSERT INTO debts (person,amount,type,note,created_at) VALUES (?,?,?,?,?)",
                 (person, amount, dtype, note, now_str()))
    conn.commit(); conn.close()

def debt_list():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM debts WHERE settled=0 ORDER BY created_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def debt_settle(did):
    conn = get_conn()
    conn.execute("UPDATE debts SET settled=1 WHERE id=?", (did,))
    conn.commit(); conn.close()


# ── PLANS ─────────────────────────────────────
def plan_save(content, date=None):
    conn = get_conn()
    d = date or today_str()
    conn.execute("DELETE FROM plans WHERE date=?", (d,))
    conn.execute("INSERT INTO plans (date,content,created_at) VALUES (?,?,?)", (d, content, now_str()))
    conn.commit(); conn.close()

def plan_get(date=None):
    conn = get_conn()
    d = date or today_str()
    row = conn.execute("SELECT * FROM plans WHERE date=?", (d,)).fetchone()
    conn.close(); return dict(row) if row else None
