import json
import sqlite3
import zipfile

from bhasha_lib.db import init_db, search_word
from bhasha_lib.loaders.aksharantar import load_aksharantar, main


def create_fake_aksharantar_zip(zip_path):
    """Helper to create a small test zip file mimicking the Aksharantar brx format."""
    records = [
        {"unique_identifier": "1", "native word": "बर'", "english word": "boro"},
        {"unique_identifier": "2", "native word": "बर'", "english word": "boro"},
        {"unique_identifier": "3", "native word": "राव", "english word": "rao"},
        {"unique_identifier": "4", "native word": "", "english word": "empty"},
        {"unique_identifier": "5", "native word": "EnglishOnly", "english word": "eng"},
        {"unique_identifier": "6", "native word": "12345", "english word": "digits"},
    ]
    with zipfile.ZipFile(zip_path, "w") as z:
        content = "\n".join(json.dumps(r) for r in records)
        z.writestr("brx_sample.json", content)


def test_load_aksharantar_fake_zip(tmp_path):
    """Verify unique words stored once, invalid entries skipped, license saved."""
    fake_zip = tmp_path / "fake_brx.zip"
    create_fake_aksharantar_zip(fake_zip)

    db_file = tmp_path / "aksharantar_test.sqlite"
    init_db(db_file)

    summary = load_aksharantar(fake_zip, db_path=db_file, license="CC-BY-4.0")

    # 6 total records in fake zip
    assert summary["records_read"] == 6
    # 2 unique valid words: "बर'" and "राव"
    assert summary["unique_words_stored"] == 2
    # 3 skipped: empty, EnglishOnly, 12345
    assert summary["records_skipped"] == 3

    # Check words table
    w1 = search_word("बर'", db_path=db_file)
    assert w1 is not None
    assert w1["roman"] == "boro"
    assert w1["freq"] == 1  # stored once with freq=1

    w2 = search_word("राव", db_path=db_file)
    assert w2 is not None
    assert w2["roman"] == "rao"
    assert w2["freq"] == 1

    assert search_word("EnglishOnly", db_path=db_file) is None

    # Verify no occurrences are created
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM occurrences")
    occ_count = cursor.fetchone()[0]
    assert occ_count == 0

    # Verify source record contains the given license
    cursor.execute(
        "SELECT title, author, license FROM sources WHERE id = ?",
        (summary["source_id"],),
    )
    source_row = cursor.fetchone()
    conn.close()

    assert source_row is not None
    assert source_row[0] == "Aksharantar brx"
    assert source_row[1] == "AI4Bharat"
    assert source_row[2] == "CC-BY-4.0"


def test_aksharantar_cli(tmp_path):
    """Verify CLI entry point python -m bhasha_lib.loaders.aksharantar."""
    fake_zip = tmp_path / "cli_brx.zip"
    create_fake_aksharantar_zip(fake_zip)

    db_file = tmp_path / "cli_aksharantar.sqlite"

    exit_code = main(
        [
            str(fake_zip),
            "--license",
            "Public Domain",
            "--db",
            str(db_file),
        ]
    )
    assert exit_code == 0

    w = search_word("बर'", db_path=db_file)
    assert w is not None
    assert w["roman"] == "boro"
    assert w["freq"] == 1
