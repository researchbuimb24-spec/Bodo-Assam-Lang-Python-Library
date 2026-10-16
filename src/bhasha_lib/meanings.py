"""Lexical annotation and meanings workflow module for bhasha_lib."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from bhasha_lib.db import (
    DEFAULT_DB_PATH,
    add_word,
    get_connection,
    init_db,
    update_word_meaning,
)

# Foundational vocabulary with verified Hindi and English meanings
FOUNDATIONAL_SEED_MEANINGS: list[dict[str, Any]] = [
    {
        "word": "बड़ो",
        "roman": "bodo",
        "meaning_hi": "बोडो (असम की मूल जनजाति व भाषा)",
        "meaning_en": "Bodo (indigenous community and language of Assam)",
        "pos": "noun",
    },
    {
        "word": "राव",
        "roman": "rao",
        "meaning_hi": "भाषा, बोली",
        "meaning_en": "language, speech",
        "pos": "noun",
    },
    {
        "word": "आफा",
        "roman": "afa",
        "meaning_hi": "पिता; संघ, सभा",
        "meaning_en": "father; association, council",
        "pos": "noun",
    },
    {
        "word": "गाहाम",
        "roman": "gaham",
        "meaning_hi": "अच्छा, शुभ",
        "meaning_en": "good, well, auspicious",
        "pos": "adjective",
    },
    {
        "word": "खाम",
        "roman": "kham",
        "meaning_hi": "पारंपरिक ढोल / मृदंग",
        "meaning_en": "traditional Bodo drum",
        "pos": "noun",
    },
    {
        "word": "सिफुं",
        "roman": "siphung",
        "meaning_hi": "५ छेदों वाली पारंपरिक बांसुरी",
        "meaning_en": "traditional 5-hole bamboo flute",
        "pos": "noun",
    },
    {
        "word": "सेरजा",
        "roman": "serja",
        "meaning_hi": "सारंगी जैसा पारंपरिक तार-वाद्य",
        "meaning_en": "traditional stringed instrument / violin",
        "pos": "noun",
    },
    {
        "word": "दखना",
        "roman": "dokhona",
        "meaning_hi": "बोडो महिलाओं की पारंपरिक पोशाक",
        "meaning_en": "traditional attire of Bodo women",
        "pos": "noun",
    },
    {
        "word": "आरनाय",
        "roman": "aronai",
        "meaning_hi": "सम्मान का प्रतीक पारंपरिक स्कार्फ",
        "meaning_en": "traditional decorative scarf of honour",
        "pos": "noun",
    },
    {
        "word": "नाफाम",
        "roman": "napham",
        "meaning_hi": "पारंपरिक किण्वित (fermented) मछली",
        "meaning_en": "traditional fermented fish delicacy",
        "pos": "noun",
    },
    {
        "word": "अं",
        "roman": "ang",
        "meaning_hi": "मैं, मुझे",
        "meaning_en": "I, me",
        "pos": "pronoun",
    },
    {
        "word": "नों",
        "roman": "nwng",
        "meaning_hi": "तुम, आप",
        "meaning_en": "you",
        "pos": "pronoun",
    },
    {
        "word": "बि",
        "roman": "bi",
        "meaning_hi": "वह, यह",
        "meaning_en": "he, she, that",
        "pos": "pronoun",
    },
    {
        "word": "जों",
        "roman": "zong",
        "meaning_hi": "हम, हमें",
        "meaning_en": "we, us",
        "pos": "pronoun",
    },
    {
        "word": "मा",
        "roman": "ma",
        "meaning_hi": "क्या",
        "meaning_en": "what",
        "pos": "pronoun",
    },
    {
        "word": "दा",
        "roman": "da",
        "meaning_hi": "मत, नहीं (निषेधार्थक)",
        "meaning_en": "do not (prohibitive particle)",
        "pos": "particle",
    },
    {
        "word": "हा",
        "roman": "ha",
        "meaning_hi": "भूमि, जमीन, धरती",
        "meaning_en": "land, soil, earth",
        "pos": "noun",
    },
    {
        "word": "नो",
        "roman": "no",
        "meaning_hi": "घर, मकान",
        "meaning_en": "house, home",
        "pos": "noun",
    },
    {
        "word": "फै",
        "roman": "fai",
        "meaning_hi": "आना",
        "meaning_en": "to come",
        "pos": "verb",
    },
    {
        "word": "थां",
        "roman": "thang",
        "meaning_hi": "जाना",
        "meaning_en": "to go",
        "pos": "verb",
    },
    {
        "word": "जा",
        "roman": "za",
        "meaning_hi": "खाना; होना, बनना",
        "meaning_en": "to eat; to become, to happen",
        "pos": "verb",
    },
    {
        "word": "से",
        "roman": "se",
        "meaning_hi": "एक (१)",
        "meaning_en": "one (1)",
        "pos": "numeral",
    },
    {
        "word": "नै",
        "roman": "nwi",
        "meaning_hi": "दो (२)",
        "meaning_en": "two (2)",
        "pos": "numeral",
    },
    {
        "word": "थाम",
        "roman": "tham",
        "meaning_hi": "तीन (३)",
        "meaning_en": "three (3)",
        "pos": "numeral",
    },
    {
        "word": "ब्रै",
        "roman": "brui",
        "meaning_hi": "चार (४)",
        "meaning_en": "four (4)",
        "pos": "numeral",
    },
    {
        "word": "बा",
        "roman": "ba",
        "meaning_hi": "पांच (५)",
        "meaning_en": "five (5)",
        "pos": "numeral",
    },
    {
        "word": "द'",
        "roman": "do",
        "meaning_hi": "छह (६)",
        "meaning_en": "six (6)",
        "pos": "numeral",
    },
    {
        "word": "स्नि",
        "roman": "sni",
        "meaning_hi": "सात (७)",
        "meaning_en": "seven (7)",
        "pos": "numeral",
    },
    {
        "word": "दाय",
        "roman": "dath",
        "meaning_hi": "आठ (८)",
        "meaning_en": "eight (8)",
        "pos": "numeral",
    },
    {
        "word": "गु",
        "roman": "gu",
        "meaning_hi": "नौ (९)",
        "meaning_en": "nine (9)",
        "pos": "numeral",
    },
    {
        "word": "जि",
        "roman": "zi",
        "meaning_hi": "दस (१०)",
        "meaning_en": "ten (10)",
        "pos": "numeral",
    },
]


def export_meanings_csv(
    out_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
    min_freq: int = 1,
    limit: int | None = None,
    script: str = "all",
    only_empty: bool = True,
) -> int:
    """Export words needing annotation into a CSV template.

    Writes CSV using UTF-8-SIG encoding so spreadsheet tools (Excel,
    LibreOffice, Google Sheets) properly display Indic/Devanagari scripts.

    Args:
        out_path: File path to save the exported CSV.
        db_path: Path to the SQLite database.
        min_freq: Minimum frequency threshold to export.
        limit: Maximum number of rows to export (None for all).
        script: Filter script: 'devanagari', 'latin', or 'all'.
        only_empty: If True, only exports words lacking Hindi or English meanings.

    Returns:
        Number of exported word rows.
    """
    init_db(db_path)
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    conditions = ["(dialect IS NULL OR dialect != 'english')"]
    params: list[Any] = []

    if only_empty:
        conditions.append(
            "((meaning_hi IS NULL OR meaning_hi = '') AND "
            "(meaning_en IS NULL OR meaning_en = ''))"
        )

    if min_freq > 1:
        conditions.append("freq >= ?")
        params.append(min_freq)

    query = f"""
        SELECT word, roman, meaning_hi, meaning_en, pos, tone, dialect, freq
        FROM words
        WHERE {" AND ".join(conditions)}
        ORDER BY freq DESC, word ASC
    """
    if limit is not None:
        query += f" LIMIT {int(limit)}"

    rows: list[dict[str, Any]] = []
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        all_words = [dict(r) for r in cursor.fetchall()]

        # Filter by script if requested
        for r in all_words:
            w = r["word"]
            has_devanagari = any("\u0900" <= c <= "\u097f" for c in w)
            if script.lower() == "devanagari" and not has_devanagari:
                continue
            if script.lower() == "latin" and has_devanagari:
                continue

            # Fetch up to 1 example context occurrence to aid annotators
            cursor.execute(
                "SELECT context FROM occurrences WHERE word = ? LIMIT 1",
                (w,),
            )
            occ = cursor.fetchone()
            r["example_context"] = occ[0] if occ else ""
            rows.append(r)

    fieldnames = [
        "word",
        "roman",
        "meaning_hi",
        "meaning_en",
        "pos",
        "tone",
        "dialect",
        "freq",
        "example_context",
    ]

    with open(out_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return len(rows)


def import_meanings_csv(
    csv_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, int]:
    """Import filled meanings from a CSV file into the database.

    Updates meaning_hi, meaning_en, pos, tone, and dialect. Does not
    modify existing frequencies.

    Returns:
        Summary dict: {'updated': int, 'inserted': int, 'total': int}
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    init_db(db_path)
    updated = 0
    inserted = 0
    total = 0

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            word = (row.get("word") or "").strip()
            if not word:
                continue

            meaning_hi = (row.get("meaning_hi") or "").strip() or None
            meaning_en = (row.get("meaning_en") or "").strip() or None
            roman = (row.get("roman") or "").strip() or None
            pos = (row.get("pos") or "").strip() or None
            tone = (row.get("tone") or "").strip() or None
            dialect = (row.get("dialect") or "").strip() or None

            # Skip rows where no semantic fields are filled
            if not any([meaning_hi, meaning_en, pos, tone, dialect]):
                continue

            did_update = update_word_meaning(
                word=word,
                meaning_hi=meaning_hi,
                meaning_en=meaning_en,
                roman=roman,
                pos=pos,
                tone=tone,
                dialect=dialect,
                db_path=db_path,
            )
            if did_update:
                updated += 1
            else:
                # If word does not exist, insert it
                add_word(
                    word=word,
                    roman=roman,
                    meaning_hi=meaning_hi,
                    meaning_en=meaning_en,
                    pos=pos,
                    tone=tone,
                    dialect=dialect,
                    freq=1,
                    db_path=db_path,
                )
                inserted += 1

    return {"updated": updated, "inserted": inserted, "total": total}


def bootstrap_seed_meanings(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, int]:
    """Bootstrap foundational Bodo vocabulary with verified meanings."""
    init_db(db_path)
    applied = 0
    for item in FOUNDATIONAL_SEED_MEANINGS:
        did_update = update_word_meaning(
            word=item["word"],
            meaning_hi=item.get("meaning_hi"),
            meaning_en=item.get("meaning_en"),
            roman=item.get("roman"),
            pos=item.get("pos"),
            db_path=db_path,
        )
        if not did_update:
            add_word(
                word=item["word"],
                roman=item.get("roman"),
                meaning_hi=item.get("meaning_hi"),
                meaning_en=item.get("meaning_en"),
                pos=item.get("pos"),
                freq=1,
                db_path=db_path,
            )
        applied += 1
    return {"applied": applied, "total": len(FOUNDATIONAL_SEED_MEANINGS)}


def get_meanings_stats(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Return statistical summary of lexicon meanings coverage."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT count(1) FROM words WHERE (dialect IS NULL OR dialect != 'english')"
        )
        total_native = int(cursor.fetchone()[0])

        cursor.execute(
            """
            SELECT count(1) FROM words
            WHERE (dialect IS NULL OR dialect != 'english')
              AND ((meaning_hi IS NOT NULL AND meaning_hi != '')
                   OR (meaning_en IS NOT NULL AND meaning_en != ''))
            """
        )
        annotated = int(cursor.fetchone()[0])

        empty = total_native - annotated
        pct = (annotated / total_native * 100.0) if total_native > 0 else 0.0

    return {
        "total_words": total_native,
        "annotated_words": annotated,
        "empty_words": empty,
        "coverage_percentage": round(pct, 2),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for meanings export, import, and stats."""
    parser = argparse.ArgumentParser(
        description="Manage lexical meanings and community annotation workflows."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: stats
    stats_p = subparsers.add_parser("stats", help="Show meanings coverage statistics")
    stats_p.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )

    # Subcommand: export
    export_p = subparsers.add_parser(
        "export", help="Export words template to CSV for annotation"
    )
    export_p.add_argument("output_csv", type=str, help="Destination CSV file path")
    export_p.add_argument(
        "--min-freq",
        type=int,
        default=1,
        help="Minimum word frequency to export (default: 1)",
    )
    export_p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of words to export (default: all)",
    )
    export_p.add_argument(
        "--script",
        type=str,
        choices=["devanagari", "latin", "all"],
        default="all",
        help="Filter by script: devanagari, latin, or all (default: all)",
    )
    export_p.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )

    # Subcommand: import
    import_p = subparsers.add_parser(
        "import", help="Import filled meanings from CSV file"
    )
    import_p.add_argument("input_csv", type=str, help="Source CSV file path")
    import_p.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )

    # Subcommand: bootstrap
    boot_p = subparsers.add_parser(
        "bootstrap", help="Bootstrap core foundational Bodo vocabulary"
    )
    boot_p.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )

    args = parser.parse_args(argv)

    if args.command == "stats":
        stats = get_meanings_stats(db_path=args.db)
        print("Lexicon Meanings Coverage:")
        print(f"  Total native words: {stats['total_words']}")
        print(f"  Annotated with meaning: {stats['annotated_words']}")
        print(f"  Empty meanings: {stats['empty_words']}")
        print(f"  Coverage: {stats['coverage_percentage']}%")
        return 0

    if args.command == "export":
        count = export_meanings_csv(
            out_path=args.output_csv,
            db_path=args.db,
            min_freq=args.min_freq,
            limit=args.limit,
            script=args.script,
        )
        print(f"Exported {count} words to '{args.output_csv}'.")
        return 0

    if args.command == "import":
        res = import_meanings_csv(csv_path=args.input_csv, db_path=args.db)
        print(
            f"Imported from '{args.input_csv}': "
            f"{res['updated']} updated, {res['inserted']} inserted "
            f"out of {res['total']} rows."
        )
        return 0

    if args.command == "bootstrap":
        b_res = bootstrap_seed_meanings(db_path=args.db)
        print(f"Bootstrapped {b_res['applied']} foundational words with meanings.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
