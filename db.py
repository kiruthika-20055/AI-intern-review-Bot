import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), "data", "app.db")

def conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS interns(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL, name TEXT, phone TEXT, college TEXT, department TEXT);
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE, intern_email TEXT NOT NULL,
        title TEXT, description TEXT, requirements TEXT, deadline TEXT,
        status TEXT DEFAULT 'assigned',   -- assigned | completed | review_scheduled | reviewed
        submission TEXT DEFAULT '', review_dt TEXT, meet_link TEXT, reminded INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER UNIQUE,
        transcript TEXT DEFAULT '[]', report TEXT, score INTEGER, created TEXT);
    """)
    c.commit(); c.close()

def q(sql, args=(), one=False):
    c = conn(); r = c.execute(sql, args).fetchall(); c.close()
    return (r[0] if r else None) if one else r

def ex(sql, args=()):
    c = conn(); cur = c.execute(sql, args); c.commit(); i = cur.lastrowid; c.close(); return i
