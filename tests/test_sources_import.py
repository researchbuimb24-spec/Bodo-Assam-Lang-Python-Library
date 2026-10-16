import sqlite3

from bhasha_lib.db import init_db
from bhasha_lib.sources_import import import_sources_csv, main


def test_import_sources_csv(tmp_path, capsys):
    """Verify importing sources creates rows and skips duplicates."""
    csv_file = tmp_path / "sources.csv"
    csv_content = """title,type,author,year,license,url,file_path
Bodo Grammar,book,S. Endle,1884,Public Domain,http://archive.org/endle,data/books/endle.txt
Bodo Folk Tales,book,J. D. Anderson,1895,Public Domain,http://archive.org/anderson,data/books/anderson.txt
Invalid Source,book,Unknown,2000,,http://example.org,data/books/invalid.txt
Bodo Grammar,duplicate,Another Author,1990,CC-BY,http://example.org/dup,data/books/dup.txt
"""
    csv_file.write_text(csv_content, encoding="utf-8")

    db_file = tmp_path / "test_sources.sqlite"
    init_db(db_file)

    stats = import_sources_csv(csv_file, db_path=db_file)

    # 4 lines total:
    # Line 2 (Bodo Grammar): imported (1)
    # Line 3 (Bodo Folk Tales): imported (2)
    # Line 4 (Invalid Source): rejected (empty license)
    # Line 5 (Bodo Grammar duplicate title): skipped
    assert stats["imported"] == 2
    assert stats["rejected"] == 1
    assert stats["skipped"] == 1

    # Check output prints rejected line
    captured = capsys.readouterr()
    assert "Rejected line 4" in captured.out
    assert "Invalid Source" in captured.out

    # Check DB rows
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT title, author, year, license FROM sources ORDER BY id")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 2
    assert rows[0][0] == "Bodo Grammar"
    assert rows[0][1] == "S. Endle"
    assert rows[0][2] == 1884
    assert rows[0][3] == "Public Domain"

    assert rows[1][0] == "Bodo Folk Tales"


def test_import_sources_cli(tmp_path):
    """Verify CLI entry point python -m bhasha_lib.sources_import."""
    csv_file = tmp_path / "cli_sources.csv"
    csv_content = """title,type,author,year,license,url,file_path
CLI Source 1,dataset,Author A,2021,CC0,http://example.org/1,path/1.txt
"""
    csv_file.write_text(csv_content, encoding="utf-8")

    db_file = tmp_path / "cli_sources.sqlite"

    exit_code = main([str(csv_file), "--db", str(db_file)])
    assert exit_code == 0

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT title, license FROM sources WHERE title = 'CLI Source 1'")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "CLI Source 1"
    assert row[1] == "CC0"
