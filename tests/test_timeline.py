from bhasha_lib.culture import load_culture_dir
from bhasha_lib.db import add_culture_item, get_connection, init_db
from bhasha_lib.timeline import format_year_range, get_timeline, main, print_timeline


def test_timeline_loads_and_sorts_chronologically(tmp_path):
    """Verify get_timeline returns only items with year_start sorted chronologically."""
    db_file = tmp_path / "timeline_test.sqlite"
    init_db(db_file)

    add_culture_item(
        category="history",
        title="Script Accord",
        description="Agreement to adopt Devanagari script.",
        year_start=1975,
        confidence="verified",
        db_path=db_file,
    )
    add_culture_item(
        category="history",
        title="Sabha Foundation",
        description="Bodo Sahitya Sabha was founded in Basugaon.",
        year_start=1952,
        confidence="needs_check",
        db_path=db_file,
    )
    add_culture_item(
        category="history",
        title="Primary Medium",
        description="Bodo introduced as primary medium of instruction.",
        year_start=1963,
        confidence="verified",
        db_path=db_file,
    )
    add_culture_item(
        category="dance",
        title="Bagurumba",
        description="Traditional folk dance without specific historical year.",
        year_start=None,
        db_path=db_file,
    )

    events = get_timeline(db_file)
    assert len(events) == 3

    years = [e["year_start"] for e in events]
    titles = [e["title"] for e in events]

    assert years == [1952, 1963, 1975]
    assert titles == ["Sabha Foundation", "Primary Medium", "Script Accord"]
    assert events[0]["confidence"] == "needs_check"
    assert events[1]["confidence"] == "verified"


def test_timeline_same_year_sorting(tmp_path):
    """Verify events in the same year are properly ordered and formatted."""
    db_file = tmp_path / "same_year.sqlite"
    init_db(db_file)

    add_culture_item(
        category="history",
        title="Bodo lipi ka itihaas",
        description="Script evolution overview.",
        year_start=1952,
        year_end=1975,
        confidence="needs_check",
        db_path=db_file,
    )
    add_culture_item(
        category="history",
        title="Bodo Sahitya Sabha",
        description="Foundation in Basugaon.",
        year_start=1952,
        year_end=None,
        confidence="needs_check",
        db_path=db_file,
    )

    events = get_timeline(db_file)
    assert len(events) == 2

    assert events[0]["title"] == "Bodo Sahitya Sabha"
    assert events[0]["year_start"] == 1952
    assert events[0]["year_end"] is None

    assert events[1]["title"] == "Bodo lipi ka itihaas"
    assert events[1]["year_start"] == 1952
    assert events[1]["year_end"] == 1975

    assert format_year_range(1952, None) == "1952"
    assert format_year_range(1952, 1975) == "1952 - 1975"


def test_timeline_filters_by_category_and_year_range(tmp_path):
    """Verify filtering by category, from_year, and to_year."""
    db_file = tmp_path / "filter_test.sqlite"
    init_db(db_file)

    add_culture_item(
        category="history",
        title="Event 1952",
        year_start=1952,
        db_path=db_file,
    )
    add_culture_item(
        category="history",
        title="Event 1963",
        year_start=1963,
        db_path=db_file,
    )
    add_culture_item(
        category="festival",
        title="Festival 1963",
        year_start=1963,
        db_path=db_file,
    )
    add_culture_item(
        category="history",
        title="Event 1975",
        year_start=1975,
        db_path=db_file,
    )

    # Filter by category
    hist_only = get_timeline(db_file, category="history")
    assert len(hist_only) == 3

    # Filter by year range
    range_events = get_timeline(db_file, from_year=1960, to_year=1970)
    assert len(range_events) == 2
    assert {e["title"] for e in range_events} == {"Event 1963", "Festival 1963"}


def test_load_history_files_with_timeline_keys(tmp_path):
    """Verify load_culture_dir parses year_start, year_end, and confidence."""
    history_dir = tmp_path / "history"
    history_dir.mkdir()

    md_content = """---
category: history
title: Kokrajhar Medium Accord
region: Assam
year_start: 1963
confidence: needs_check
source: Historical Records
related_words: []
---
Bodo language medium declaration at Kokrajhar.
"""
    (history_dir / "medium.md").write_text(md_content, encoding="utf-8")

    db_file = tmp_path / "history_parse.sqlite"
    init_db(db_file)

    loaded = load_culture_dir(history_dir, db_path=db_file)
    assert len(loaded) == 1

    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT category, title, year_start, year_end, confidence
            FROM culture_items
            WHERE id = ?
            """,
            (loaded[0],),
        )
        row = cursor.fetchone()
        assert row["category"] == "history"
        assert row["title"] == "Kokrajhar Medium Accord"
        assert row["year_start"] == 1963
        assert row["year_end"] is None
        assert row["confidence"] == "needs_check"


def test_timeline_cli_and_printing(tmp_path, capsys):
    """Verify timeline CLI output formatting."""
    db_file = tmp_path / "cli_timeline.sqlite"
    init_db(db_file)

    add_culture_item(
        category="history",
        title="Bodo Sahitya Sabha",
        description="Foundation in Basugaon.",
        region="Assam",
        year_start=1952,
        confidence="needs_check",
        db_path=db_file,
    )

    exit_code = main(["--db", str(db_file)])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "1952: Bodo Sahitya Sabha (Assam) - history [needs_check]" in out
    assert "Foundation in Basugaon." in out

    # Empty timeline output
    empty_db = tmp_path / "empty.sqlite"
    init_db(empty_db)
    print_timeline([])
    empty_out = capsys.readouterr().out
    assert "No timeline events found." in empty_out
