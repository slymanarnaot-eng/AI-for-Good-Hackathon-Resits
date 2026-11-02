import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path


# Use a separate database for the cleaned dataset.
# Your existing rail_pulse.db and backups remain untouched.
DB_PATH = Path(__file__).with_name("rail_pulse_clean.db")


# --------------------------------------------------
# 1. DATABASE CONNECTION
# --------------------------------------------------

@contextmanager
def connect_db():
    """Open a database connection and always close it."""

    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    try:
        connection.execute("PRAGMA busy_timeout = 30000")
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# --------------------------------------------------
# 2. INITIALIZE AND MIGRATE DATABASE
# --------------------------------------------------

def init_db():
    """
    Create the required tables and migrate an older
    database without deleting existing post records.
    """

    with connect_db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_text TEXT NOT NULL,
                post_time TEXT NOT NULL,
                collected_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                sentiment TEXT,
                topic TEXT,
                post_hash TEXT,
                UNIQUE(post_text, post_time)
            )
        """)

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(posts)"
            ).fetchall()
        }

        if "post_hash" not in columns:
            connection.execute(
                "ALTER TABLE posts ADD COLUMN post_hash TEXT"
            )

        # If an older database contains duplicate hashes,
        # preserve the first record and clear later hashes.
        connection.execute("""
            UPDATE posts
            SET post_hash = NULL
            WHERE post_hash IS NOT NULL
              AND id NOT IN (
                  SELECT MIN(id)
                  FROM posts
                  WHERE post_hash IS NOT NULL
                  GROUP BY post_hash
              )
        """)

        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_posts_hash
            ON posts(post_hash)
            WHERE post_hash IS NOT NULL
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_posts_time
            ON posts(post_time)
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)


# --------------------------------------------------
# 3. POST HASHING
# --------------------------------------------------

def hash_post_uri(post_uri):
    """
    Hash a post URI for duplicate detection.
    The raw URI is not stored in the database.
    """

    if not isinstance(post_uri, str) or not post_uri.strip():
        return None

    return hashlib.sha256(
        post_uri.strip().encode("utf-8")
    ).hexdigest()


# --------------------------------------------------
# 4. CHECK FOR DUPLICATES
# --------------------------------------------------

def has_post(post_text, post_time, post_uri=None):
    """Return True if the post already exists in the database."""

    if not isinstance(post_text, str):
        return False

    if not isinstance(post_time, str):
        return False

    post_text = post_text.strip()
    post_time = post_time.strip()

    if not post_text or not post_time:
        return False

    post_hash = hash_post_uri(post_uri)

    with connect_db() as connection:
        if post_hash:
            existing = connection.execute("""
                SELECT 1
                FROM posts
                WHERE post_hash = ?
                   OR (post_text = ? AND post_time = ?)
                LIMIT 1
            """, (
                post_hash,
                post_text,
                post_time,
            )).fetchone()

        else:
            existing = connection.execute("""
                SELECT 1
                FROM posts
                WHERE post_text = ?
                  AND post_time = ?
                LIMIT 1
            """, (
                post_text,
                post_time,
            )).fetchone()

    return existing is not None


# --------------------------------------------------
# 5. SAVE POSTS
# --------------------------------------------------

def save_post(
    post_text,
    post_time,
    sentiment=None,
    topic=None,
    post_uri=None,
):
    """
    Save a post and its sentiment analysis.

    Return True if saved.
    Return False if invalid or already present.
    """

    if not isinstance(post_text, str):
        return False

    if not isinstance(post_time, str):
        return False

    post_text = post_text.strip()
    post_time = post_time.strip()

    if not post_text or not post_time:
        return False

    post_hash = hash_post_uri(post_uri)

    try:
        with connect_db() as connection:
            connection.execute("""
                INSERT INTO posts (
                    post_text,
                    post_time,
                    sentiment,
                    topic,
                    post_hash
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                post_text,
                post_time,
                sentiment,
                topic,
                post_hash,
            ))

        return True

    except sqlite3.IntegrityError:
        # The URI hash or post text/time combination already exists.
        return False


# --------------------------------------------------
# 6. DATABASE STATISTICS
# --------------------------------------------------

def get_post_count():
    """Return the total number of saved posts."""

    with connect_db() as connection:
        result = connection.execute(
            "SELECT COUNT(*) FROM posts"
        ).fetchone()

    return result[0]


# --------------------------------------------------
# 7. COLLECTION METADATA
# --------------------------------------------------

def set_metadata(key, value):
    """Save collection information such as its start time."""

    if not isinstance(key, str) or not key:
        raise ValueError(
            "Metadata key must be a non-empty string."
        )

    if not isinstance(value, str):
        raise ValueError(
            "Metadata value must be a string."
        )

    with connect_db() as connection:
        connection.execute("""
            INSERT INTO metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
        """, (
            key,
            value,
        ))


def get_metadata(key):
    """Retrieve stored collection information."""

    with connect_db() as connection:
        result = connection.execute(
            "SELECT value FROM metadata WHERE key = ?",
            (key,),
        ).fetchone()

    return result[0] if result else None


# --------------------------------------------------
# 8. TEST THE DATABASE
# --------------------------------------------------

if __name__ == "__main__":
    init_db()

    print("Database initialized successfully!")
    print("Database location:", DB_PATH)
    print("Stored posts:", get_post_count())

    collection_started_at = get_metadata(
        "collection_started_at"
    )

    print(
        "Collection started at:",
        collection_started_at or "Not started",
    )