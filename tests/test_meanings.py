import csv

from bhasha_lib.db import add_word, get_connection, init_db, search_word
from bhasha_lib.meanings import (
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
