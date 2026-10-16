"""SQLite database layer for bhasha_lib."""

from __future__ import annotations

import sqlite3
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH: str = "data/lexicon.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    type TEXT,
    author TEXT,
    year INTEGER,
    license TEXT NOT NULL,
    contributor TEXT,
    url TEXT,
    file_path TEXT
);

CREATE TABLE IF NOT EXISTS words (
    word TEXT PRIMARY KEY,
    roman TEXT,
    meaning_hi TEXT,
    meaning_en TEXT,
    pos TEXT,
    tone TEXT,
    dialect TEXT,
    freq INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS occurrences (
    word TEXT,
    source_id INTEGER,
    line_no INTEGER,
    context TEXT,
    FOREIGN KEY (word) REFERENCES words(word),
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS culture_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    title TEXT,
    description TEXT,
    region TEXT,
    related_words TEXT,
    source_id INTEGER,
    media_path TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);
"""


@contextmanager
def get_connection(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> Iterator[sqlite3.Connection]:
    """Provide a transactional database connection that closes automatically.

    Ensures parent directories exist when a file path is provided.
    """
    if str(db_path) != ":memory:":
        path_obj = Path(db_path)
        if path_obj.parent and not path_obj.parent.exists():
            path_obj.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: str | Path = DEFAULT_DB_PATH) -> Path:
    """Initialize database tables if they do not exist."""
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.executescript(SCHEMA)
    return Path(path)


def add_source(
    title: str | None = None,
    type: str | None = None,
    author: str | None = None,
    year: int | None = None,
    license: str | None = None,
    contributor: str | None = None,
    url: str | None = None,
    file_path: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Insert a source record.

    Raises:
        ValueError: If license is None or an empty string.
    """
    if license is None or not str(license).strip():
        raise ValueError("The 'license' field is required and cannot be empty.")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sources (
                title, type, author, year, license, contributor, url, file_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                type,
                author,
                year,
                str(license).strip(),
                contributor,
                url,
                file_path,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to insert source record.")
        return int(cursor.lastrowid)


def add_word(
    word: str,
    roman: str | None = None,
    meaning_hi: str | None = None,
    meaning_en: str | None = None,
    pos: str | None = None,
    tone: str | None = None,
    dialect: str | None = None,
    freq: int = 1,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    """Insert or update a word record.

    Normalizes the word to Unicode NFC format.
    If the word already exists, increments its freq count.
    """
    if not word or not str(word).strip():
        raise ValueError("Word cannot be empty.")

    normalized_word = unicodedata.normalize("NFC", str(word).strip())
    freq_increment = freq if freq > 0 else 1

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO words (
                word, roman, meaning_hi, meaning_en, pos, tone, dialect, freq
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(word) DO UPDATE SET
                freq = words.freq + excluded.freq,
                roman = COALESCE(excluded.roman, words.roman),
                meaning_hi = COALESCE(excluded.meaning_hi, words.meaning_hi),
                meaning_en = COALESCE(excluded.meaning_en, words.meaning_en),
                pos = COALESCE(excluded.pos, words.pos),
                tone = COALESCE(excluded.tone, words.tone),
                dialect = COALESCE(excluded.dialect, words.dialect)
            """,
            (
                normalized_word,
                roman,
                meaning_hi,
                meaning_en,
                pos,
                tone,
                dialect,
                freq_increment,
            ),
        )


def add_occurrence(
    word: str,
    source_id: int | None = None,
    line_no: int | None = None,
    context: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    """Insert a word occurrence record.

    Normalizes the word to Unicode NFC format.
    """
    if not word or not str(word).strip():
        raise ValueError("Word cannot be empty.")

    normalized_word = unicodedata.normalize("NFC", str(word).strip())

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO occurrences (word, source_id, line_no, context)
            VALUES (?, ?, ?, ?)
            """,
            (normalized_word, source_id, line_no, context),
        )


def add_culture_item(
    category: str | None = None,
    title: str | None = None,
    description: str | None = None,
    region: str | None = None,
    related_words: str | None = None,
    source_id: int | None = None,
    media_path: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Insert a cultural metadata item record."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO culture_items (
                category,
                title,
                description,
                region,
                related_words,
                source_id,
                media_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                category,
                title,
                description,
                region,
                related_words,
                source_id,
                media_path,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to insert culture item.")
        return int(cursor.lastrowid)


def search_word(
    word: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    """Search for a word by its NFC-normalized string.

    Returns:
        A dictionary representation of the word row, or None if not found.
    """
    if not word or not str(word).strip():
        return None

    normalized_word = unicodedata.normalize("NFC", str(word).strip())

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT word, roman, meaning_hi, meaning_en, pos, tone, dialect, freq
            FROM words
            WHERE word = ?
            """,
            (normalized_word,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)
