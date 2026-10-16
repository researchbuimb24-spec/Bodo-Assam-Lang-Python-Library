import csv

from bhasha_lib.db import (
    add_occurrence,
    add_word,
    get_connection,
    init_db,
    search_word,
)
from bhasha_lib.meanings import (
    CONTEXT_1_COL,
    CONTEXT_2_COL,
    CSV_FIELDNAMES,
    export_for_review,
    get_meanings_stats,
    import_meanings,
    main,
    print_stats,
)


def test_export_writes_empty_meanings_and_correct_columns(tmp_path):
    db_file = tmp_path / "export_test.sqlite"
    init_db(db_file)

    # Word 1: no meaning (should be exported)
    add_word(word="बर'", roman="boro", freq=5, db_path=db_file)
    # Word 2: has Hindi meaning (should NOT be exported)
    add_word(
        word="गाहाम",
        roman="gaham",
        meaning_hi="अच्छा",
        freq=3,
        db_path=db_file,
    )
    # Word 3: has English meaning (should NOT be exported)
    add_word(
        word="राव",
        roman="rao",
        meaning_en="language",
        freq=2,
        db_path=db_file,
    )
    # Word 4: no meaning (should be exported)
    add_word(word="आफा", roman="afa", freq=1, db_path=db_file)

    csv_out = tmp_path / "review_out.csv"
    count = export_for_review(db_file, csv_out, limit=500, only_empty=True)

    assert count == 2
    assert csv_out.is_file()

    with open(csv_out, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == CSV_FIELDNAMES
        rows = list(reader)

    exported_words = {r["word"] for r in rows}
    assert exported_words == {"बर'", "आफा"}
    assert "गाहाम" not in exported_words
    assert "राव" not in exported_words


def test_import_updates_meanings_and_sets_status_and_verified_by(tmp_path):
    db_file = tmp_path / "import_test.sqlite"
    init_db(db_file)

    add_word(word="बर'", roman="boro", freq=5, db_path=db_file)
    w_initial = search_word("बर'", db_path=db_file)
    assert w_initial["status"] == "unverified"
    assert w_initial["verified_by"] is None

    # Prepare review CSV
    csv_file = tmp_path / "review_filled.csv"
    with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerow(
            {
                "word": "बर'",
                "roman": "boro",
                "meaning_hi": "बोडो (भाषा/समुदाय)",
                "meaning_en": "Bodo language and people",
                "pos": "noun",
                "origin": "bodo",
                "dialect": "standard",
                "verified_by": "Dr. Brahma",
                "notes": "Verified native term",
            }
        )

    res = import_meanings(csv_file, db_file)
    assert res["updated"] == 1
    assert res["rejected"] == 0
    assert res["conflicts"] == 0

    w_after = search_word("बर'", db_path=db_file)
    assert w_after["meaning_hi"] == "बोडो (भाषा/समुदाय)"
    assert w_after["meaning_en"] == "Bodo language and people"
    assert w_after["origin"] == "bodo"
    assert w_after["status"] == "community"
    assert w_after["verified_by"] == "Dr. Brahma"
    assert w_after["freq"] == 5  # Word frequency must remain untouched


def test_empty_verified_by_is_rejected(tmp_path):
    db_file = tmp_path / "reject_test.sqlite"
    init_db(db_file)

    add_word(word="राव", roman="rao", db_path=db_file)

    csv_file = tmp_path / "no_verifier.csv"
    with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        # meaning is provided but verified_by is empty
        writer.writerow(
            {
                "word": "राव",
                "roman": "rao",
                "meaning_hi": "भाषा",
                "meaning_en": "language",
                "origin": "bodo",
                "verified_by": "",
            }
        )

    res = import_meanings(csv_file, db_file)
    assert res["rejected"] == 1
    assert res["updated"] == 0

    # Ensure database record was NOT updated
    w = search_word("राव", db_path=db_file)
    assert w["meaning_hi"] is None
    assert w["status"] == "unverified"


def test_invalid_origin_is_rejected(tmp_path):
    db_file = tmp_path / "origin_test.sqlite"
    init_db(db_file)

    add_word(word="सम्पर्क", db_path=db_file)

    csv_file = tmp_path / "bad_origin.csv"
    with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerow(
            {
                "word": "सम्पर्क",
                "meaning_hi": "संपर्क",
                "origin": "sanskrit_derived",  # Invalid, must be bodo, loan, or unsure
                "verified_by": "Linguist",
            }
        )

    res = import_meanings(csv_file, db_file)
    assert res["rejected"] == 1
    assert res["updated"] == 0


def test_existing_meaning_is_not_overwritten_and_conflicts(tmp_path):
    db_file = tmp_path / "conflict_test.sqlite"
    init_db(db_file)

    # Word already has an established meaning
    add_word(
        word="गाहाम",
        roman="gaham",
        meaning_hi="अच्छा, शुभ",
        meaning_en="good",
        db_path=db_file,
    )

    csv_file = tmp_path / "conflict.csv"
    with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        # Incoming row gives conflicting Hindi meaning
        writer.writerow(
            {
                "word": "गाहाम",
                "meaning_hi": "खराब",
                "meaning_en": "good",
                "origin": "bodo",
                "verified_by": "Conflicting Contributor",
            }
        )

    res = import_meanings(csv_file, db_file)
    assert res["conflicts"] == 1
    assert res["updated"] == 0

    # Ensure original meaning in database was preserved
    w = search_word("गाहाम", db_path=db_file)
    assert w["meaning_hi"] == "अच्छा, शुभ"


def test_devanagari_round_trip_unchanged(tmp_path):
    db_file = tmp_path / "roundtrip_test.sqlite"
    init_db(db_file)

    original_word = "बर' राव"
    add_word(word=original_word, db_path=db_file)

    csv_file = tmp_path / "roundtrip.csv"
    export_for_review(db_file, csv_file, limit=10)

    # Read and fill in meaning while keeping word string intact
    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        reader = list(csv.DictReader(f))

    assert reader[0]["word"] == original_word

    with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerow(
            {
                "word": original_word,
                "roman": "boro rao",
                "meaning_hi": "बोडो भाषा",
                "meaning_en": "Bodo language",
                "origin": "bodo",
                "verified_by": "Native Speaker",
            }
        )

    import_meanings(csv_file, db_file)

    # Direct query to ensure exact Unicode character preservation
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT word, meaning_hi FROM words WHERE word = ?", (original_word,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == original_word
        assert row[1] == "बोडो भाषा"


def test_stats_and_cli(tmp_path):
    db_file = tmp_path / "cli_test.sqlite"
    init_db(db_file)

    add_word(word="word1", db_path=db_file)
    add_word(word="word2", db_path=db_file)

    # Stats initially
    stats = get_meanings_stats(db_file)
    assert stats["total_words"] == 2
    assert stats["words_with_meaning"] == 0
    assert stats["status_counts"]["unverified"] == 2
    printed = print_stats(db_file)
    assert printed["total_words"] == 2

    # CLI stats
    assert main(["stats", "--db", str(db_file)]) == 0

    # CLI export
    csv_file = tmp_path / "cli_out.csv"
    assert main(["export", str(csv_file), "--limit", "10", "--db", str(db_file)]) == 0
    assert csv_file.is_file()

    # CLI import
    assert main(["import", str(csv_file), "--db", str(db_file)]) == 0


def test_export_source_id_filtering(tmp_path):
    """Verify --source-id filters only words with occurrences from that source."""
    db_file = tmp_path / "source_filter.sqlite"
    init_db(db_file)

    add_word(word="word_source_10", db_path=db_file)
    add_occurrence(
        word="word_source_10",
        source_id=10,
        line_no=1,
        context="Story line 1",
        db_path=db_file,
    )

    add_word(word="word_source_2", db_path=db_file)
    add_occurrence(
        word="word_source_2",
        source_id=2,
        line_no=5,
        context="Aksharantar line",
        db_path=db_file,
    )

    add_word(word="word_no_occ", db_path=db_file)

    csv_file = tmp_path / "src_10.csv"
    count = export_for_review(db_file, csv_file, source_id=10)
    assert count == 1

    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["word"] == "word_source_10"


def test_export_with_context_columns(tmp_path):
    """Verify context columns are filled from occurrences and empty when none exist."""
    db_file = tmp_path / "context_test.sqlite"
    init_db(db_file)

    add_word(word="word_with_ctx", db_path=db_file)
    add_occurrence(
        word="word_with_ctx",
        source_id=10,
        line_no=10,
        context="First snippet",
        db_path=db_file,
    )
    add_occurrence(
        word="word_with_ctx",
        source_id=10,
        line_no=20,
        context="Second snippet",
        db_path=db_file,
    )
    add_occurrence(
        word="word_with_ctx",
        source_id=10,
        line_no=30,
        context="Third snippet",
        db_path=db_file,
    )

    add_word(word="word_zero_ctx", db_path=db_file)

    csv_file = tmp_path / "with_ctx.csv"
    count = export_for_review(db_file, csv_file, with_context=True)
    assert count == 2

    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert CONTEXT_1_COL in reader.fieldnames
        assert CONTEXT_2_COL in reader.fieldnames
        rows = {r["word"]: r for r in reader}

    assert rows["word_with_ctx"][CONTEXT_1_COL] == "First snippet"
    assert rows["word_with_ctx"][CONTEXT_2_COL] == "Second snippet"
    assert rows["word_zero_ctx"][CONTEXT_1_COL] == ""
    assert rows["word_zero_ctx"][CONTEXT_2_COL] == ""


def test_export_min_freq_order_and_exclude_hyphen(tmp_path):
    """Verify --min-freq, --order freq, and --exclude-hyphen."""
    db_file = tmp_path / "freq_filter.sqlite"
    init_db(db_file)

    add_word(word="rare_word", freq=1, db_path=db_file)
    add_word(word="common_word", freq=15, db_path=db_file)
    add_word(word="mid_word", freq=5, db_path=db_file)
    add_word(word="hyphen-word", freq=25, db_path=db_file)

    csv_file = tmp_path / "freq_out.csv"
    count = export_for_review(
        db_file,
        csv_file,
        min_freq=3,
        order="freq",
        exclude_hyphen=True,
    )
    # rare_word (freq 1 < 3) and hyphen-word (contains '-') are excluded
    assert count == 2

    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # Must be ordered by freq descending: common_word (15) before mid_word (5)
    assert [r["word"] for r in rows] == ["common_word", "mid_word"]


def test_import_with_context_columns_and_old_layout(tmp_path):
    """Verify import ignores context columns and old layout still imports cleanly."""
    db_file = tmp_path / "import_compat.sqlite"
    init_db(db_file)

    add_word(word="word_ctx_test", db_path=db_file)
    add_occurrence(
        word="word_ctx_test",
        source_id=10,
        line_no=1,
        context="Permanent context",
        db_path=db_file,
    )

    # 1. Export with context columns
    csv_file = tmp_path / "compat_out.csv"
    export_for_review(db_file, csv_file, with_context=True)

    # 2. Fill in meaning in the exported CSV
    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    rows[0]["meaning_hi"] = "अर्थ"
    rows[0]["meaning_en"] = "meaning"
    rows[0]["origin"] = "bodo"
    rows[0]["verified_by"] = "Verifier A"
    # Even if someone modifies the read-only context columns:
    rows[0][CONTEXT_1_COL] = "Modified context in CSV"

    with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    res = import_meanings(csv_file, db_file)
    assert res["updated"] == 1

    # Word meaning in DB is updated
    w = search_word("word_ctx_test", db_path=db_file)
    assert w["meaning_hi"] == "अर्थ"
    assert w["status"] == "community"

    # Context in DB occurrences table was NOT changed or corrupted
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT context FROM occurrences WHERE word = 'word_ctx_test'")
        db_context = cursor.fetchone()[0]
        assert db_context == "Permanent context"

    # 3. Test old layout CSV (without context columns) still imports seamlessly
    old_csv = tmp_path / "old_layout.csv"
    add_word(word="old_layout_word", db_path=db_file)
    with open(old_csv, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerow(
            {
                "word": "old_layout_word",
                "meaning_hi": "पुराना",
                "origin": "bodo",
                "verified_by": "Verifier Old",
            }
        )
    res_old = import_meanings(old_csv, db_file)
    assert res_old["updated"] == 1
    w_old = search_word("old_layout_word", db_path=db_file)
    assert w_old["meaning_hi"] == "पुराना"
