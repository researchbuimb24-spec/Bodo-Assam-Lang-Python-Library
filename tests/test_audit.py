from pathlib import Path

from bhasha_lib.audit import audit_culture_and_history, main
from bhasha_lib.db import add_culture_item, add_source, init_db


def test_audit_flags_no_file(tmp_path):
    """Verify NO FILE is flagged when DB row has no matching markdown file."""
    db_file = tmp_path / "audit_nofile.sqlite"
    init_db(db_file)
    src_id = add_source(
        title="Valid Historical Book 2026",
        license="CC-BY-4.0",
        db_path=db_file,
    )
    add_culture_item(
        category="dance",
        title="Ghost Dance",
        source_id=src_id,
        db_path=db_file,
    )

    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    res = audit_culture_and_history(db_path=db_file, dir_path=empty_dir)
    assert len(res["rows"]) == 1
    row = res["rows"][0]
    assert "NO FILE" in row["flags"]
    assert row["file_path"] == "NO FILE"
    assert res["summary"]["flag_counts"]["NO FILE"] == 1


def test_audit_flags_no_source(tmp_path):
    """Verify NO SOURCE is flagged when source title is empty or < 15 chars."""
    db_file = tmp_path / "audit_nosource.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "culture_dir"
    dir_path.mkdir()

    # Create matching markdown file
    (dir_path / "item.md").write_text(
        """---
category: craft
title: Handloom Craft
source: Short Source
related_words: []
---
Craft description.
""",
        encoding="utf-8",
    )

    src_id = add_source(
        title="Short Source",  # 12 chars < 15
        license="own_words",
        db_path=db_file,
    )
    add_culture_item(
        category="craft",
        title="Handloom Craft",
        source_id=src_id,
        db_path=db_file,
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    assert len(res["rows"]) == 1
    row = res["rows"][0]
    assert "NO SOURCE" in row["flags"]
    assert res["summary"]["flag_counts"]["NO SOURCE"] == 1


def test_audit_flags_vague_source(tmp_path):
    """Verify VAGUE SOURCE is flagged when source is only a site name like Wikipedia."""
    db_file = tmp_path / "audit_vague.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "culture_dir"
    dir_path.mkdir()

    (dir_path / "item.md").write_text(
        """---
category: festival
title: Spring Fest
source: Wikipedia
related_words: []
---
Festival description.
""",
        encoding="utf-8",
    )

    src_id = add_source(
        title="Wikipedia",
        license="CC-BY-SA-4.0",
        db_path=db_file,
    )
    add_culture_item(
        category="festival",
        title="Spring Fest",
        source_id=src_id,
        db_path=db_file,
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    assert len(res["rows"]) == 1
    row = res["rows"][0]
    assert "VAGUE SOURCE" in row["flags"]
    assert res["summary"]["flag_counts"]["VAGUE SOURCE"] == 1


def test_audit_flags_duplicate_title(tmp_path):
    """Verify DUPLICATE TITLE is flagged when title appears in different categories."""
    db_file = tmp_path / "audit_dup.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "culture_dir"
    dir_path.mkdir()

    src_id = add_source(
        title="Comprehensive Folk Tradition Archive",
        license="CC-BY-4.0",
        db_path=db_file,
    )

    (dir_path / "item1.md").write_text(
        """---
category: festival
title: Bwisagu
source: Comprehensive Folk Tradition Archive
related_words: []
---
Festival text.
""",
        encoding="utf-8",
    )
    (dir_path / "item2.md").write_text(
        """---
category: dance
title: Bwisagu
source: Comprehensive Folk Tradition Archive
related_words: []
---
Dance text.
""",
        encoding="utf-8",
    )

    add_culture_item(
        category="festival",
        title="Bwisagu",
        source_id=src_id,
        db_path=db_file,
    )
    add_culture_item(
        category="dance",
        title="Bwisagu",
        source_id=src_id,
        db_path=db_file,
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    assert len(res["rows"]) == 2
    assert all("DUPLICATE TITLE" in r["flags"] for r in res["rows"])
    assert res["summary"]["flag_counts"]["DUPLICATE TITLE"] == 2


def test_audit_flags_verified_without_note(tmp_path):
    """Verify VERIFIED WITHOUT NOTE when verified item lacks verified_by."""
    db_file = tmp_path / "audit_unverified_note.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "culture_dir"
    dir_path.mkdir()

    src_id = add_source(
        title="Assam Cultural Heritage Survey 2026",
        license="CC-BY-4.0",
        db_path=db_file,
    )

    # File 1: verified without verified_by
    (dir_path / "item1.md").write_text(
        """---
category: attire
title: Traditional Dress
source: Assam Cultural Heritage Survey 2026
confidence: verified
related_words: []
---
Dress description.
""",
        encoding="utf-8",
    )

    # File 2: verified WITH verified_by
    (dir_path / "item2.md").write_text(
        """---
category: attire
title: Traditional Turban
source: Assam Cultural Heritage Survey 2026
confidence: verified
verified_by: Cultural Expert
related_words: []
---
Turban description.
""",
        encoding="utf-8",
    )

    add_culture_item(
        category="attire",
        title="Traditional Dress",
        confidence="verified",
        source_id=src_id,
        db_path=db_file,
    )
    add_culture_item(
        category="attire",
        title="Traditional Turban",
        confidence="verified",
        source_id=src_id,
        db_path=db_file,
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    row1 = next(r for r in res["rows"] if r["title"] == "Traditional Dress")
    row2 = next(r for r in res["rows"] if r["title"] == "Traditional Turban")

    assert "VERIFIED WITHOUT NOTE" in row1["flags"]
    assert "VERIFIED WITHOUT NOTE" not in row2["flags"]


def test_audit_clean_item_and_cli(tmp_path, capsys):
    """Verify clean item has no flags and CLI formats output properly."""
    db_file = tmp_path / "audit_clean.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "culture_dir"
    dir_path.mkdir()

    src_id = add_source(
        title="Comprehensive Folk Tradition Archive",
        license="CC-BY-4.0",
        db_path=db_file,
    )

    (dir_path / "kham.md").write_text(
        """---
category: instrument
title: Kham Drum
source: Comprehensive Folk Tradition Archive
confidence: needs_check
related_words: []
---
Kham is a traditional instrument.
""",
        encoding="utf-8",
    )

    add_culture_item(
        category="instrument",
        title="Kham Drum",
        confidence="needs_check",
        source_id=src_id,
        year_start=1800,
        db_path=db_file,
    )

    exit_code = main(["--db", str(db_file), "--dir", str(dir_path)])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Culture & History Notes Audit Table" in out
    assert "Kham Drum" in out
    assert "1800" in out
    assert "needs_check" in out
    assert "Flagged Problems (0):" in out
    assert "Total culture_items rows: 1" in out


def test_audit_never_modifies_db_or_files(tmp_path):
    """Verify audit is completely read-only and never alters database or files."""
    db_file = tmp_path / "audit_readonly.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "culture_dir"
    dir_path.mkdir()

    file_content = """---
category: food
title: Napham
source: Bodo Culinary Heritage 2026
related_words: []
---
Napham is a traditional fermented fish dish.
"""
    file_path = dir_path / "napham.md"
    file_path.write_text(file_content, encoding="utf-8")

    src_id = add_source(
        title="Bodo Culinary Heritage 2026",
        license="CC-BY-4.0",
        db_path=db_file,
    )
    add_culture_item(
        category="food",
        title="Napham",
        source_id=src_id,
        db_path=db_file,
    )

    db_mtime_before = Path(db_file).stat().st_mtime_ns
    file_content_before = file_path.read_text(encoding="utf-8")

    audit_culture_and_history(db_path=db_file, dir_path=dir_path)

    assert Path(db_file).stat().st_mtime_ns == db_mtime_before
    assert file_path.read_text(encoding="utf-8") == file_content_before


def test_audit_flags_source_equals_title(tmp_path):
    """Verify SOURCE EQUALS TITLE is flagged when source equals item title."""
    db_file = tmp_path / "audit_src_eq_title.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "culture_dir"
    dir_path.mkdir()

    (dir_path / "song.md").write_text(
        """---
category: folk_song
title: Habao Fwinailai
source: Habao Fwinailai!
contributor: Bodo Elder
permission_type: written
permission_date: 2026-04-14
---
Short description.
""",
        encoding="utf-8",
    )

    src_id = add_source(
        title="Habao Fwinailai!",
        license="CC-BY-4.0",
        db_path=db_file,
    )
    add_culture_item(
        category="folk_song",
        title="Habao Fwinailai",
        source_id=src_id,
        db_path=db_file,
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    row = res["rows"][0]
    assert "SOURCE EQUALS TITLE" in row["flags"]
    assert res["summary"]["flag_counts"]["SOURCE EQUALS TITLE"] == 1


def test_audit_folk_song_consent_keys_pass_and_fail(tmp_path):
    """Verify folk song with all 3 consent keys passes and missing key fails."""
    db_file = tmp_path / "audit_folk_consent.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "folk_songs"
    dir_path.mkdir()

    # Song 1: Complete consent (contributor, valid permission_type, permission_date)
    (dir_path / "song_valid.md").write_text(
        """---
category: folk_song
title: Valid Song
source: Archive of Bodo Folk Traditions (Vol 1)
contributor: Promod Boro
permission_type: written
permission_date: 2026-01-15
---
Short note.
""",
        encoding="utf-8",
    )

    # Song 2: Missing permission_date and invalid permission_type
    (dir_path / "song_invalid.md").write_text(
        """---
category: folk_song
title: Missing Consent Song
source: Archive of Bodo Folk Traditions (Vol 2)
contributor: Community Elder
permission_type: verbal
---
Short note.
""",
        encoding="utf-8",
    )

    # Song 3: Missing contributor
    (dir_path / "song_no_contrib.md").write_text(
        """---
category: folk_song
title: No Contributor Song
source: Archive of Bodo Folk Traditions (Vol 3)
permission_type: public_domain
permission_date: 2026-01-01
---
Short note.
""",
        encoding="utf-8",
    )

    src_id1 = add_source(
        title="Archive of Bodo Folk Traditions (Vol 1)",
        license="CC-BY-4.0",
        db_path=db_file,
    )
    src_id2 = add_source(
        title="Archive of Bodo Folk Traditions (Vol 2)",
        license="CC-BY-4.0",
        db_path=db_file,
    )
    src_id3 = add_source(
        title="Archive of Bodo Folk Traditions (Vol 3)",
        license="CC-BY-4.0",
        db_path=db_file,
    )

    add_culture_item(
        category="folk_song",
        title="Valid Song",
        source_id=src_id1,
        db_path=db_file,
    )
    add_culture_item(
        category="folk_song",
        title="Missing Consent Song",
        source_id=src_id2,
        db_path=db_file,
    )
    add_culture_item(
        category="folk_song",
        title="No Contributor Song",
        source_id=src_id3,
        db_path=db_file,
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    rows_by_title = {r["title"]: r for r in res["rows"]}

    assert "FOLK SONG WITHOUT CONSENT" not in rows_by_title["Valid Song"]["flags"]
    assert "FOLK SONG WITHOUT CONSENT" in rows_by_title["Missing Consent Song"]["flags"]
    assert "FOLK SONG WITHOUT CONSENT" in rows_by_title["No Contributor Song"]["flags"]


def test_audit_flags_possible_lyrics(tmp_path):
    """Verify POSSIBLE LYRICS flags long descriptions or short rhythmic lines."""
    db_file = tmp_path / "audit_lyrics.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "folk_songs"
    dir_path.mkdir()

    # 4 short lines of similar length in body
    (dir_path / "song_verse.md").write_text(
        """---
category: folk_song
title: Rhythmic Song
source: Field Recording Notes by Bodo Culture Cell
contributor: Field Collector
permission_type: recorded
permission_date: 2026-02-20
---
Line one of the traditional folk verse
Line two of the traditional folk verse
Line three of the traditional folk verse
Line four of the traditional folk verse
""",
        encoding="utf-8",
    )

    # Short prose in body
    (dir_path / "song_prose.md").write_text(
        """---
category: folk_song
title: Prose Song Note
source: Field Recording Notes by Bodo Culture Cell
contributor: Field Collector
permission_type: recorded
permission_date: 2026-02-20
---
This is a standard historical context note about the origins of seasonal singing.
""",
        encoding="utf-8",
    )

    src_id = add_source(
        title="Field Recording Notes by Bodo Culture Cell",
        license="CC-BY-4.0",
        db_path=db_file,
    )
    add_culture_item(
        category="folk_song",
        title="Rhythmic Song",
        source_id=src_id,
        db_path=db_file,
    )
    add_culture_item(
        category="folk_song",
        title="Prose Song Note",
        source_id=src_id,
        db_path=db_file,
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    rows_by_title = {r["title"]: r for r in res["rows"]}

    assert "POSSIBLE LYRICS" in rows_by_title["Rhythmic Song"]["flags"]
    assert "POSSIBLE LYRICS" not in rows_by_title["Prose Song Note"]["flags"]


def test_audit_flags_needs_citation_detail(tmp_path):
    """Verify NEEDS CITATION DETAIL flags generic sites without 2nd source."""
    db_file = tmp_path / "audit_generic_src.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "culture_dir"
    dir_path.mkdir()

    (dir_path / "item1.md").write_text(
        """---
category: festival
title: Fest Wikipedia Only
source: Boro culture (Wikipedia)
---
Fest note.
""",
        encoding="utf-8",
    )
    (dir_path / "item2.md").write_text(
        """---
category: festival
title: Fest Wikipedia And Distinct
source: Boro culture (Wikipedia); Bodoland Tourism (tourism.bodoland.gov.in)
---
Fest note.
""",
        encoding="utf-8",
    )

    src_id1 = add_source(
        title="Boro culture (Wikipedia)",
        license="CC-BY-SA-4.0",
        db_path=db_file,
    )
    src_id2 = add_source(
        title="Boro culture (Wikipedia); Bodoland Tourism (tourism.bodoland.gov.in)",
        license="CC-BY-4.0",
        db_path=db_file,
    )

    add_culture_item(
        category="festival",
        title="Fest Wikipedia Only",
        source_id=src_id1,
        db_path=db_file,
    )
    add_culture_item(
        category="festival",
        title="Fest Wikipedia And Distinct",
        source_id=src_id2,
        db_path=db_file,
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    rows_by_title = {r["title"]: r for r in res["rows"]}

    assert "NEEDS CITATION DETAIL" in rows_by_title["Fest Wikipedia Only"]["flags"]
    fest2_flags = rows_by_title["Fest Wikipedia And Distinct"]["flags"]
    assert "NEEDS CITATION DETAIL" not in fest2_flags


def test_audit_remove_culture_item(tmp_path):
    """Verify remove command deletes DB row on exact confirmation."""
    from bhasha_lib.audit import remove_culture_item
    from bhasha_lib.db import get_connection

    db_file = tmp_path / "audit_remove.sqlite"
    init_db(db_file)
    file_path = tmp_path / "item_to_remove.md"
    file_content = "Markdown content that should remain"
    file_path.write_text(file_content, encoding="utf-8")

    src_id = add_source(
        title="Source Reference 2026", license="CC-BY-4.0", db_path=db_file
    )
    row_id = add_culture_item(
        category="dance",
        title="Item To Delete",
        source_id=src_id,
        db_path=db_file,
    )

    # 1. Abort when title confirmation does not match
    aborted = remove_culture_item(
        item_id=row_id,
        db_path=db_file,
        prompt_input=lambda _: "Wrong Title",
    )
    assert aborted is False

    with get_connection(db_file) as conn:
        q = "SELECT COUNT(*) FROM culture_items WHERE id = ?"
        count = conn.execute(q, (row_id,)).fetchone()[0]
        assert count == 1

    # 2. Succeed when title confirmation matches exactly
    confirmed = remove_culture_item(
        item_id=row_id,
        db_path=db_file,
        prompt_input=lambda _: "Item To Delete",
    )
    assert confirmed is True

    with get_connection(db_file) as conn:
        q = "SELECT COUNT(*) FROM culture_items WHERE id = ?"
        count = conn.execute(q, (row_id,)).fetchone()[0]
        assert count == 0

    # Ensure markdown file is NOT deleted
    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == file_content


def test_audit_exit_code_on_problems(tmp_path):
    """Verify CLI exit code is 1 when problems exist and 0 when clean."""
    db_file = tmp_path / "audit_exitcode.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "culture_dir"
    dir_path.mkdir()

    src_id = add_source(title="Short", license="CC-BY-4.0", db_path=db_file)
    add_culture_item(
        category="dance",
        title="Unmatched Row",
        source_id=src_id,
        db_path=db_file,
    )

    exit_code = main(["--db", str(db_file), "--dir", str(dir_path)])
    assert exit_code == 1


def test_audit_flags_consent_file_missing_and_invalid_date(tmp_path):
    """Verify CONSENT FILE MISSING and FUTURE OR INVALID DATE flags."""
    db_file = tmp_path / "audit_fs_flags.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "folk_songs"
    dir_path.mkdir()

    # Song with missing consent doc and future date
    (dir_path / "song_bad.md").write_text(
        """---
category: folk_song
title: Bad Consent Song
source: Archive of Folk Traditions
consent_document: non_existent_doc.pdf
contributor: Field Collector
permission_type: written
permission_date: 2099-01-01
---
Song description.
""",
        encoding="utf-8",
    )

    # Song with valid existing consent doc and past date
    real_doc = tmp_path / "consent.pdf"
    real_doc.write_bytes(b"dummy consent")

    (dir_path / "song_good.md").write_text(
        f"""---
category: folk_song
title: Good Consent Song
source: Archive of Folk Traditions
consent_document: {real_doc.as_posix()}
contributor: Field Collector
permission_type: written
permission_date: 2026-01-01
---
Song description.
""",
        encoding="utf-8",
    )

    src_id = add_source(
        title="Archive of Folk Traditions", license="CC-BY-4.0", db_path=db_file
    )
    add_culture_item(
        category="folk_song",
        title="Bad Consent Song",
        source_id=src_id,
        db_path=db_file,
    )
    add_culture_item(
        category="folk_song",
        title="Good Consent Song",
        source_id=src_id,
        db_path=db_file,
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    rows_by_title = {r["title"]: r for r in res["rows"]}

    bad_flags = rows_by_title["Bad Consent Song"]["flags"]
    assert "CONSENT FILE MISSING" in bad_flags
    assert "FUTURE OR INVALID DATE" in bad_flags

    good_flags = rows_by_title["Good Consent Song"]["flags"]
    assert "CONSENT FILE MISSING" not in good_flags
    assert "FUTURE OR INVALID DATE" not in good_flags


def test_audit_flags_consent_hash_mismatch(tmp_path):
    """Verify audit flags CONSENT HASH MISMATCH when consent file was modified."""
    from bhasha_lib.consent import add_consent

    db_file = tmp_path / "audit_fs_mismatch.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "archive_folk_songs"
    dir_path.mkdir()

    consent_file = tmp_path / "doc.pdf"
    consent_file.write_bytes(b"initial consent bytes")

    reg_file = tmp_path / "register.csv"
    add_consent(
        file_path=consent_file,
        contributor="Field Collector",
        permission_type="written",
        date_str="2026-01-01",
        scope="Public release",
        register_path=reg_file,
    )

    # Edit the file so its hash changes
    consent_file.write_bytes(b"tampered consent bytes")

    (dir_path / "song.md").write_text(
        f"""---
category: folk_song
title: Modified Song
source: Archive Source Ref
consent_document: {consent_file.as_posix()}
contributor: Field Collector
permission_type: written
permission_date: 2026-01-01
---
Description.
""",
        encoding="utf-8",
    )

    src_id = add_source(
        title="Archive Source Ref", license="CC-BY-4.0", db_path=db_file
    )
    add_culture_item(
        category="folk_song",
        title="Modified Song",
        source_id=src_id,
        db_path=db_file,
    )

    res = audit_culture_and_history(
        db_path=db_file, dir_path=dir_path, register_path=reg_file
    )
    rows_by_title = {r["title"]: r for r in res["rows"]}
    flags = rows_by_title["Modified Song"]["flags"]
    assert "CONSENT HASH MISMATCH" in flags
    assert res["summary"]["flag_counts"]["CONSENT HASH MISMATCH"] == 1


def test_audit_flags_untracked_data_file(tmp_path):
    """Verify UNTRACKED DATA FILE flags unreferenced non-culture files."""
    db_file = tmp_path / "audit_untracked.sqlite"
    init_db(db_file)
    dir_path = tmp_path / "archive_dir"
    dir_path.mkdir()

    # Markdown file not in DB and uncommitted
    (dir_path / "mystery_note.md").write_text(
        """---
category: custom
title: Mystery Note
source: Unknown
---
Mystery text.
""",
        encoding="utf-8",
    )

    res = audit_culture_and_history(db_path=db_file, dir_path=dir_path)
    assert res["summary"]["flag_counts"]["UNTRACKED DATA FILE"] == 1
    untracked_probs = [
        p for p in res["problems"] if p["flag"] == "UNTRACKED DATA FILE"
    ]
    assert len(untracked_probs) == 1
    assert "mystery_note" in untracked_probs[0]["title"]


def test_audit_files_command(tmp_path, capsys):
    """Verify files subcommand lists archive files sorted by mtime."""
    dir_path = tmp_path / "archive"
    dir_path.mkdir()

    f1 = dir_path / "file1.txt"
    f1.write_text("content 1", encoding="utf-8")
    f2 = dir_path / "file2.txt"
    f2.write_text("longer content 2", encoding="utf-8")

    exit_code = main(["files", "--dir", str(dir_path)])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Archive Files (sorted by modified time, newest first):" in out
    assert "file1.txt" in out
    assert "file2.txt" in out
    assert "Total files: 2" in out


