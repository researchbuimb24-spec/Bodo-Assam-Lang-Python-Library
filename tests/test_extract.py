import sqlite3

from bhasha_lib.db import add_source, init_db, search_word
from bhasha_lib.extract import (
    extract_file,
    is_english_inflection,
    main,
    strip_gutenberg,
)


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


def test_strip_gutenberg():
    """Verify strip_gutenberg removes header before START and footer from END onward."""
    text = (
        "The Project Gutenberg eBook\n"
        "Some preface information\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK TALES ***\n"
        "First story line.\n"
        "Second story line.\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK TALES ***\n"
        "Project Gutenberg license terms and conditions...\n"
    )
    stripped = strip_gutenberg(text)
    assert "*** START OF" not in stripped
    assert "*** END OF" not in stripped
    assert "The Project Gutenberg eBook" not in stripped
    assert "license terms" not in stripped
    assert "First story line." in stripped
    assert "Second story line." in stripped

    # Text without markers remains untouched
    plain = "Just plain text\nwith no markers\n"
    assert strip_gutenberg(plain) == plain


def test_extract_gutenberg_and_english_wordlist(tmp_path):
    """Verify header/footer removal and wordlist filtering with origin/status check."""
    fake_book = tmp_path / "fake_gutenberg_book.txt"
    fake_book.write_text(
        "Gutenberg Preamble Header text\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK FAKE ***\n"
        "Âng brai burui man.\n"
        "This is an english translation sentence.\n"
        "Brai fainânai khithânaise.\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK FAKE ***\n"
        "Gutenberg Postamble Full License text here\n",
        encoding="utf-8",
    )

    wordlist = tmp_path / "tiny_wordlist.txt"
    wordlist.write_text(
        "this\nis\nan\nenglish\ntranslation\nsentence\n",
        encoding="utf-8",
    )

    db_file = tmp_path / "fake_book.sqlite"
    init_db(db_file)
    source_id = add_source(
        title="Fake Book",
        license="public_domain",
        db_path=db_file,
    )

    freqs = extract_file(
        path=fake_book,
        db_path=db_file,
        source_id=source_id,
        license="public_domain",
        script="latin",
        gutenberg=True,
        english_wordlist=wordlist,
    )

    # Gutenberg header & footer words should NOT be present
    assert "preamble" not in freqs
    assert "postamble" not in freqs

    # English words from wordlist should be skipped
    assert "this" not in freqs
    assert "translation" not in freqs
    assert "sentence" not in freqs

    # Bodo words should be stored
    assert "brai" in freqs
    assert "burui" in freqs
    assert "khithânaise" in freqs

    # Check origin = NULL and status = 'unverified'
    w = search_word("brai", db_path=db_file)
    assert w is not None
    assert w["origin"] is None
    assert w["status"] == "unverified"


def test_extract_cli_gutenberg_and_wordlist(tmp_path):
    """Verify CLI accepts --gutenberg and --english-wordlist."""
    fake_book = tmp_path / "cli_book.txt"
    fake_book.write_text(
        "Header\n"
        "*** START OF TEST ***\n"
        "Gåthå brai gaham\n"
        "*** END OF TEST ***\n"
        "Footer\n",
        encoding="utf-8",
    )
    wordlist = tmp_path / "cli_words.txt"
    wordlist.write_text("test\nenglish\n", encoding="utf-8")

    db_file = tmp_path / "cli_test.sqlite"
    init_db(db_file)
    source_id = add_source(title="CLI Book", license="public_domain", db_path=db_file)

    code = main(
        [
            str(fake_book),
            "--source-id",
            str(source_id),
            "--license",
            "public_domain",
            "--script",
            "latin",
            "--gutenberg",
            "--english-wordlist",
            str(wordlist),
            "--db",
            str(db_file),
        ]
    )
    assert code == 0
    assert search_word("brai", db_path=db_file) is not None


def test_is_english_inflection_rules():
    """Verify inflection stem matching and minimum 3-letter stem constraint."""
    wordlist = {"tiger", "walk", "stop", "run", "dance", "quick", "king", "a", "he"}

    # "tigers", "walking", "stopped" should match stems in wordlist
    assert is_english_inflection("tigers", wordlist) is True
    assert is_english_inflection("walking", wordlist) is True
    assert is_english_inflection("stopped", wordlist) is True

    # Other common endings: 's, es, ed, d, ly, er, est
    assert is_english_inflection("king's", wordlist) is True
    assert is_english_inflection("quickly", wordlist) is True

    # Short stems under 3 letters are NOT stripped
    # e.g. "as" -> ending "s", stem "a" (len 1 < 3) -> False
    assert is_english_inflection("as", wordlist) is False
    # e.g. "he's" -> ending "'s", stem "he" (len 2 < 3) -> False
    assert is_english_inflection("he's", wordlist) is False
    # Non-English word not in wordlist
    assert is_english_inflection("khithanaise", wordlist) is False


def test_extract_with_keep_list_and_inflections(tmp_path):
    """Verify inflections are skipped, keep-list rescues words, and DB updates."""
    text_file = tmp_path / "bilingual_inflections.txt"
    text_file.write_text(
        "Two tigers were walking in the jungle.\n"
        "The boy stopped near the river.\n"
        "Âng ha mairong be khithânaise.\n",
        encoding="utf-8",
    )

    wordlist = tmp_path / "wordlist.txt"
    wordlist.write_text(
        "tiger\nwalk\nstop\nin\nthe\nnear\ntwo\nbe\nha\n", encoding="utf-8"
    )

    # "be" and "ha" are in wordlist but also in keep list -> MUST be rescued and kept
    keep_list = tmp_path / "keep_list.txt"
    keep_list.write_text("be\nha\n", encoding="utf-8")

    db_file = tmp_path / "inflection_test.sqlite"
    init_db(db_file)
    source_id = add_source(
        title="Inflection Source",
        license="public_domain",
        db_path=db_file,
    )

    freqs = extract_file(
        path=text_file,
        db_path=db_file,
        source_id=source_id,
        license="public_domain",
        script="latin",
        english_wordlist=wordlist,
        keep_list=keep_list,
    )

    # Inflected English words MUST be skipped
    assert "tigers" not in freqs
    assert "walking" not in freqs
    assert "stopped" not in freqs

    # Regular English words in wordlist MUST be skipped
    assert "two" not in freqs
    assert "near" not in freqs
    assert "in" not in freqs

    # Rescued Bodo words from keep list MUST be kept even though in wordlist
    assert "be" in freqs
    assert "ha" in freqs
    assert search_word("be", db_path=db_file) is not None
    assert search_word("ha", db_path=db_file) is not None

    # Normal Bodo words kept
    assert "khithânaise" in freqs
    assert search_word("khithânaise", db_path=db_file) is not None
