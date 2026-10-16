import unicodedata

import pytest

from bhasha_lib.db import (
    add_culture_item,
    add_occurrence,
    add_source,
    add_word,
    init_db,
    search_word,
)


def test_create_db_insert_and_search(tmp_path):
    db_file = tmp_path / "lexicon.sqlite"
    init_db(db_file)

    source_id = add_source(
        title="Bodo Grammar & Usage",
        type="book",
        author="Bodo Sahitya Sabha",
        year=2020,
        license="CC-BY-4.0",
        contributor="Archive Contributor",
        url="https://example.org/bodo-grammar",
        file_path="data/archive/bodo/books/grammar.pdf",
        db_path=db_file,
    )
    assert isinstance(source_id, int)
    assert source_id > 0

    add_word(
        word="बर'",
        roman="Boro",
        meaning_hi="बोडो भाषा/लोग",
        meaning_en="Bodo language or ethnic group",
        pos="noun",
        tone="high",
        dialect="Standard",
        freq=1,
        db_path=db_file,
    )

    result = search_word("बर'", db_path=db_file)
    assert result is not None
    assert result["word"] == "बर'"
    assert result["roman"] == "Boro"
    assert result["meaning_en"] == "Bodo language or ethnic group"
    assert result["freq"] == 1


def test_empty_license_raises_value_error(tmp_path):
    db_file = tmp_path / "lexicon.sqlite"
    init_db(db_file)

    with pytest.raises(ValueError, match="license"):
        add_source(title="Untitled", license="", db_path=db_file)

    with pytest.raises(ValueError, match="license"):
        add_source(title="Untitled", license="   ", db_path=db_file)

    with pytest.raises(ValueError, match="license"):
        add_source(title="Untitled", license=None, db_path=db_file)


def test_adding_same_word_twice_increases_freq(tmp_path):
    db_file = tmp_path / "lexicon.sqlite"
    init_db(db_file)

    add_word("अंखा", meaning_en="star", freq=1, db_path=db_file)
    res1 = search_word("अंखा", db_path=db_file)
    assert res1 is not None
    assert res1["freq"] == 1

    # Adding the word again must increase freq
    add_word("अंखा", freq=1, db_path=db_file)
    res2 = search_word("अंखा", db_path=db_file)
    assert res2 is not None
    assert res2["freq"] == 2

    # Adding with a specific frequency increment
    add_word("अंखा", freq=3, db_path=db_file)
    res3 = search_word("अंखा", db_path=db_file)
    assert res3 is not None
    assert res3["freq"] == 5


def test_nfc_normalization(tmp_path):
    db_file = tmp_path / "lexicon.sqlite"
    init_db(db_file)

    # Decomposed form (NFD)
    word_nfd = unicodedata.normalize("NFD", "बड़ो")
    word_nfc = unicodedata.normalize("NFC", "बड़ो")

    add_word(word_nfd, meaning_en="Bodo", db_path=db_file)

    # Search with composed (NFC)
    found_nfc = search_word(word_nfc, db_path=db_file)
    assert found_nfc is not None
    assert found_nfc["word"] == word_nfc

    # Search with decomposed (NFD)
    found_nfd = search_word(word_nfd, db_path=db_file)
    assert found_nfd is not None
    assert found_nfd["word"] == word_nfc


def test_occurrences_and_culture_items(tmp_path):
    db_file = tmp_path / "lexicon.sqlite"
    init_db(db_file)

    s_id = add_source(
        title="Folk Songs of Bodos", license="Public Domain", db_path=db_file
    )
    add_word("बैसागु", meaning_en="Bwisagu Spring Festival", db_path=db_file)

    add_occurrence(
        word="बैसागु",
        source_id=s_id,
        line_no=42,
        context="बैसागु सान बेलाव...",
        db_path=db_file,
    )

    c_id = add_culture_item(
        category="festivals",
        title="Bwisagu",
        description="Spring festival celebrated during Bwisagu month",
        region="Bodoland",
        related_words="बैसागु,बागुरुम्बा",
        source_id=s_id,
        media_path="data/archive/bodo/culture/bwisagu.jpg",
        db_path=db_file,
    )
    assert isinstance(c_id, int)
    assert c_id > 0


def test_search_word_not_found(tmp_path):
    db_file = tmp_path / "lexicon.sqlite"
    init_db(db_file)

    assert search_word("nonexistent_word", db_path=db_file) is None
    assert search_word("", db_path=db_file) is None
