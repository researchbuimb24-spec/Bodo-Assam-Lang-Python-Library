"""Culture metadata loading and semantic search module."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from bhasha_lib.db import (
    DEFAULT_DB_PATH,
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


class CultureLoadResult(list):
    """List of newly inserted item IDs with summary counts."""

    def __init__(
        self,
        inserted: list[int] | None = None,
        updated: list[int] | None = None,
        unchanged: list[int] | None = None,
    ):
        self.inserted: list[int] = inserted or []
        self.updated: list[int] = updated or []
        self.unchanged: list[int] = unchanged or []
        super().__init__(self.inserted)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "inserted": len(self.inserted),
            "updated": len(self.updated),
            "unchanged": len(self.unchanged),
        }


def reset_confidence(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Set confidence to 'needs_check' for all culture_items rows."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE culture_items SET confidence = 'needs_check'")
        count = cursor.rowcount
    print(f"Reset confidence to 'needs_check' for {count} culture item(s).")
    return count


def load_culture_dir(
    dir_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> CultureLoadResult:
    """Read every .md file in the directory and load culture records into DB.

    1. Parses YAML header and description body.
    2. Rejects files missing category, title, source, or description.
    3. Finds or creates a row in sources table.
    4. If row with same title and category exists, updates its fields.
    5. Inserts new culture items via add_culture_item().
    6. Prints summary of inserted, updated, and unchanged items.

    Returns:
        CultureLoadResult containing inserted, updated, and unchanged IDs.
    """
    directory = Path(dir_path)
    if not directory.is_dir():
        raise FileNotFoundError(f"Culture directory not found: {directory}")

    init_db(db_path)
    inserted_ids: list[int] = []
    updated_ids: list[int] = []
    unchanged_ids: list[int] = []

    md_files = sorted(directory.glob("*.md"))
    for file_path in md_files:
        text = file_path.read_text(encoding="utf-8")
        header, description = parse_culture_markdown(
            text, file_name=file_path.name
        )

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

        # Optional timeline and verification metadata
        year_start_raw = header.get("year_start")
        year_end_raw = header.get("year_end")
        confidence_raw = header.get("confidence")

        year_start = None
        if year_start_raw is not None:
            try:
                year_start = int(year_start_raw)
            except (ValueError, TypeError):
                year_start = None

        year_end = None
        if year_end_raw is not None:
            try:
                year_end = int(year_end_raw)
            except (ValueError, TypeError):
                year_end = None

        confidence = (
            str(confidence_raw).strip() if confidence_raw else "needs_check"
        )

        with get_connection(db_path) as conn:
            cursor = conn.cursor()

            # Find or create source row
            note_type = (
                f"{category}_note"
                if category in ("history", "culture")
                else "culture_note"
            )
            cursor.execute(
                "SELECT id FROM sources "
                "WHERE title = ? AND (type = ? OR type = 'culture_note')",
                (source, note_type),
            )
            source_row = cursor.fetchone()
            if source_row is not None:
                source_id = int(source_row[0])
            else:
                cursor.execute(
                    """
                    INSERT INTO sources (title, type, license, file_path)
                    VALUES (?, ?, 'own_words', ?)
                    """,
                    (source, note_type, str(file_path)),
                )
                source_id = int(cursor.lastrowid)

            # Format related words as comma-separated string
            if isinstance(related_words, list):
                related_words_str = ",".join(
                    str(w).strip() for w in related_words
                )
            else:
                related_words_str = str(related_words).strip()
            related_words_val = (
                related_words_str if related_words_str else None
            )
            region_val = region if region else None

            # Check for existing duplicate (same title and category)
            cursor.execute(
                """
                SELECT id, description, region, related_words,
                       year_start, year_end, confidence, source_id
                FROM culture_items
                WHERE title = ? AND category = ?
                """,
                (title, category),
            )
            existing = cursor.fetchone()

            if existing is not None:
                item_id = int(existing["id"])
                exist_desc = existing["description"] or ""
                exist_reg = existing["region"] or ""
                exist_rw = existing["related_words"] or ""
                exist_ys = existing["year_start"]
                exist_ye = existing["year_end"]
                exist_conf = existing["confidence"] or "needs_check"
                exist_src = existing["source_id"]

                cur_desc = description or ""
                cur_reg = region_val or ""
                cur_rw = related_words_val or ""
                cur_ys = year_start
                cur_ye = year_end
                cur_conf = confidence
                cur_src = source_id

                is_changed = (
                    exist_desc != cur_desc
                    or exist_reg != cur_reg
                    or exist_rw != cur_rw
                    or exist_ys != cur_ys
                    or exist_ye != cur_ye
                    or exist_conf != cur_conf
                    or exist_src != cur_src
                )

                if is_changed:
                    cursor.execute(
                        """
                        UPDATE culture_items SET
                            description = ?,
                            region = ?,
                            related_words = ?,
                            year_start = ?,
                            year_end = ?,
                            confidence = ?,
                            source_id = ?
                        WHERE id = ?
                        """,
                        (
                            description,
                            region_val,
                            related_words_val,
                            year_start,
                            year_end,
                            confidence,
                            source_id,
                            item_id,
                        ),
                    )
                    updated_ids.append(item_id)
                else:
                    unchanged_ids.append(item_id)
            else:
                cursor.execute(
                    """
                    INSERT INTO culture_items (
                        category,
                        title,
                        description,
                        region,
                        related_words,
                        source_id,
                        media_path,
                        year_start,
                        year_end,
                        confidence
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        category,
                        title,
                        description,
                        region_val,
                        related_words_val,
                        source_id,
                        None,
                        year_start,
                        year_end,
                        confidence,
                    ),
                )
                if cursor.lastrowid is None:
                    raise RuntimeError("Failed to insert culture item.")
                item_id = int(cursor.lastrowid)
                inserted_ids.append(item_id)

    print(
        f"Culture items: {len(inserted_ids)} inserted, "
        f"{len(updated_ids)} updated, {len(unchanged_ids)} unchanged."
    )
    return CultureLoadResult(
        inserted=inserted_ids,
        updated=updated_ids,
        unchanged=unchanged_ids,
    )


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
                related_words, source_id, media_path,
                year_start, year_end, confidence
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
        description="Load culture markdown files or reset confidence."
    )
    parser.add_argument(
        "target",
        type=str,
        help="Directory containing culture .md files OR 'reset-confidence'",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    args = parser.parse_args(argv)

    if args.target == "reset-confidence":
        reset_confidence(db_path=args.db)
        return 0

    load_culture_dir(args.target, db_path=args.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
