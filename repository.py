import sqlite3
from datetime import datetime, timedelta

def init_tables(conn, cursor):
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT,
        username TEXT,
        telegram_profile TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER NOT NULL,
        participant_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        event_datetime TEXT NOT NULL,
        FOREIGN KEY (creator_id) REFERENCES users(user_id),
        FOREIGN KEY (participant_id) REFERENCES users(user_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reminders (
        reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        reminder_time TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(event_id)
    )
    ''')
    conn.commit()

def select_event_data(cursor, event_id):
    cursor.execute("SELECT creator_id, participant_id, description, event_datetime FROM events WHERE event_id=?", (event_id,))

def select_reminder_time(cursor, event_id):
    cursor.execute("SELECT reminder_time FROM reminders WHERE event_id=?", (event_id,))

def select_user_name(cursor, creator_id):
    cursor.execute("SELECT username FROM users WHERE user_id=?", (creator_id,))

def select_user_data(cursor, user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))

def add_user(conn, cursor, user_id, first_name, last_name, username, telegram_profile):
    cursor.execute(
            "INSERT INTO users (user_id, first_name, last_name, username, telegram_profile) VALUES (?, ?, ?, ?, ?)",
            (user_id, first_name, last_name, username, telegram_profile)
        )
    conn.commit()

def select_user_by_id(cursor, user_id):
    cursor.execute("SELECT user_id, first_name, last_name, username FROM users WHERE user_id != ?", (user_id,))

def select_users(cursor):
    cursor.execute("SELECT user_id, first_name, last_name, username FROM users")

def select_event_by_user(cursor, user_id):
    cursor.execute("""
            SELECT event_id, description, event_datetime, participant_id, creator_id
            FROM events
            WHERE creator_id=? OR participant_id=?
            ORDER BY event_datetime
        """, (user_id, user_id))

def select_fnu(cursor, _id):
    cursor.execute("SELECT first_name, last_name, username FROM users WHERE user_id=?", (_id,))

def get_creator_from_event(cursor, event_id):
     cursor.execute("SELECT creator_id FROM events WHERE event_id=?", (event_id,))

def select_creator_participant(cursor, event_id):
    cursor.execute("SELECT creator_id, participant_id FROM events WHERE event_id=?", (event_id,))

def delete_reminders(conn, cursor, event_id):
    cursor.execute("DELETE FROM reminders WHERE event_id=?", (event_id,))
    conn.commit()

def delete_event(conn, cursor, event_id):
    cursor.execute("DELETE FROM events WHERE event_id=?", (event_id,))
    conn.commit()

def select_event_by_participant_date(cursor, participant_id, event_datetime):
    cursor.execute("""
            SELECT * FROM events
            WHERE participant_id=? AND event_datetime=?
        """, (participant_id, event_datetime.isoformat()))

def create_event(conn, cursor, user_id, participant_id, description, event_datetime):
    cursor.execute("""
            INSERT INTO events (creator_id, participant_id, description, event_datetime)
            VALUES (?, ?, ?, ?)
        """, (user_id, participant_id, description, event_datetime.isoformat()))
    conn.commit()

def create_reminders(conn, cursor, event_id, reminder_time):
    cursor.execute("""
                    INSERT INTO reminders (event_id, reminder_time)
                    VALUES (?, ?)
                """, (event_id, reminder_time.isoformat()))
    conn.commit()

def get_event_data(cursor, event_id):
    cursor.execute("""
            SELECT event_id, participant_id, description, event_datetime FROM events
            WHERE event_id=?
        """, (event_id,))

def select_for_check_intersection(cursor, event_id, new_event_datetime):
    cursor.execute("""
            SELECT * FROM events
            WHERE participant_id=(SELECT participant_id FROM events WHERE event_id=?)
            AND event_datetime=?
            AND event_id != ?
    """, (event_id, new_event_datetime.isoformat(), event_id))

def update_event(conn, cursor, new_description, new_event_datetime, event_id):
    cursor.execute("""
            UPDATE events
            SET description=?, event_datetime=?
            WHERE event_id=?
        """, (new_description, new_event_datetime.isoformat(), event_id))
    conn.commit()

def select_last_event(cursor, user_id):
    cursor.execute("SELECT event_id, event_datetime FROM events WHERE creator_id=? ORDER BY event_id DESC LIMIT 1",
                       (user_id,))
