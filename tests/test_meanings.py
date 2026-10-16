from bhasha_lib.db import (
    add_occurrence,
    add_word,
    init_db,
    search_word,
    update_word_meaning,
)
from bhasha_lib.meanings import (
    bootstrap_seed_meanings,
    export_meanings_csv,
    get_meanings_stats,
    import_meanings_csv,
    main,
)


def test_update_word_meaning_preserves_freq(tmp_path):
    db_file = tmp_path / "meanings_test.sqlite"
    init_db(db_file)

    # Insert word with freq=10 and no meaning
    add_word(word="गाहाम", freq=10, db_path=db_file)
    w_initial = search_word("गाहाम", db_path=db_file)
    assert w_initial["freq"] == 10
    assert w_initial["meaning_hi"] is None

    # Update meaning
    updated = update_word_meaning(
        word="गाहाम",
        meaning_hi="अच्छा, शुभ",
        meaning_en="good, auspicious",
        pos="adjective",
        db_path=db_file,
    )
    assert updated is True

    # Frequency must still be exactly 10
    w_after = search_word("गाहाम", db_path=db_file)
    assert w_after["freq"] == 10
    assert w_after["meaning_hi"] == "अच्छा, शुभ"
    assert w_after["meaning_en"] == "good, auspicious"
    assert w_after["pos"] == "adjective"


def test_bootstrap_seed_meanings(tmp_path):
    db_file = tmp_path / "bootstrap_test.sqlite"
    init_db(db_file)

    res = bootstrap_seed_meanings(db_path=db_file)
    assert res["applied"] > 25

    w_bodo = search_word("बड़ो", db_path=db_file)
    assert w_bodo is not None
    assert "बोडो" in w_bodo["meaning_hi"]
    assert "Bodo" in w_bodo["meaning_en"]

    w_rao = search_word("राव", db_path=db_file)
    assert w_rao is not None
    assert w_rao["pos"] == "noun"


def test_export_and_import_meanings_csv(tmp_path):
    db_file = tmp_path / "csv_test.sqlite"
    init_db(db_file)

    # Insert some words with occurrences
    add_word(word="बर'", freq=5, db_path=db_file)
    add_occurrence(
        word="बर'", source_id=1, line_no=10, context="बर' राव गाहाम", db_path=db_file
    )

    add_word(word="राव", freq=3, db_path=db_file)
    add_word(word="गाहाम", freq=1, meaning_hi="अच्छा", db_path=db_file)

    csv_out = tmp_path / "exported_template.csv"
    count = export_meanings_csv(
        out_path=csv_out,
        db_path=db_file,
        only_empty=True,
    )
    # "बर'" and "राव" have empty meanings; "गाहाम" already has meaning_hi
    assert count == 2
    assert csv_out.is_file()

    # Content includes example context
    content = csv_out.read_text(encoding="utf-8-sig")
    assert "बर'" in content
    assert "बर' राव गाहाम" in content

    # Simulate annotator filling in meaning
    filled_csv = tmp_path / "filled.csv"
    filled_csv.write_text(
        "word,roman,meaning_hi,meaning_en,pos,tone,dialect,freq,example_context\n"
        "बर',boro,बोडो (जाति/भाषा),Bodo people or language,noun,,,,बर' राव गाहाम\n"
        "राव,rao,भाषा,language,noun,,,,,\n",
        encoding="utf-8-sig",
    )

    import_res = import_meanings_csv(csv_path=filled_csv, db_path=db_file)
    assert import_res["updated"] == 2

    # Verify updated in DB
    w_boro = search_word("बर'", db_path=db_file)
    assert w_boro["meaning_hi"] == "बोडो (जाति/भाषा)"
    assert w_boro["meaning_en"] == "Bodo people or language"
    assert w_boro["pos"] == "noun"
    assert w_boro["freq"] == 5  # Unchanged frequency


def test_get_meanings_stats(tmp_path):
    db_file = tmp_path / "stats_test.sqlite"
    init_db(db_file)

    add_word(word="word1", freq=1, meaning_hi="Meaning 1", db_path=db_file)
    add_word(word="word2", freq=1, db_path=db_file)

    stats = get_meanings_stats(db_path=db_file)
    assert stats["total_words"] == 2
    assert stats["annotated_words"] == 1
    assert stats["empty_words"] == 1
    assert stats["coverage_percentage"] == 50.0


def test_meanings_cli(tmp_path):
    db_file = tmp_path / "cli_test.sqlite"
    init_db(db_file)

    # CLI bootstrap
    assert main(["bootstrap", "--db", str(db_file)]) == 0

    # CLI stats
    assert main(["stats", "--db", str(db_file)]) == 0

    # CLI export
    csv_file = tmp_path / "cli_export.csv"
    assert main(["export", str(csv_file), "--db", str(db_file)]) == 0
    assert csv_file.is_file()

    # CLI import
    assert main(["import", str(csv_file), "--db", str(db_file)]) == 0
