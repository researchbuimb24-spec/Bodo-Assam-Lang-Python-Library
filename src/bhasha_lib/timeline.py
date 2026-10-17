"""Chronological timeline module for historical and cultural milestones."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from bhasha_lib.db import DEFAULT_DB_PATH, get_connection, init_db


def get_timeline(
    db_path: str | Path = DEFAULT_DB_PATH,
    category: str | None = None,
    from_year: int | None = None,
    to_year: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve chronological timeline events from culture_items.

    Filters items where year_start is specified and orders by
    year_start ASC, year_end ASC, title ASC.
    """
    init_db(db_path)
    conditions: list[str] = ["year_start IS NOT NULL"]
    params: list[Any] = []

    if category:
        conditions.append("category = ?")
        params.append(category.strip())

    if from_year is not None:
        conditions.append("year_start >= ?")
        params.append(int(from_year))

    if to_year is not None:
        conditions.append("year_start <= ?")
        params.append(int(to_year))

    where_clause = f"WHERE {' AND '.join(conditions)}"
    query = f"""
        SELECT
            id, category, title, description, region, related_words,
            source_id, media_path, year_start, year_end, confidence
        FROM culture_items
        {where_clause}
        ORDER BY year_start ASC,
                 COALESCE(year_end, year_start) ASC,
                 title ASC
    """

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def format_year_range(year_start: int | None, year_end: int | None) -> str:
    """Format single year or year interval string."""
    if year_start is None:
        return "Unknown"
    if year_end is not None and year_end != year_start:
        return f"{year_start} - {year_end}"
    return str(year_start)


def print_timeline(events: list[dict[str, Any]]) -> None:
    """Display timeline items in human-readable chronological format."""
    if not events:
        print("No timeline events found.")
        return

    print(f"Bodo Language & Cultural Timeline ({len(events)} event(s)):\n")
    for idx, event in enumerate(events, start=1):
        year_str = format_year_range(
            event.get("year_start"), event.get("year_end")
        )
        title = event.get("title") or "Untitled"
        cat = event.get("category") or "general"
        region = event.get("region")
        region_str = f" ({region})" if region else ""
        confidence = event.get("confidence") or "verified"
        conf_marker = f" [{confidence}]" if confidence != "verified" else ""

        print(f"[{idx}] {year_str}: {title}{region_str} - {cat}{conf_marker}")
        desc = (event.get("description") or "").strip()
        if desc:
            first_para = desc.split("\n\n")[0].replace("\n", " ").strip()
            print(f"    {first_para}")
        print()


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for viewing the historical timeline."""
    parser = argparse.ArgumentParser(
        description="Display chronological timeline of language and cultural history."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter events by category (e.g. history, festival)",
    )
    parser.add_argument(
        "--from-year",
        type=int,
        default=None,
        help="Earliest year_start to include",
    )
    parser.add_argument(
        "--to-year",
        type=int,
        default=None,
        help="Latest year_start to include",
    )
    args = parser.parse_args(argv)

    events = get_timeline(
        db_path=args.db,
        category=args.category,
        from_year=args.from_year,
        to_year=args.to_year,
    )
    print_timeline(events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
