import unicodedata

from bhasha_lib.culture import load_culture_dir
from bhasha_lib.db import add_occurrence, add_source, add_word, init_db
from bhasha_lib.lookup import lookup_term, main, print_lookup_results


def test_lookup_exact_and_prefix_matches(tmp_path):
    """Verify lookup finds exact match first, then prefix matches, up to limit."""
    db_file = tmp_path / "lookup_test.sqlite"
    init_db(db_file)

    # Insert test words
    add_word(
        "बिलाइ",
        roman="bilai",
        meaning_en="leaf",
        origin="bodo",
        status="community",
        verified_by="Contributor A",
        freq=10,
        db_path=db_file,
    )
    add_word(
        "बिलाइफोर",
        roman="bilaifwr",
        meaning_en="leaves",
        origin="bodo",
        status="community",
        verified_by="Contributor A",
        freq=5,
        db_path=db_file,
    )
    add_word(
        "बिलाइसा",
        roman="bilaisa",
        meaning_en="small leaf",
        origin="bodo",
        status="community",
        verified_by="Contributor B",
        freq=2,
        db_path=db_file,
    )
    add_word(
        "हाग्रा",
        roman="hagra",
        meaning_en="forest",
        origin="bodo",
        status="unverified",
        freq=3,
        db_path=db_file,
    )

    res = lookup_term("बिलाइ", db_path=db_file)
    words = res["words"]
    assert len(words) == 3

    # Exact match must be first
    assert words[0]["word"] == "बिलाइ"
    assert words[0]["roman"] == "bilai"
    assert words[0]["meaning_en"] == "leaf"

    # Prefix matches follow
    prefix_words = [w["word"] for w in words[1:]]
    assert "बिलाइफोर" in prefix_words
    assert "बिलाइसा" in prefix_words
    assert "हाग्रा" not in prefix_words


def test_lookup_prints_not_found_when_no_match(tmp_path, capsys):
    """Verify clear 'not found' message when no words or culture items match."""
    db_file = tmp_path / "lookup_empty.sqlite"
    init_db(db_file)

    res = lookup_term("nonexistent_xyz", db_path=db_file)
    assert len(res["words"]) == 0
    assert len(res["culture_items"]) == 0

    print_lookup_results(res)
    captured = capsys.readouterr()
    assert "not found" in captured.out.lower()


def test_devanagari_term_works(tmp_path, capsys):
    """Verify lookup works with Devanagari input, occurrences, and culture items."""
    db_file = tmp_path / "lookup_devanagari.sqlite"
    init_db(db_file)

    source_id = add_source(
        title="Bodo Folklore Collection",
        license="CC-BY-4.0",
        db_path=db_file,
    )

    # Word with decomposed unicode to verify NFC normalization
    raw_word = "गाहाम"
    nfc_word = unicodedata.normalize("NFC", raw_word)

    add_word(
        nfc_word,
        roman="gaham",
        meaning_hi="अच्छा",
        meaning_en="good",
        pos="adj",
        origin="bodo",
        status="expert",
        verified_by="Linguist Expert",
        db_path=db_file,
    )

    # Add occurrences
    add_occurrence(
        nfc_word,
        source_id=source_id,
        line_no=12,
        context="गाहाम मानसि फैबाय",
        db_path=db_file,
    )

    # Add cultural note
    culture_dir = tmp_path / "culture_notes"
    culture_dir.mkdir()
    (culture_dir / "gaham.md").write_text(
        """---
category: custom
title: Gaham Greetings
source: Cultural Survey
related_words:
  - गाहाम
---
Bodo society mein shubhkaamnayein dene ke liye prayog kiya jata hai.
""",
        encoding="utf-8",
    )
    load_culture_dir(culture_dir, db_path=db_file)

    # Search with Devanagari term
    res = lookup_term(raw_word, db_path=db_file)
    assert len(res["words"]) == 1
    w = res["words"][0]
    assert w["word"] == nfc_word
    assert w["meaning_hi"] == "अच्छा"
    assert w["meaning_en"] == "good"
    assert w["pos"] == "adj"
    assert w["origin"] == "bodo"
    assert w["status"] == "expert"
    assert w["verified_by"] == "Linguist Expert"

    # Verify occurrence snippet
    assert len(w["occurrences"]) == 1
    assert w["occurrences"][0]["title"] == "Bodo Folklore Collection"
    assert "गाहाम मानसि फैबाय" in w["occurrences"][0]["context"]

    # Verify related culture items
    assert len(res["culture_items"]) == 1
    assert res["culture_items"][0]["title"] == "Gaham Greetings"

    # Test CLI output formatting
    exit_code = main([raw_word, "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "गाहाम" in out
    assert "gaham" in out
    assert "अच्छा" in out
    assert "good" in out
    assert "Bodo Folklore Collection" in out
    assert "Gaham Greetings" in out


def test_lookup_max_20_results(tmp_path):
    """Verify lookup returns a maximum of 20 results."""
    db_file = tmp_path / "lookup_limit.sqlite"
    init_db(db_file)

    for i in range(25):
        add_word(f"prefix_word_{i:02d}", db_path=db_file)

    res = lookup_term("prefix_word", db_path=db_file)
    assert len(res["words"]) == 20


def test_lookup_special_character_escaping(tmp_path):
    """Verify SQLite LIKE special characters (%, _) are properly escaped."""
    db_file = tmp_path / "lookup_escape.sqlite"
    init_db(db_file)

    add_word("100%_natural", db_path=db_file)
    add_word("1000_other", db_path=db_file)

    res = lookup_term("100%", db_path=db_file)
    words = [w["word"] for w in res["words"]]
    assert "100%_natural" in words
    assert "1000_other" not in words
