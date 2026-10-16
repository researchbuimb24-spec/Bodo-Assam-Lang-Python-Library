"""Culture metadata loading and semantic search module."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from bhasha_lib.db import (
    DEFAULT_DB_PATH,
    add_culture_item,
    get_connection,
    init_db,
    search_word,
)


def _escape_like(text: str, escape_char: str = "\\") -> str:
    """Escape special pattern characters (%, _, and escape_char) for SQLite LIKE."""
    escaped = text.replace(escape_char, escape_char + escape_char)
    escaped = escaped.replace("%", escape_char + "%")
    return escaped.replace("_", escape_char + "_")


def parse_culture_markdown(
    content: str, file_name: str = "document"
) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter header and markdown description body.

    Raises:
        ValueError: If header delimiters are missing or invalid YAML.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(
            f"Invalid culture file format in '{file_name}': "
            "Missing starting '---' YAML header."
        )

    closing_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing_idx = i
            break

    if closing_idx == -1:
        raise ValueError(
            f"Invalid culture file format in '{file_name}': "
            "Missing closing '---' YAML header."
        )

    header_yaml = "\n".join(lines[1:closing_idx])
    body = "\n".join(lines[closing_idx + 1 :]).strip()

    header_data = yaml.safe_load(header_yaml) or {}
    if not isinstance(header_data, dict):
        raise ValueError(
            f"Invalid YAML frontmatter in '{file_name}': Expected key-value dictionary."
        )

    return header_data, body


def load_culture_dir(
    dir_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[int]:
    """Read every .md file in the directory and load culture records into DB.

    1. Parses YAML header and description body.
    2. Rejects files missing category, title, source, or description.
    3. Finds or creates a row in sources table
       (type='culture_note', license='own_words').
    4. Skips duplicate entries (same title and category).
    5. Inserts new culture items via add_culture_item().

    Returns:
        List of inserted culture item IDs.
    """
    directory = Path(dir_path)
    if not directory.is_dir():
        raise FileNotFoundError(f"Culture directory not found: {directory}")

    init_db(db_path)
    inserted_ids: list[int] = []

    md_files = sorted(directory.glob("*.md"))
    for file_path in md_files:
        text = file_path.read_text(encoding="utf-8")
        header, description = parse_culture_markdown(text, file_name=file_path.name)

        category = str(header.get("category") or "").strip()
        title = str(header.get("title") or "").strip()
        source = str(header.get("source") or "").strip()
        region = str(header.get("region") or "").strip()
        related_words = header.get("related_words") or []

        # Validate mandatory fields
        if not category:
            raise ValueError(
                f"File '{file_path.name}' is rejected: Missing required 'category'."
            )
        if not title:
            raise ValueError(
                f"File '{file_path.name}' is rejected: Missing required 'title'."
            )
        if not source:
            raise ValueError(
                f"File '{file_path.name}' is rejected: Missing required 'source'."
            )
        if not description:
            raise ValueError(
                f"File '{file_path.name}' is rejected: Missing description text."
            )

        # Check for existing duplicate (same title and category)
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM culture_items WHERE title = ? AND category = ?",
                (title, category),
            )
            if cursor.fetchone() is not None:
                # Skip duplicate
                continue

            # Find or create source row
            cursor.execute(
                "SELECT id FROM sources WHERE title = ? AND type = 'culture_note'",
                (source,),
            )
            source_row = cursor.fetchone()
            if source_row is not None:
                source_id = int(source_row[0])
            else:
                cursor.execute(
                    """
                    INSERT INTO sources (title, type, license, file_path)
                    VALUES (?, 'culture_note', 'own_words', ?)
                    """,
                    (source, str(file_path)),
                )
                source_id = int(cursor.lastrowid)

        # Format related words as comma-separated string
        if isinstance(related_words, list):
            related_words_str = ",".join(str(w).strip() for w in related_words)
        else:
            related_words_str = str(related_words).strip()

        item_id = add_culture_item(
            category=category,
            title=title,
            description=description,
            region=region if region else None,
            related_words=related_words_str,
            source_id=source_id,
            db_path=db_path,
        )
        inserted_ids.append(item_id)

    return inserted_ids


def related(
    term: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Search for culture items and vocabulary related to the given term.

    Returns a dict with:
    - 'culture_items': items whose title, description or related_words contain term
    - 'word': the result of search_word(term) if it exists
    """
    init_db(db_path)
    clean_term = term.strip()
    if not clean_term:
        return {"culture_items": [], "word": None}

    escaped = _escape_like(clean_term)
    pattern = f"%{escaped}%"

    culture_items: list[dict[str, Any]] = []
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id, category, title, description, region,
                related_words, source_id, media_path
            FROM culture_items
            WHERE title LIKE ? ESCAPE '\\'
               OR description LIKE ? ESCAPE '\\'
               OR related_words LIKE ? ESCAPE '\\'
            ORDER BY id ASC
            """,
            (pattern, pattern, pattern),
        )
        for row in cursor.fetchall():
            culture_items.append(dict(row))

    word_info = search_word(clean_term, db_path=db_path)

    return {
        "culture_items": culture_items,
        "word": word_info,
    }


def main(argv: list[str] | None = None) -> int:
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description="Load culture markdown files into SQLite database."
    )
    parser.add_argument("dir", type=str, help="Directory containing culture .md files")
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    args = parser.parse_args(argv)

    loaded = load_culture_dir(args.dir, db_path=args.db)
    print(f"Loaded {len(loaded)} culture item(s) from {args.dir}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
