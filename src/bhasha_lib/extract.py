"""Extraction pipeline for loading text files into the SQLite database."""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

from bhasha_lib.db import (
    DEFAULT_DB_PATH,
    add_occurrence,
    add_word,
    init_db,
)
from bhasha_lib.english import is_english_word
from bhasha_lib.tokenizer import tokenize, tokenize_roman

# Licenses that permit storing context snippets
OPEN_LICENSES: frozenset[str] = frozenset(
    {"public_domain", "public-domain", "cc0", "cc-by-sa", "cc_by_sa"}
)


def is_open_license(license_str: str) -> bool:
    """Check if the license permits storing context snippets."""
    if not license_str:
        return False
    return license_str.strip().lower() in OPEN_LICENSES


def make_context_snippet(line: str, target_word: str, max_words: int = 15) -> str:
    """Extract a context snippet of at most max_words from line around target_word."""
    words = line.strip().split()
    if len(words) <= max_words:
        return " ".join(words)

    # Locate the word within whitespace-separated tokens
    target_idx = -1
    for i, w in enumerate(words):
        if target_word in w:
            target_idx = i
            break

    if target_idx == -1:
        target_idx = 0

    half = max_words // 2
    start = max(0, target_idx - half)
    end = min(len(words), start + max_words)
    start = max(0, end - max_words)
    return " ".join(words[start:end])


def extract_file(
    path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
    source_id: int = 1,
    license: str = "",
    script: str = "devanagari",
    mark_english: bool = True,
    filter_english: bool = False,
) -> dict[str, int]:
    """Read a UTF-8 text file, tokenize lines, count frequencies, and store in DB.

    For each word, stores up to 5 occurrences (line_no and context
    snippet of <= 15 words) only if the license is an approved open
    license ('public_domain', 'cc0', 'cc-by-sa').

    Args:
        path: Path to the UTF-8 text file.
        db_path: Path to the SQLite database.
        source_id: ID of the source record in the database.
        license: License string (e.g. 'public_domain', 'cc0', 'cc-by-sa').
        script: Tokenizer script: 'devanagari' (default) or 'latin'.
        mark_english: If True and script is latin, marks English words
            with dialect='english'.
        filter_english: If True and script is latin, skips inserting English words.

    Returns:
        Dictionary mapping each unique word to its frequency in the file.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Ensure DB tables exist
    init_db(db_path)

    open_lic = is_open_license(license)
    is_latin = script.lower() == "latin"
    word_counts: Counter[str] = Counter()
    word_occurrences: dict[str, list[tuple[int, str]]] = defaultdict(list)
    tokenizer_fn = tokenize_roman if is_latin else tokenize

    with open(file_path, encoding="utf-8-sig") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            tokens = tokenizer_fn(line)
            if not tokens:
                continue

            for token in tokens:
                word_counts[token] += 1
                if open_lic and len(word_occurrences[token]) < 5:
                    snippet = make_context_snippet(line, token, max_words=15)
                    word_occurrences[token].append((line_no, snippet))

    persisted_counts: dict[str, int] = {}
    # Persist words and their frequencies
    for word, freq in word_counts.items():
        is_eng = is_latin and is_english_word(word)
        if is_eng and filter_english:
            continue
        dialect_tag = "english" if (is_latin and mark_english and is_eng) else None
        add_word(word=word, freq=freq, dialect=dialect_tag, db_path=db_path)
        persisted_counts[word] = freq

    # Persist occurrences if license permits
    if open_lic:
        for word, occurrences in word_occurrences.items():
            if is_latin and filter_english and is_english_word(word):
                continue
            for line_no, context in occurrences:
                add_occurrence(
                    word=word,
                    source_id=source_id,
                    line_no=line_no,
                    context=context,
                    db_path=db_path,
                )

    return persisted_counts


def main(argv: list[str] | None = None) -> int:
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract words and occurrences from a text file into SQLite database."
        )
    )
    parser.add_argument("txt_file", type=str, help="Path to input UTF-8 text file")
    parser.add_argument(
        "--source-id",
        type=int,
        required=True,
        help="Source ID in the database",
    )
    parser.add_argument(
        "--license",
        type=str,
        required=True,
        help="License type (e.g. public_domain, cc0, cc-by-sa)",
    )
    parser.add_argument(
        "--script",
        type=str,
        choices=["devanagari", "latin"],
        default="devanagari",
        help="Script tokenizer: devanagari (default) or latin",
    )
    parser.add_argument(
        "--mark-english",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Mark identified English words with dialect='english' (default: True)",
    )
    parser.add_argument(
        "--filter-english",
        action="store_true",
        default=False,
        help="Exclude identified English words from being inserted into words table",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    args = parser.parse_args(argv)

    stats = extract_file(
        path=args.txt_file,
        db_path=args.db,
        source_id=args.source_id,
        license=args.license,
        script=args.script,
        mark_english=args.mark_english,
        filter_english=args.filter_english,
    )
    print(f"Extracted {len(stats)} unique words from {args.txt_file}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
