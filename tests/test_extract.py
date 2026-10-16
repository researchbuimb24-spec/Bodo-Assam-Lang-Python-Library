import sqlite3

from bhasha_lib.db import add_source, init_db, search_word
from bhasha_lib.extract import extract_file, main


def test_extract_file_frequencies(tmp_path):
    """Verify extracting a small temporary file stores correct frequencies."""
    txt_file = tmp_path / "sample.txt"
    content = "बर' राव बर'\nराव बर' आफा\nबर' ख'र'सां\n"
    txt_file.write_text(content, encoding="utf-8")

    db_file = tmp_path / "lexicon_test.sqlite"
    init_db(db_file)
    source_id = add_source(title="Test Source", license="cc0", db_path=db_file)

    freqs = extract_file(
        path=txt_file,
        db_path=db_file,
        source_id=source_id,
        license="cc0",
    )

    # Word frequencies from the text:
    # "बर'" appears 4 times (2 on line 1, 1 on line 2, 1 on line 3)
    # "राव" appears 2 times (1 on line 1, 1 on line 2)
    # "आफा" appears 1 time (line 2)
    # "ख'र'सां" appears 1 time (line 3)
    assert freqs["बर'"] == 4
    assert freqs["राव"] == 2
    assert freqs["आफा"] == 1
    assert freqs["ख'र'सां"] == 1

    # Verify values persisted in SQLite
    w1 = search_word("बर'", db_path=db_file)
    assert w1 is not None
    assert w1["freq"] == 4

    w2 = search_word("राव", db_path=db_file)
    assert w2 is not None
    assert w2["freq"] == 2


def test_non_open_license_no_context_snippets(tmp_path):
    """Verify a non-open license stores word and frequency but NO context snippets."""
    txt_file = tmp_path / "copyrighted.txt"
    txt_file.write_text("बर' राव बर'\nराव बर' आफा\n", encoding="utf-8")

    db_file = tmp_path / "lexicon_closed.sqlite"
    init_db(db_file)
    source_id = add_source(
        title="Proprietary Book",
        license="All Rights Reserved",
        db_path=db_file,
    )

    extract_file(
        path=txt_file,
        db_path=db_file,
        source_id=source_id,
        license="All Rights Reserved",
    )

    # Words and frequency MUST be stored
    w = search_word("बर'", db_path=db_file)
    assert w is not None
    assert w["freq"] == 3

    # Occurrences table MUST contain no context snippets
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM occurrences")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 0


def test_max_five_occurrences_stored(tmp_path):
    """Verify for each word at most 5 occurrences are stored."""
    txt_file = tmp_path / "repeated.txt"
    # Write 8 lines with the word बर'
    lines = [f"लाइन {i} बर' राव जों" for i in range(1, 9)]
    txt_file.write_text("\n".join(lines), encoding="utf-8")

    db_file = tmp_path / "lexicon_occ.sqlite"
    init_db(db_file)
    source_id = add_source(
        title="Open Corpus", license="public_domain", db_path=db_file
    )

    extract_file(
        path=txt_file,
        db_path=db_file,
        source_id=source_id,
        license="public_domain",
    )

    # Frequency should be 8
    w = search_word("बर'", db_path=db_file)
    assert w is not None
    assert w["freq"] == 8

    # Occurrences should be capped at 5
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT line_no, context FROM occurrences WHERE word = ?", ("बर'",))
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 5
    # Check that context snippets are at most 15 words
    for _, context in rows:
        assert len(context.split()) <= 15


def test_cli_main(tmp_path):
    """Verify CLI entry point python -m bhasha_lib.extract executes correctly."""
    txt_file = tmp_path / "cli_sample.txt"
    txt_file.write_text("बर' राव\n", encoding="utf-8")

    db_file = tmp_path / "cli_lexicon.sqlite"
    init_db(db_file)
    source_id = add_source(title="CLI Source", license="cc-by-sa", db_path=db_file)

    exit_code = main(
        [
            str(txt_file),
            "--source-id",
            str(source_id),
            "--license",
            "cc-by-sa",
            "--db",
            str(db_file),
        ]
    )
    assert exit_code == 0

    w = search_word("बर'", db_path=db_file)
    assert w is not None
    assert w["freq"] == 1


def test_extract_file_calls_init_db(tmp_path):
    """Verify extract_file automatically initializes the DB when it does not exist."""
    txt_file = tmp_path / "init_check.txt"
    txt_file.write_text("बर' राव\n", encoding="utf-8")

    db_file = tmp_path / "fresh_auto.sqlite"
    assert not db_file.exists()

    # Call extract_file directly without pre-calling init_db
    extract_file(
        path=txt_file,
        db_path=db_file,
        source_id=1,
        license="cc0",
    )
    assert db_file.exists()

    w = search_word("बर'", db_path=db_file)
    assert w is not None
    assert w["freq"] == 1


def test_extract_file_latin_script(tmp_path):
    """Verify extracting with script='latin' extracts Roman Bodo words."""
    txt_file = tmp_path / "latin_book.txt"
    text = "Boro and Kachari grammar by Rev. S. Endle in 1884. A ha-ba word.\n"
    txt_file.write_text(text, encoding="utf-8")

    db_file = tmp_path / "latin_test.sqlite"
    init_db(db_file)
    source_id = add_source(title="Endle 1884", license="public_domain", db_path=db_file)

    freqs = extract_file(
        path=txt_file,
        db_path=db_file,
        source_id=source_id,
        license="public_domain",
        script="latin",
    )

    assert "boro" in freqs
    assert "kachari" in freqs
    assert "ha-ba" in freqs
    assert "1884" not in freqs
    assert "a" not in freqs

    w = search_word("boro", db_path=db_file)
    assert w is not None
    assert w["word"] == "boro"


def test_extract_cli_latin_script(tmp_path):
    """Verify CLI with --script latin uses tokenize_roman."""
    txt_file = tmp_path / "cli_latin.txt"
    txt_file.write_text("Boro grammar book.\n", encoding="utf-8")

    db_file = tmp_path / "cli_latin.sqlite"
    init_db(db_file)
    source_id = add_source(title="Latin Source", license="cc-by-sa", db_path=db_file)

    exit_code = main(
        [
            str(txt_file),
            "--source-id",
            str(source_id),
            "--license",
            "cc-by-sa",
            "--script",
            "latin",
            "--db",
            str(db_file),
        ]
    )
    assert exit_code == 0

    w = search_word("boro", db_path=db_file)
    assert w is not None


def test_extract_latin_mark_english(tmp_path):
    """Verify English words are tagged with dialect='english'.

    Bodo words must not be tagged with dialect='english'.
    """
    txt_file = tmp_path / "bilingual.txt"
    txt_file.write_text(
        "Rev Endle wrote Boro grammar in Assam with gaham words.\n", encoding="utf-8"
    )

    db_file = tmp_path / "bilingual_marked.sqlite"
    init_db(db_file)
    source_id = add_source(title="Endle 1884", license="public_domain", db_path=db_file)

    freqs = extract_file(
        path=txt_file,
        db_path=db_file,
        source_id=source_id,
        license="public_domain",
        script="latin",
        mark_english=True,
        filter_english=False,
    )

    assert "grammar" in freqs
    assert "gaham" in freqs
    assert "boro" in freqs

    w_eng = search_word("grammar", db_path=db_file)
    assert w_eng is not None
    assert w_eng["dialect"] == "english"

    w_bodo = search_word("gaham", db_path=db_file)
    assert w_bodo is not None
    assert w_bodo["dialect"] is None or w_bodo["dialect"] != "english"


def test_extract_latin_filter_english(tmp_path):
    """Verify --filter-english completely excludes English words from DB."""
    txt_file = tmp_path / "bilingual_filter.txt"
    txt_file.write_text(
        "Rev Endle wrote Boro grammar in Assam with gaham words.\n", encoding="utf-8"
    )

    db_file = tmp_path / "bilingual_filtered.sqlite"
    init_db(db_file)
    source_id = add_source(
        title="Endle 1884 Filtered", license="public_domain", db_path=db_file
    )

    freqs = extract_file(
        path=txt_file,
        db_path=db_file,
        source_id=source_id,
        license="public_domain",
        script="latin",
        filter_english=True,
    )

    # "grammar", "wrote", "words" are English and should be filtered
    assert "grammar" not in freqs
    assert search_word("grammar", db_path=db_file) is None

    # Bodo words should be kept
    assert "gaham" in freqs
    assert search_word("gaham", db_path=db_file) is not None
