import sqlite3
import re
import os

DB_NAME = os.getenv("DB_NAME", "songs.db")

# ---------------- INIT DB ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS songs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        message_id INTEGER UNIQUE,
        song TEXT,
        artist TEXT,
        search_blob TEXT
    )
    """)

    conn.commit()
    conn.close()

# ---------------- NORMALIZE ----------------
def normalize(text):
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ---------------- ADD SONG ----------------
def add_song(chat_id, message_id, song, artist):
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cur = conn.cursor()

    blob = normalize(song + " " + artist)

    cur.execute("""
    INSERT OR REPLACE INTO songs(
        chat_id,
        message_id,
        song,
        artist,
        search_blob
    )
    VALUES (?, ?, ?, ?, ?)
    """, (chat_id, message_id, song, artist, blob))

    conn.commit()
    conn.close()

# ---------------- SEARCH ----------------
def search_songs(query, limit=20):
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cur = conn.cursor()

    q = normalize(query)
    words = q.split()

    if not words:
        return []

    conditions = []
    params = []

    for w in words:
        conditions.append("search_blob LIKE ?")
        params.append(f"%{w}%")

    where_sql = " AND ".join(conditions)

    cur.execute(f"""
    SELECT chat_id, message_id, song, artist
    FROM songs
    WHERE {where_sql}
    LIMIT ?
    """, params + [limit])

    rows = cur.fetchall()
    conn.close()

    return rows

# ---------------- GET SONG ----------------
def get_song(message_id):
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cur = conn.cursor()

    cur.execute("""
    SELECT chat_id, message_id, song, artist
    FROM songs
    WHERE message_id = ?
    """, (message_id,))

    row = cur.fetchone()
    conn.close()

    return row

# ---------------- COUNT ----------------
def get_count():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM songs")
    count = cur.fetchone()[0]

    conn.close()
    return count