import datetime

import pytest

from bhasha_lib.culture import load_culture_dir
from bhasha_lib.db import get_connection, init_db
from bhasha_lib.newnote import create_new_note, main, make_slug


def test_make_slug():
    assert make_slug("Bagurumba") == "bagurumba"
    assert make_slug("Oma jwng narjwi") == "oma_jwng_narjwi"
    assert make_slug("  Bwisagu Festival!  ") == "bwisagu_festival"
    assert make_slug("") == "untitled"


def test_skeleton_creation(tmp_path):
    """Skeleton creation creates metadata header with empty fields and TODO body."""
    note_path = create_new_note(
        category="dance",
        title="Bagurumba Butterfly",
        out_dir=tmp_path,
    )
    assert note_path == tmp_path / "bagurumba_butterfly.md"
    assert note_path.is_file()

    expected_content = (
        "---\n"
        "category: dance\n"
        "title: Bagurumba Butterfly\n"
        "region:\n"
        "year_start:\n"
        "year_end:\n"
        "source:\n"
        "confidence: needs_check\n"
        "related_words: []\n"
        "---\n"
        "TODO\n"
    )
    assert note_path.read_text(encoding="utf-8") == expected_content

    # CLI creation
    cli_out_dir = tmp_path / "cli_notes"
    code = main(
        [
            "--category",
            "attire",
            "--title",
            "Aronai Scarf",
            "--out",
            str(cli_out_dir),
        ]
    )
    assert code == 0
    cli_file = cli_out_dir / "aronai_scarf.md"
    assert cli_file.is_file()
    assert "TODO" in cli_file.read_text(encoding="utf-8")


def test_no_overwrite(tmp_path):
    """Refuses to overwrite an existing note file in Python and CLI."""
    file_1 = create_new_note("dance", "Bagurumba", tmp_path)
    assert file_1.is_file()

    with pytest.raises(FileExistsError, match="already exists"):
        create_new_note("dance", "Bagurumba", tmp_path)

    # CLI exit code 1 on existing file
    code = main(
        [
            "--category",
            "dance",
            "--title",
            "Bagurumba",
            "--out",
            str(tmp_path),
        ]
    )
    assert code == 1


def test_todo_refused(tmp_path):
    """refuse to load any note whose body contains TODO, naming the file."""
    db_file = tmp_path / "test.sqlite"
    init_db(db_file)

    # Note created by newnote has body TODO
    create_new_note("dance", "Skeleton Dance", tmp_path)

    with pytest.raises(ValueError) as excinfo:
        load_culture_dir(tmp_path, db_path=db_file)
    err_msg = str(excinfo.value)
    assert "skeleton_dance.md" in err_msg
    assert "TODO" in err_msg


def test_empty_source_refused(tmp_path):
    """refuse to load any note whose source is empty, naming the file."""
    db_file = tmp_path / "test.sqlite"
    init_db(db_file)

    note = tmp_path / "empty_source.md"
    note.write_text(
        """---
category: food
title: Narjwi
region: Assam
source:
confidence: needs_check
related_words: []
---
Valid description without any banned tokens.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        load_culture_dir(tmp_path, db_path=db_file)
    err_msg = str(excinfo.value)
    assert "empty_source.md" in err_msg
    assert "source" in err_msg


def test_verified_without_verified_by_refused(tmp_path):
    """refuse confidence: verified without non-empty verified_by and verified_on."""
    db_file = tmp_path / "test.sqlite"
    init_db(db_file)

    # 1. Missing verified_by
    note1 = tmp_path / "no_verifier.md"
    note1.write_text(
        """---
category: festival
title: Festival One
source: Authentic Source
confidence: verified
verified_on: 2026-01-01
---
Valid description text.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc1:
        load_culture_dir(tmp_path, db_path=db_file)
    err_msg1 = str(exc1.value)
    assert "no_verifier.md" in err_msg1
    assert "verified_by" in err_msg1

    note1.unlink()

    # 2. Missing verified_on
    note2 = tmp_path / "no_date.md"
    note2.write_text(
        """---
category: festival
title: Festival Two
source: Authentic Source
confidence: verified
verified_by: Dr. Brahma
---
Valid description text.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc2:
        load_culture_dir(tmp_path, db_path=db_file)
    err_msg2 = str(exc2.value)
    assert "no_date.md" in err_msg2
    assert "verified_on" in err_msg2

    note2.unlink()

    # 3. Future verified_on date
    tomorrow = datetime.date.today() + datetime.timedelta(days=10)
    note3 = tmp_path / "future_date.md"
    note3.write_text(
        f"""---
category: festival
title: Festival Three
source: Authentic Source
confidence: verified
verified_by: Dr. Brahma
verified_on: {tomorrow.isoformat()}
---
Valid description text.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc3:
        load_culture_dir(tmp_path, db_path=db_file)
    err_msg3 = str(exc3.value)
    assert "future_date.md" in err_msg3
    assert "future" in err_msg3


def test_verified_with_both_accepted(tmp_path):
    """verified accepted with verified_by and verified_on; verified_by omitted in DB."""
    db_file = tmp_path / "test.sqlite"
    init_db(db_file)

    note = tmp_path / "accepted_item.md"
    note.write_text(
        """---
category: attire
title: Aronai Scarf
region: Assam
source: Authentic Heritage Documentation
confidence: verified
verified_by: Elder Brahma
verified_on: 2026-05-10
related_words: []
---
Traditional scarf of respect and celebration.
""",
        encoding="utf-8",
    )

    res = load_culture_dir(tmp_path, db_path=db_file)
    assert len(res) == 1

    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM culture_items WHERE title = 'Aronai Scarf'")
        row = cursor.fetchone()
        assert row is not None
        assert row["confidence"] == "verified"
        assert row["verified_on"] == "2026-05-10"

        # verified_by must NEVER be stored in the database
        col_names = [col[0] for col in cursor.description]
        assert "verified_by" not in col_names
