import sqlite3
import os
import uuid
from datetime import datetime

DB_PATH = "./chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            source TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

def create_session(title="New Chat", session_id=None):
    if session_id is None:
        session_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions (id, title) VALUES (?, ?)", (session_id, title))
    conn.commit()
    conn.close()
    return session_id

def rename_session(session_id, new_title):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id))
    conn.commit()
    conn.close()

def get_all_sessions():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, created_at FROM sessions ORDER BY created_at DESC")
    sessions = [{"id": row[0], "title": row[1], "created_at": row[2]} for row in cursor.fetchall()]
    conn.close()
    return sessions

def delete_session(session_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

def add_message(session_id, role, content, source=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (session_id, role, content, source) VALUES (?, ?, ?, ?)",
        (session_id, role, content, source)
    )
    conn.commit()
    conn.close()

def get_messages(session_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content, source, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
    messages = [{"role": row[0], "content": row[1], "source": row[2], "timestamp": row[3]} for row in cursor.fetchall()]
    conn.close()
    return messages

def export_db_to_dict():
    """Returns a dict representation of the entire SQLite DB for export."""
    data = {"sessions": [], "messages": []}
    conn = sqlite3.connect(DB_PATH)
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, created_at FROM sessions")
    for row in cursor.fetchall():
        data["sessions"].append({"id": row[0], "title": row[1], "created_at": row[2]})
        
    cursor.execute("SELECT id, session_id, role, content, source, timestamp FROM messages")
    for row in cursor.fetchall():
        data["messages"].append({
            "id": row[0], "session_id": row[1], "role": row[2], 
            "content": row[3], "source": row[4], "timestamp": row[5]
        })
        
    conn.close()
    return data

def import_dict_to_db(data):
    """Imports dict representation into SQLite DB, avoiding duplicates."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for s in data.get("sessions", []):
        cursor.execute("SELECT id FROM sessions WHERE id = ?", (s["id"],))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)", 
                           (s["id"], s["title"], s["created_at"]))
            
    for m in data.get("messages", []):
        # We can't easily dedup messages by auto-id across different DBs if they clash, 
        # but since session_id is a UUID, we can just insert them if session exists.
        # Wait, if we're merging, let's just insert all messages and maybe duplicate them.
        # Better: check if message with exact content and timestamp exists for the session.
        cursor.execute("SELECT id FROM messages WHERE session_id = ? AND content = ? AND timestamp = ?", 
                       (m["session_id"], m["content"], m["timestamp"]))
        if cursor.fetchone() is None:
            cursor.execute('''
                INSERT INTO messages (session_id, role, content, source, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (m["session_id"], m["role"], m["content"], m["source"], m["timestamp"]))

    conn.commit()
    conn.close()

# Ensure DB is initialized when module loads
init_db()
