import pytest

from bhasha_lib.culture import load_culture_dir, main, related
from bhasha_lib.db import add_word, init_db


def test_valid_file_loaded_and_searchable(tmp_path):
    """Verify a valid markdown file is loaded and searchable via related()."""
    culture_dir = tmp_path / "culture_data"
    culture_dir.mkdir()

    md_content = """---
category: festival
title: Bwisagu Festival
region: Bodoland
source: Bodoland Tourism Board
related_words:
  - बैसागु
  - basant
---
Bwisagu is celebrated during the advent of the Bodo new year in spring.
Mahilayein Bagurumba dance perform karti hain.
"""
    (culture_dir / "bwisagu.md").write_text(md_content, encoding="utf-8")

    db_file = tmp_path / "culture_test.sqlite"
    init_db(db_file)

    # Pre-populate a related word in dictionary
    add_word("बैसागु", roman="Bwisagu", freq=1, db_path=db_file)

    loaded_ids = load_culture_dir(culture_dir, db_path=db_file)
    assert len(loaded_ids) == 1

    # Search by title
    res_title = related("Bwisagu", db_path=db_file)
    assert len(res_title["culture_items"]) == 1
    assert res_title["culture_items"][0]["title"] == "Bwisagu Festival"
    assert res_title["culture_items"][0]["category"] == "festival"
    # Word match
    assert res_title["word"] is None  # "Bwisagu" was not in words (बैसागु was)

    # Search by description
    res_desc = related("Bagurumba", db_path=db_file)
    assert len(res_desc["culture_items"]) == 1
    assert res_desc["culture_items"][0]["title"] == "Bwisagu Festival"


def test_file_missing_source_rejected(tmp_path):
    """Verify a culture file missing 'source' raises ValueError."""
    culture_dir = tmp_path / "culture_invalid"
    culture_dir.mkdir()

    bad_content = """---
category: dance
title: Incomplete Item
region: Assam
related_words: []
---
This item has no source.
"""
    (culture_dir / "incomplete.md").write_text(bad_content, encoding="utf-8")

    db_file = tmp_path / "culture_bad.sqlite"
    init_db(db_file)

    with pytest.raises(ValueError, match="source"):
        load_culture_dir(culture_dir, db_path=db_file)


def test_loading_same_file_twice_no_duplicate(tmp_path):
    """Verify loading the same file twice does not create duplicate culture items."""
    culture_dir = tmp_path / "culture_dup"
    culture_dir.mkdir()

    content = """---
category: craft
title: Dokhona Weaving
region: Assam
source: Bodo Textile Heritage
related_words:
  - Dokhona
---
Traditional handwoven dress worn by Bodo women.
"""
    (culture_dir / "dokhona.md").write_text(content, encoding="utf-8")

    db_file = tmp_path / "culture_dup.sqlite"
    init_db(db_file)

    first_load = load_culture_dir(culture_dir, db_path=db_file)
    assert len(first_load) == 1

    # Second load of the exact same directory/items
    second_load = load_culture_dir(culture_dir, db_path=db_file)
    assert len(second_load) == 0

    # Ensure only 1 entry exists in database
    res = related("Dokhona", db_path=db_file)
    assert len(res["culture_items"]) == 1


def test_devanagari_search_term_works(tmp_path):
    """Verify searching with a Devanagari term matches items and dictionary words."""
    culture_dir = tmp_path / "culture_dev"
    culture_dir.mkdir()

    content = """---
category: music
title: Kham Instrument
region: Bodoland
source: Traditional Musical Instruments
related_words:
  - बाम
  - खाम
---
खाम Bodo lok-sangeet ka ek pramukh dhol (drum) hai.
"""
    (culture_dir / "kham.md").write_text(content, encoding="utf-8")

    db_file = tmp_path / "culture_dev.sqlite"
    init_db(db_file)

    add_word(
        "खाम", roman="kham", meaning_en="traditional drum", freq=2, db_path=db_file
    )

    load_culture_dir(culture_dir, db_path=db_file)

    # Search with Devanagari term
    res = related("खाम", db_path=db_file)
    assert len(res["culture_items"]) == 1
    assert res["culture_items"][0]["title"] == "Kham Instrument"

    # Word match found in dictionary
    assert res["word"] is not None
    assert res["word"]["word"] == "खाम"
    assert res["word"]["meaning_en"] == "traditional drum"


def test_culture_cli(tmp_path):
    """Verify CLI entry point python -m bhasha_lib.culture."""
    culture_dir = tmp_path / "culture_cli"
    culture_dir.mkdir()

    content = """---
category: dance
title: Kherai
region: Assam
source: Bodo Religious Traditions
related_words: []
---
Kherai is a sacred religious dance performed during Kherai puja.
"""
    (culture_dir / "kherai.md").write_text(content, encoding="utf-8")

    db_file = tmp_path / "culture_cli.sqlite"

    exit_code = main([str(culture_dir), "--db", str(db_file)])
    assert exit_code == 0

    res = related("Kherai", db_path=db_file)
    assert len(res["culture_items"]) == 1
