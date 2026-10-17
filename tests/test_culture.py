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


def test_culture_default_confidence_is_needs_check(tmp_path):
    """Verify culture file without confidence key defaults to 'needs_check'."""
    culture_dir = tmp_path / "default_conf"
    culture_dir.mkdir()

    content = """---
category: attire
title: Aronai Scarf
region: Bodoland
source: Textile Survey
related_words: []
---
Traditional scarf of honour in Bodo community.
"""
    (culture_dir / "aronai.md").write_text(content, encoding="utf-8")

    db_file = tmp_path / "default_conf.sqlite"
    init_db(db_file)

    load_culture_dir(culture_dir, db_path=db_file)

    res = related("Aronai", db_path=db_file)
    assert len(res["culture_items"]) == 1
    assert res["culture_items"][0]["confidence"] == "needs_check"


def test_culture_explicit_confidence_verified(tmp_path):
    """Verify culture file with confidence: verified is stored as verified."""
    culture_dir = tmp_path / "verified_conf"
    culture_dir.mkdir()

    content = """---
category: festival
title: Bwisagu New Year
region: Assam
confidence: verified
source: Verified Cultural Board
related_words: []
---
Celebrated during Bodo new year.
"""
    (culture_dir / "bwisagu.md").write_text(content, encoding="utf-8")

    db_file = tmp_path / "verified_conf.sqlite"
    init_db(db_file)

    load_culture_dir(culture_dir, db_path=db_file)

    res = related("Bwisagu", db_path=db_file)
    assert len(res["culture_items"]) == 1
    assert res["culture_items"][0]["confidence"] == "verified"


def test_editing_file_and_reloading_updates_without_duplicate(tmp_path):
    """Verify editing a file and reloading updates the row without duplicates."""
    culture_dir = tmp_path / "reload_test"
    culture_dir.mkdir()
    md_file = culture_dir / "item.md"

    md_file.write_text(
        """---
category: history
title: Historical Event
region: Assam
year_start: 1950
confidence: needs_check
source: Initial Source
related_words: []
---
Initial draft description.
""",
        encoding="utf-8",
    )

    db_file = tmp_path / "reload.sqlite"
    init_db(db_file)

    res1 = load_culture_dir(culture_dir, db_path=db_file)
    assert res1.summary["inserted"] == 1
    assert res1.summary["updated"] == 0
    assert res1.summary["unchanged"] == 0

    # Reload without edits -> unchanged
    res2 = load_culture_dir(culture_dir, db_path=db_file)
    assert res2.summary["inserted"] == 0
    assert res2.summary["updated"] == 0
    assert res2.summary["unchanged"] == 1

    # Edit the file: update description, year_end, and confidence
    md_file.write_text(
        """---
category: history
title: Historical Event
region: Assam
year_start: 1950
year_end: 1960
confidence: verified
source: Updated Source
related_words:
  - history
---
Revised and verified description text.
""",
        encoding="utf-8",
    )

    res3 = load_culture_dir(culture_dir, db_path=db_file)
    assert res3.summary["inserted"] == 0
    assert res3.summary["updated"] == 1
    assert res3.summary["unchanged"] == 0

    # Ensure no duplicate row was created in database
    items = related("Historical", db_path=db_file)["culture_items"]
    assert len(items) == 1
    item = items[0]
    assert item["description"] == "Revised and verified description text."
    assert item["year_end"] == 1960
    assert item["confidence"] == "verified"
    assert item["related_words"] == "history"


def test_reset_confidence_sets_all_rows_to_needs_check(tmp_path):
    """Verify reset-confidence command updates all rows to 'needs_check'."""
    culture_dir = tmp_path / "reset_test"
    culture_dir.mkdir()

    (culture_dir / "item1.md").write_text(
        """---
category: dance
title: Dance One
region: Assam
confidence: verified
source: Source 1
related_words: []
---
Description 1
""",
        encoding="utf-8",
    )
    (culture_dir / "item2.md").write_text(
        """---
category: dance
title: Dance Two
region: Assam
confidence: verified
source: Source 2
related_words: []
---
Description 2
""",
        encoding="utf-8",
    )

    db_file = tmp_path / "reset.sqlite"
    init_db(db_file)
    load_culture_dir(culture_dir, db_path=db_file)

    # Verify both are initially 'verified'
    items_before = related("Dance", db_path=db_file)["culture_items"]
    assert len(items_before) == 2
    assert all(i["confidence"] == "verified" for i in items_before)

    # Execute reset-confidence CLI
    exit_code = main(["reset-confidence", "--db", str(db_file)])
    assert exit_code == 0

    # Verify all are now 'needs_check'
    items_after = related("Dance", db_path=db_file)["culture_items"]
    assert len(items_after) == 2
    assert all(i["confidence"] == "needs_check" for i in items_after)


def test_folk_song_without_consent_document_refused(tmp_path, capsys):
    """Verify folk song without consent_document is refused with clear error."""
    culture_dir = tmp_path / "folk_songs"
    culture_dir.mkdir()

    (culture_dir / "song_no_doc.md").write_text(
        """---
category: folk_song
title: Refused Song 1
source: Archive Source Ref
contributor: Field Collector
permission_type: written
permission_date: 2026-03-01
source_recording: Tape collection recorded in village 1998
---
Song description.
""",
        encoding="utf-8",
    )

    db_file = tmp_path / "fs_guard1.sqlite"
    init_db(db_file)

    res = load_culture_dir(culture_dir, db_path=db_file)
    assert res.summary["inserted"] == 0

    out = capsys.readouterr().out
    assert "Refused folk song 'song_no_doc.md'" in out
    assert "Missing required 'consent_document'" in out


def test_folk_song_consent_document_not_existing_refused(tmp_path, capsys):
    """Verify folk song with non-existent consent_document is refused."""
    culture_dir = tmp_path / "folk_songs"
    culture_dir.mkdir()

    (culture_dir / "song_missing_doc.md").write_text(
        """---
category: folk_song
title: Refused Song 2
source: Archive Source Ref
consent_document: non_existent_doc.pdf
contributor: Field Collector
permission_type: written
permission_date: 2026-03-01
source_recording: Tape collection recorded in village 1998
---
Song description.
""",
        encoding="utf-8",
    )

    db_file = tmp_path / "fs_guard2.sqlite"
    init_db(db_file)

    res = load_culture_dir(culture_dir, db_path=db_file)
    assert res.summary["inserted"] == 0

    out = capsys.readouterr().out
    assert "Refused folk song 'song_missing_doc.md'" in out
    assert "does not exist on disk" in out


def test_folk_song_with_all_keys_accepted(tmp_path):
    """Verify folk song with all keys and existing consent file is accepted."""
    culture_dir = tmp_path / "folk_songs"
    culture_dir.mkdir()

    # Create actual consent document on disk
    consent_file = tmp_path / "signed_consent.pdf"
    consent_file.write_bytes(b"%PDF-1.4 dummy consent content")

    (culture_dir / "valid_song.md").write_text(
        f"""---
category: folk_song
title: Accepted Song
source: Archive of Folk Traditions
consent_document: {consent_file.as_posix()}
contributor: Field Collector
permission_type: written
permission_date: 2026-03-01
source_recording: Tape collection recorded in village 1998
---
Song description.
""",
        encoding="utf-8",
    )

    db_file = tmp_path / "fs_guard3.sqlite"
    init_db(db_file)

    res = load_culture_dir(culture_dir, db_path=db_file)
    assert res.summary["inserted"] == 1

    items = related("Accepted Song", db_path=db_file)["culture_items"]
    assert len(items) == 1
    assert items[0]["title"] == "Accepted Song"


