"""Folk songs and oral literature loader with ethical consent enforcement."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from bhasha_lib.consent import ConsentError, ConsentRecord, validate_consent_dict
from bhasha_lib.db import (
    DEFAULT_DB_PATH,
    add_culture_item,
    add_source,
    add_word,
    get_connection,
    init_db,
)
from bhasha_lib.tokenizer import tokenize, tokenize_roman


def parse_folk_song_markdown(
    content: str, file_name: str = "document"
) -> tuple[dict[str, Any], str]:
    """Parse YAML header and song lyrics from markdown content.

    Raises:
        ValueError: If header delimiters are missing or invalid YAML.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(
            f"Invalid folk song file in '{file_name}': "
            "Missing starting '---' YAML header."
        )

    closing_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing_idx = i
            break

    if closing_idx == -1:
        raise ValueError(
            f"Invalid folk song file in '{file_name}': "
            "Missing closing '---' YAML header."
        )

    header_yaml = "\n".join(lines[1:closing_idx])
    lyrics = "\n".join(lines[closing_idx + 1 :]).strip()

    header_data = yaml.safe_load(header_yaml) or {}
    if not isinstance(header_data, dict):
        raise ValueError(
            f"Invalid YAML frontmatter in '{file_name}': Expected key-value dictionary."
        )

    return header_data, lyrics


def load_folk_song_file(
    file_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Validate consent and load a single folk song into the database.

    Raises:
        ConsentError: If the song lacks verified written consent.
        ValueError: If required metadata fields (title, lyrics) are missing.

    Returns:
        The inserted culture_item ID.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Folk song file not found: {path}")

    init_db(db_path)
    text = path.read_text(encoding="utf-8")
    header, lyrics = parse_folk_song_markdown(text, file_name=path.name)

    title = str(header.get("title") or "").strip()
    if not title:
        raise ValueError(f"Folk song '{path.name}' is missing required 'title'.")
    if not lyrics:
        raise ValueError(f"Folk song '{path.name}' has empty lyrics.")

    # Strictly enforce consent verification
    consent_record: ConsentRecord = validate_consent_dict(
        header.get("consent"), item_title=title
    )

    category = str(header.get("category") or "folk_song").strip()
    genre = str(header.get("genre") or "traditional").strip()
    region = str(header.get("region") or "").strip()
    license_type = str(header.get("license") or "CC-BY-NC-SA-4.0").strip()
    lyrics_script = str(header.get("lyrics_script") or "devanagari").strip().lower()

    instruments = header.get("instruments") or []
    if isinstance(instruments, list):
        inst_str = ", ".join(str(i).strip() for i in instruments if str(i).strip())
    else:
        inst_str = str(instruments).strip()

    related_words = [inst_str, genre] if inst_str else [genre]
    related_str = ", ".join(filter(None, related_words))

    # Register or find source record
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM sources WHERE title = ? AND type = 'folk_song'",
            (title,),
        )
        row = cursor.fetchone()
        if row is not None:
            source_id = int(row[0])
        else:
            source_id = add_source(
                title=title,
                type="folk_song",
                author=consent_record.performer_name,
                license=license_type,
                contributor=consent_record.consent_holder,
                file_path=str(path),
                db_path=db_path,
            )

    # Ingest into culture_items table
    description = (
        f"Genre: {genre}\nPerformer: {consent_record.performer_name}\n\n{lyrics}"
    )
    item_id = add_culture_item(
        category=category,
        title=title,
        description=description,
        region=region if region else None,
        related_words=related_str,
        source_id=source_id,
        db_path=db_path,
    )

    # Tokenize lyrics into vocabulary table
    tokenizer_fn = tokenize_roman if lyrics_script == "latin" else tokenize
    tokens = tokenizer_fn(lyrics)
    for token in tokens:
        add_word(word=token, freq=1, db_path=db_path)

    return item_id


def load_folk_songs_dir(
    dir_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
    skip_unconsented: bool = False,
) -> list[int]:
    """Load all compliant folk songs from a folder into the database.

    Args:
        dir_path: Directory containing folk song markdown files.
        db_path: SQLite database path.
        skip_unconsented: If True, skips files with invalid consent instead of failing.

    Returns:
        List of inserted culture item IDs.
    """
    directory = Path(dir_path)
    if not directory.is_dir():
        raise FileNotFoundError(f"Folk songs directory not found: {directory}")

    loaded_ids: list[int] = []
    for file_path in sorted(directory.glob("*.md")):
        try:
            item_id = load_folk_song_file(file_path, db_path=db_path)
            loaded_ids.append(item_id)
        except ConsentError as e:
            if skip_unconsented:
                print(f"[Skipping] {file_path.name}: {e}", file=sys.stderr)
                continue
            raise

    return loaded_ids


def verify_folk_songs_dir(dir_path: str | Path) -> dict[str, list[str]]:
    """Audit a directory and classify files by consent compliance."""
    directory = Path(dir_path)
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")

    report: dict[str, list[str]] = {
        "valid": [],
        "pending": [],
        "invalid": [],
    }

    for file_path in sorted(directory.glob("*.md")):
        try:
            text = file_path.read_text(encoding="utf-8")
            header, _ = parse_folk_song_markdown(text, file_name=file_path.name)
            validate_consent_dict(header.get("consent"), item_title=file_path.name)
            report["valid"].append(file_path.name)
        except ConsentError as e:
            if "status is 'pending'" in str(e).lower():
                report["pending"].append(file_path.name)
            else:
                report["invalid"].append(file_path.name)
        except Exception:
            report["invalid"].append(file_path.name)

    return report


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for folk songs and oral literature."""
    parser = argparse.ArgumentParser(
        description="Manage and verify folk songs and audio with ethical consent."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: verify
    verify_p = subparsers.add_parser(
        "verify", help="Verify consent compliance in folk songs folder"
    )
    verify_p.add_argument(
        "dir", type=str, help="Directory containing folk song markdown files"
    )

    # Subcommand: load
    load_p = subparsers.add_parser(
        "load", help="Load consented folk songs into SQLite database"
    )
    load_p.add_argument(
        "dir", type=str, help="Directory containing folk song markdown files"
    )
    load_p.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    load_p.add_argument(
        "--skip-unconsented",
        action="store_true",
        help="Skip unconsented files rather than raising an error",
    )

    args = parser.parse_args(argv)

    if args.command == "verify":
        res = verify_folk_songs_dir(args.dir)
        print("Folk Songs Consent Audit:")
        print(f"  Valid / Approved ({len(res['valid'])}): {res['valid']}")
        print(f"  Pending Approval ({len(res['pending'])}): {res['pending']}")
        print(f"  Invalid / Rejected ({len(res['invalid'])}): {res['invalid']}")
        return 0 if not res["invalid"] else 1

    if args.command == "load":
        loaded = load_folk_songs_dir(
            args.dir, db_path=args.db, skip_unconsented=args.skip_unconsented
        )
        print(f"Loaded {len(loaded)} consented folk song(s) into '{args.db}'.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
