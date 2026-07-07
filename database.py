"""
database.py
Central SQLite database helper for Discord Bot Hub 2.
Uses a single SQLite file (bot.db) with guild_id columns so the bot
works correctly across multiple servers.
"""

import sqlite3
import os
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")

_lock = threading.Lock()


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Create all tables if they don't already exist."""
    with _lock:
        conn = get_connection()
        cur = conn.cursor()

        # Per-guild configuration (channel ids for various features)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            confessions_channel_id INTEGER,
            suggestions_channel_id INTEGER,
            birthday_channel_id INTEGER,
            giveaway_channel_id INTEGER,
            level_up_channel_id INTEGER,
            jail_role_id INTEGER,
            jail_channel_id INTEGER,
            mod_role_id INTEGER,
            admin_role_id INTEGER
        )
        """)

        # Leveling / XP
        cur.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            guild_id INTEGER,
            user_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            last_message_ts REAL DEFAULT 0,
            voice_seconds INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

        # Economy
        cur.execute("""
        CREATE TABLE IF NOT EXISTS economy (
            guild_id INTEGER,
            user_id INTEGER,
            balance INTEGER DEFAULT 100,
            bank INTEGER DEFAULT 0,
            last_daily REAL DEFAULT 0,
            last_weekly REAL DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

        # Tickets
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            channel_id INTEGER,
            status TEXT DEFAULT 'open',
            created_at REAL,
            closed_at REAL
        )
        """)

        # Birthdays
        cur.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            guild_id INTEGER,
            user_id INTEGER,
            month INTEGER,
            day INTEGER,
            year INTEGER,
            last_announced_year INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

        # Marriages
        cur.execute("""
        CREATE TABLE IF NOT EXISTS marriages (
            guild_id INTEGER,
            user_id INTEGER,
            partner_id INTEGER,
            married_at REAL,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

        # Suggestions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            message_id INTEGER,
            content TEXT,
            status TEXT DEFAULT 'pending',
            created_at REAL
        )
        """)

        # Giveaways
        cur.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            giveaway_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            channel_id INTEGER,
            message_id INTEGER,
            prize TEXT,
            winners_count INTEGER,
            end_time REAL,
            host_id INTEGER,
            ended INTEGER DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS giveaway_entries (
            giveaway_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (giveaway_id, user_id)
        )
        """)

        # Warnings (moderation)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            moderator_id INTEGER,
            reason TEXT,
            created_at REAL
        )
        """)

        # Jail / arrest system (basic groundwork; panel to be refined later)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS jail (
            guild_id INTEGER,
            user_id INTEGER,
            jailed_by INTEGER,
            reason TEXT,
            jailed_at REAL,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

        conn.commit()
        conn.close()


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def execute(query, params=(), fetch=None):
    """
    Run a query with a fresh connection.
    fetch: None -> just commit, "one" -> fetchone, "all" -> fetchall
    """
    with _lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        result = None
        if fetch == "one":
            result = cur.fetchone()
        elif fetch == "all":
            result = cur.fetchall()
        conn.commit()
        conn.close()
        return result


def get_guild_config(guild_id):
    row = execute(
        "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,), fetch="one"
    )
    if row is None:
        execute(
            "INSERT INTO guild_config (guild_id) VALUES (?)", (guild_id,)
        )
        row = execute(
            "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,), fetch="one"
        )
    return row


def set_guild_config_field(guild_id, field, value):
    get_guild_config(guild_id)  # ensure row exists
    execute(
        f"UPDATE guild_config SET {field} = ? WHERE guild_id = ?",
        (value, guild_id),
    )


def ensure_economy_row(guild_id, user_id):
    row = execute(
        "SELECT * FROM economy WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
        fetch="one",
    )
    if row is None:
        execute(
            "INSERT INTO economy (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        row = execute(
            "SELECT * FROM economy WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
            fetch="one",
        )
    return row


def ensure_level_row(guild_id, user_id):
    row = execute(
        "SELECT * FROM levels WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
        fetch="one",
    )
    if row is None:
        execute(
            "INSERT INTO levels (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        row = execute(
            "SELECT * FROM levels WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
            fetch="one",
        )
    return row
