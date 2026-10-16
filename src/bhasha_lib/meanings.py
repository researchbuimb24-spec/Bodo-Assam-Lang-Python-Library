"""Lexical annotation and review workflow module for bhasha_lib."""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Any

from bhasha_lib.db import (
    DEFAULT_DB_PATH,
    get_connection,
    init_db,
    update_word_meaning,
)

VALID_ORIGINS: frozenset[str] = frozenset({"bodo", "loan", "unsure"})
VALID_STATUSES: frozenset[str] = frozenset({"unverified", "community", "expert"})

CSV_FIELDNAMES: list[str] = [
    "word",
    "roman",
    "meaning_hi",
    "meaning_en",
    "pos",
    "origin",
    "dialect",
    "verified_by",
    "notes",
]


def _resolve_paths(
    p1: str | Path,
    p2: str | Path,
) -> tuple[Path, Path]:
    """Helper to flexibly handle (db_path, csv_path) or (csv_path, db_path)."""
    s1, s2 = str(p1), str(p2)
    if (s1.endswith(".sqlite") or s1.endswith(".db")) or s2.endswith(".csv"):
        return Path(p1), Path(p2)
    if (s2.endswith(".sqlite") or s2.endswith(".db")) or s1.endswith(".csv"):
        return Path(p2), Path(p1)
    return Path(p1), Path(p2)


CONTEXT_1_COL: str = "context_1 (do not edit)"
CONTEXT_2_COL: str = "context_2 (do not edit)"


def export_for_review(
    db_path: str | Path = DEFAULT_DB_PATH,
    csv_path: str | Path = "data/review_batch_1.csv",
    limit: int = 500,
    only_empty: bool = True,
    seed: int = 1,
    source_id: int | None = None,
    with_context: bool = False,
    min_freq: int = 1,
    order: str = "random",
    exclude_hyphen: bool = False,
) -> int:
    """Export words needing review into a UTF-8 with BOM CSV template.

    Picks words where meaning_hi and meaning_en are both empty.
    Supports filtering by source, minimum frequency, excluding hyphenated words,
    sorting by frequency or repeatable random shuffle, and adding occurrence contexts.

    Args:
        db_path: Path to the SQLite database.
        csv_path: Destination CSV file path.
        limit: Maximum number of rows to export (default: 500).
        only_empty: Only include words with both meanings empty (default: True).
        seed: Random seed for deterministic reproducibility (default: 1).
        source_id: If given, only includes words having an occurrence from this source.
        with_context: If True, adds read-only context_1 and context_2 columns.
        min_freq: Minimum frequency threshold (default: 1).
        order: Ordering strategy: 'random' (default) or 'freq' (descending).
        exclude_hyphen: If True, skips words containing a hyphen.

    Returns:
        Number of word rows exported.
    """
    actual_db_path, actual_csv_path = _resolve_paths(db_path, csv_path)
    init_db(actual_db_path)

    actual_csv_path.parent.mkdir(parents=True, exist_ok=True)

    conditions: list[str] = []
    params: list[Any] = []

    if only_empty:
        conditions.append(
            "(words.meaning_hi IS NULL OR words.meaning_hi = '') AND "
            "(words.meaning_en IS NULL OR words.meaning_en = '')"
        )

    if min_freq > 1:
        conditions.append("words.freq >= ?")
        params.append(min_freq)

    if exclude_hyphen:
        conditions.append("words.word NOT LIKE '%-%'")

    if source_id is not None:
        conditions.append(
            "words.word IN (SELECT word FROM occurrences WHERE source_id = ?)"
        )
        params.append(source_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    if order.lower() == "freq":
        order_clause = "ORDER BY words.freq DESC, words.word ASC"
    else:
        order_clause = "ORDER BY words.word ASC"

    query = f"""
        SELECT words.word, words.roman, words.meaning_hi, words.meaning_en,
               words.pos, words.origin, words.dialect, words.verified_by, words.freq
        FROM words
        {where_clause}
        {order_clause}
    """

    with get_connection(actual_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        candidate_rows = [dict(r) for r in cursor.fetchall()]

    # If random ordering is requested, shuffle with reproducible seed
    if order.lower() != "freq":
        rng = random.Random(seed)
        rng.shuffle(candidate_rows)

    selected_rows = candidate_rows[:limit] if limit is not None else candidate_rows

    contexts_map: dict[str, list[str]] = {}
    if with_context and selected_rows:
        with get_connection(actual_db_path) as conn:
            cursor = conn.cursor()
            for r in selected_rows:
                w = r["word"]
                if source_id is not None:
                    cursor.execute(
                        """
                        SELECT context FROM occurrences
                        WHERE word = ?
                        ORDER BY (CASE WHEN source_id = ? THEN 0 ELSE 1 END), rowid ASC
                        LIMIT 2
                        """,
                        (w, source_id),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT context FROM occurrences
                        WHERE word = ?
                        ORDER BY rowid ASC
                        LIMIT 2
                        """,
                        (w,),
                    )
                snippets = [row[0] for row in cursor.fetchall() if row[0]]
                contexts_map[w] = snippets

    fieldnames = list(CSV_FIELDNAMES)
    if with_context:
        fieldnames.extend([CONTEXT_1_COL, CONTEXT_2_COL])

    with open(actual_csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in selected_rows:
            w = row.get("word") or ""
            row_dict: dict[str, Any] = {
                "word": w,
                "roman": row.get("roman") or "",
                "meaning_hi": row.get("meaning_hi") or "",
                "meaning_en": row.get("meaning_en") or "",
                "pos": row.get("pos") or "",
                "origin": row.get("origin") or "",
                "dialect": row.get("dialect") or "",
                "verified_by": row.get("verified_by") or "",
                "notes": "",
            }
            if with_context:
                snippets = contexts_map.get(w, [])
                row_dict[CONTEXT_1_COL] = snippets[0] if len(snippets) > 0 else ""
                row_dict[CONTEXT_2_COL] = snippets[1] if len(snippets) > 1 else ""

            writer.writerow(row_dict)

    return len(selected_rows)


# Alias for backwards compatibility
export_meanings_csv = export_for_review


def import_meanings(
    csv_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, int]:
    """Import reviewed meanings from CSV into database with validation.

    Rules:
    - Read the CSV as UTF-8 (accept BOM).
    - Skip a row if all of meaning_hi, meaning_en are empty.
    - REJECT a row (print line number) if verified_by is empty, or if origin is
      not one of bodo, loan, unsure (empty origin is allowed and stays unchanged).
    - Never overwrite an existing non-empty meaning. If a meaning already exists
      and differs, print a conflict line and skip it.
    - Never change the word text itself.
    - Set status to 'community' and store verified_by.
    - Print a summary: updated, skipped, rejected, conflicts.

    Returns:
        Summary dict:
        {'updated': int, 'skipped': int, 'rejected': int, 'conflicts': int}
    """
    actual_db_path, actual_csv_path = _resolve_paths(db_path, csv_path)
    if not actual_csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {actual_csv_path}")

    init_db(actual_db_path)
    updated = 0
    skipped = 0
    rejected = 0
    conflicts = 0

    with open(actual_csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):  # Header is line 1
            word = (row.get("word") or "").strip()
            if not word:
                continue

            meaning_hi = (row.get("meaning_hi") or "").strip() or None
            meaning_en = (row.get("meaning_en") or "").strip() or None
            origin_raw = (row.get("origin") or "").strip().lower()
            origin = origin_raw if origin_raw else None
            verified_by = (row.get("verified_by") or "").strip() or None
            pos = (row.get("pos") or "").strip() or None
            dialect = (row.get("dialect") or "").strip() or None

            # Skip row if both meanings are empty
            if not meaning_hi and not meaning_en:
                skipped += 1
                continue

            # Validation: verified_by is mandatory when meanings are supplied
            if not verified_by:
                print(
                    f"Line {line_no}: Rejected - 'verified_by' is empty "
                    f"for word '{word}'."
                )
                rejected += 1
                continue

            # Validation: origin must be bodo, loan, unsure, or empty
            if origin and origin not in VALID_ORIGINS:
                print(
                    f"Line {line_no}: Rejected - Invalid origin '{origin}' "
                    f"for word '{word}'. Must be one of: "
                    f"{sorted(VALID_ORIGINS)} or empty."
                )
                rejected += 1
                continue

            # Fetch existing word details
            with get_connection(actual_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT meaning_hi, meaning_en, origin FROM words WHERE word = ?",
                    (word,),
                )
                existing = cursor.fetchone()

            if existing is not None:
                exist_hi = existing["meaning_hi"] or None
                exist_en = existing["meaning_en"] or None
                exist_origin = existing["origin"] or None

                # Check for conflicts on non-empty existing meanings
                conflict_found = False
                if exist_hi and meaning_hi and exist_hi != meaning_hi:
                    print(
                        f"Line {line_no}: Conflict - Word '{word}' already has "
                        f"meaning_hi='{exist_hi}', incoming='{meaning_hi}'. Skipping."
                    )
                    conflict_found = True
                if exist_en and meaning_en and exist_en != meaning_en:
                    print(
                        f"Line {line_no}: Conflict - Word '{word}' already has "
                        f"meaning_en='{exist_en}', incoming='{meaning_en}'. Skipping."
                    )
                    conflict_found = True

                if conflict_found:
                    conflicts += 1
                    continue

                target_hi = exist_hi if exist_hi else meaning_hi
                target_en = exist_en if exist_en else meaning_en
                target_origin = origin if origin else exist_origin

                update_word_meaning(
                    word=word,
                    meaning_hi=target_hi,
                    meaning_en=target_en,
                    pos=pos,
                    origin=target_origin,
                    status="community",
                    verified_by=verified_by,
                    dialect=dialect,
                    db_path=actual_db_path,
                )
                updated += 1
            else:
                # Word does not exist in lexicon; skip to preserve lexicon integrity
                skipped += 1

    summary = {
        "updated": updated,
        "skipped": skipped,
        "rejected": rejected,
        "conflicts": conflicts,
    }
    print(
        f"Summary: {updated} updated, {skipped} skipped, "
        f"{rejected} rejected, {conflicts} conflicts."
    )
    return summary


# Alias for backwards compatibility
import_meanings_csv = import_meanings


def get_meanings_stats(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Return statistical summary of meanings, status, and origins."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Total words
        cursor.execute("SELECT count(1) FROM words")
        total_words = int(cursor.fetchone()[0])

        # Words with any meaning
        cursor.execute(
            """
            SELECT count(1) FROM words
            WHERE (meaning_hi IS NOT NULL AND meaning_hi != '')
               OR (meaning_en IS NOT NULL AND meaning_en != '')
            """
        )
        words_with_meaning = int(cursor.fetchone()[0])

        # Count by status
        cursor.execute(
            "SELECT COALESCE(status, 'unverified') as st, count(1) "
            "FROM words GROUP BY st"
        )
        status_counts = {row["st"]: row[1] for row in cursor.fetchall()}

        # Count by origin
        cursor.execute(
            "SELECT COALESCE(origin, 'unset') as orig, count(1) "
            "FROM words GROUP BY orig"
        )
        origin_counts = {row["orig"]: row[1] for row in cursor.fetchall()}

    return {
        "total_words": total_words,
        "words_with_meaning": words_with_meaning,
        "status_counts": status_counts,
        "origin_counts": origin_counts,
    }


def print_stats(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """Print meanings statistics to standard output."""
    stats = get_meanings_stats(db_path=db_path)
    print("Lexicon Meanings Statistics:")
    print(f"  Total words: {stats['total_words']}")
    print(f"  Words with any meaning: {stats['words_with_meaning']}")
    print("  Count by status:")
    for st, count in sorted(stats["status_counts"].items()):
        print(f"    - {st}: {count}")
    print("  Count by origin:")
    for orig, count in sorted(stats["origin_counts"].items()):
        print(f"    - {orig}: {count}")
    return stats


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for export, import, and stats."""
    parser = argparse.ArgumentParser(
        description="Manage lexical meanings review workflow."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # export
    p_export = subparsers.add_parser("export", help="Export words for community review")
    p_export.add_argument("out_csv", type=str, help="Destination CSV file path")
    p_export.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum words to export (default: 500)",
    )
    p_export.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    p_export.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Random seed for repeatable sampling (default: 1)",
    )
    p_export.add_argument(
        "--source-id",
        type=int,
        default=None,
        help="Only words that have an occurrence from this source ID",
    )
    p_export.add_argument(
        "--with-context",
        action="store_true",
        default=False,
        help="Add read-only context_1 and context_2 columns to the CSV",
    )
    p_export.add_argument(
        "--min-freq",
        type=int,
        default=1,
        help="Only words with freq >= N (default: 1)",
    )
    p_export.add_argument(
        "--order",
        type=str,
        choices=["random", "freq"],
        default="random",
        help="Ordering strategy: random (default) or freq (descending)",
    )
    p_export.add_argument(
        "--exclude-hyphen",
        action="store_true",
        default=False,
        help="Skip words that contain a hyphen",
    )

    # import
    p_import = subparsers.add_parser(
        "import", help="Import filled review CSV into database"
    )
    p_import.add_argument("in_csv", type=str, help="Reviewed input CSV path")
    p_import.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )

    # stats
    p_stats = subparsers.add_parser("stats", help="Display lexicon meanings statistics")
    p_stats.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )

    args = parser.parse_args(argv)

    if args.command == "export":
        exported = export_for_review(
            db_path=args.db,
            csv_path=args.out_csv,
            limit=args.limit,
            seed=args.seed,
            source_id=args.source_id,
            with_context=args.with_context,
            min_freq=args.min_freq,
            order=args.order,
            exclude_hyphen=args.exclude_hyphen,
        )
        print(f"Exported {exported} words for review to '{args.out_csv}'.")
        return 0

    if args.command == "import":
        import_meanings(csv_path=args.in_csv, db_path=args.db)
        return 0

    if args.command == "stats":
        print_stats(db_path=args.db)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
