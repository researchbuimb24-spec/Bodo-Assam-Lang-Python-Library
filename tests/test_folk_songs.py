import pytest

from bhasha_lib.consent import (
    ConsentError,
    ConsentRecord,
    ConsentStatus,
    validate_consent_dict,
)
from bhasha_lib.db import get_connection, init_db, search_word
from bhasha_lib.folk_songs import (
    load_folk_song_file,
    load_folk_songs_dir,
    main,
    verify_folk_songs_dir,
)


def test_validate_consent_valid():
    data = {
        "status": "verified_written",
        "performer_name": "Traditional Performer",
        "consent_holder": "Cultural Archivist",
        "document_ref": "docs/consents/001.pdf",
        "permitted_uses": ["preservation", "research"],
    }
    record = validate_consent_dict(data, item_title="Test Song")
    assert isinstance(record, ConsentRecord)
    assert record.is_verified is True
    assert record.status == ConsentStatus.VERIFIED_WRITTEN.value
    assert record.performer_name == "Traditional Performer"


def test_validate_consent_institutional_bss():
    data = {
        "status": "institutional_bss",
        "performer_name": "Bodo Community Elders",
        "consent_holder": "BSS Kokrajhar",
        "institutional_partner": "Bodo Sahitya Sabha",
    }
    record = validate_consent_dict(data, item_title="BSS Song")
    assert record.is_verified is True
    assert record.institutional_partner == "Bodo Sahitya Sabha"


def test_validate_consent_pending_rejected():
    data = {
        "status": "pending",
        "performer_name": "Singer Name",
        "document_ref": "pending.pdf",
    }
    with pytest.raises(ConsentError, match="Consent status is 'pending'"):
        validate_consent_dict(data, item_title="Pending Song")


def test_validate_consent_missing_performer():
    data = {
        "status": "verified_written",
        "document_ref": "docs/form.pdf",
    }
    with pytest.raises(ConsentError, match="'performer_name' is required"):
        validate_consent_dict(data, item_title="No Performer Song")


def test_validate_consent_missing_verification_proof():
    data = {
        "status": "verified_written",
        "performer_name": "Singer",
    }
    with pytest.raises(ConsentError, match="Either 'document_ref' .* must be provided"):
        validate_consent_dict(data, item_title="Unverified Song")


def test_load_folk_song_file_success(tmp_path):
    db_file = tmp_path / "song_test.sqlite"
    init_db(db_file)

    song_file = tmp_path / "bwisagu_song.md"
    song_file.write_text(
        "---\n"
        "title: 'Bwisagu Test Song'\n"
        "category: 'folk_song'\n"
        "genre: 'Bwisagu'\n"
        "region: 'Kokrajhar, Assam'\n"
        "instruments: ['Kham', 'Siphung']\n"
        "consent:\n"
        "  status: 'verified_written'\n"
        "  performer_name: 'Bodo Singer'\n"
        "  consent_holder: 'Archive Project'\n"
        "  document_ref: 'consents/01.pdf'\n"
        "license: 'CC-BY-NC-SA-4.0'\n"
        "lyrics_script: 'devanagari'\n"
        "---\n"
        "बैसागु फैबाय आदा गाहाम फैबाय\n"
        "खाम सिफुं दामनानै\n",
        encoding="utf-8",
    )

    item_id = load_folk_song_file(song_file, db_path=db_file)
    assert item_id > 0

    # Verify culture item inserted
    with get_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT title, category, related_words FROM culture_items WHERE id = ?",
            (item_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Bwisagu Test Song"
        assert row[1] == "folk_song"
        assert "Kham" in row[2]
        assert "Siphung" in row[2]

        # Verify source inserted
        cursor.execute(
            "SELECT type, author, license FROM sources "
            "WHERE title = 'Bwisagu Test Song'"
        )
        s_row = cursor.fetchone()
        assert s_row is not None
        assert s_row[0] == "folk_song"
        assert s_row[1] == "Bodo Singer"
        assert s_row[2] == "CC-BY-NC-SA-4.0"

    # Verify words tokenized from lyrics into lexicon
    w_bwisagu = search_word("बैसागु", db_path=db_file)
    assert w_bwisagu is not None


def test_load_folk_song_unconsented_rejected(tmp_path):
    db_file = tmp_path / "song_reject.sqlite"
    init_db(db_file)

    bad_song = tmp_path / "unconsented_song.md"
    bad_song.write_text(
        "---\n"
        "title: 'Unauthorized Song'\n"
        "category: 'folk_song'\n"
        "genre: 'Folk'\n"
        "lyrics_script: 'devanagari'\n"
        "---\n"
        "Lyrics without consent.\n",
        encoding="utf-8",
    )

    with pytest.raises(ConsentError, match="missing a 'consent' block"):
        load_folk_song_file(bad_song, db_path=db_file)


def test_verify_folk_songs_dir(tmp_path):
    # Create valid song
    valid_song = tmp_path / "valid.md"
    valid_song.write_text(
        "---\n"
        "title: 'Valid'\n"
        "consent:\n"
        "  status: 'verified_written'\n"
        "  performer_name: 'Singer'\n"
        "  document_ref: 'ref.pdf'\n"
        "---\n"
        "Lyrics\n",
        encoding="utf-8",
    )

    # Create pending song
    pending_song = tmp_path / "pending.md"
    pending_song.write_text(
        "---\n"
        "title: 'Pending'\n"
        "consent:\n"
        "  status: 'pending'\n"
        "  performer_name: 'Singer'\n"
        "  document_ref: 'ref.pdf'\n"
        "---\n"
        "Lyrics\n",
        encoding="utf-8",
    )

    # Create invalid song
    invalid_song = tmp_path / "invalid.md"
    invalid_song.write_text(
        "---\ntitle: 'Invalid'\n---\nLyrics\n",
        encoding="utf-8",
    )

    report = verify_folk_songs_dir(tmp_path)
    assert "valid.md" in report["valid"]
    assert "pending.md" in report["pending"]
    assert "invalid.md" in report["invalid"]


def test_load_folk_songs_dir(tmp_path):
    db_file = tmp_path / "dir_test.sqlite"
    init_db(db_file)

    song_dir = tmp_path / "songs"
    song_dir.mkdir()

    s1 = song_dir / "s1.md"
    s1.write_text(
        "---\n"
        "title: 'Song 1'\n"
        "consent:\n"
        "  status: 'institutional_bss'\n"
        "  performer_name: 'Artist'\n"
        "  institutional_partner: 'BSS'\n"
        "---\n"
        "Lyrics 1\n",
        encoding="utf-8",
    )

    loaded = load_folk_songs_dir(song_dir, db_path=db_file)
    assert len(loaded) == 1


def test_folk_songs_cli(tmp_path):
    db_file = tmp_path / "cli_test.sqlite"
    init_db(db_file)

    song_file = tmp_path / "cli_song.md"
    song_file.write_text(
        "---\n"
        "title: 'CLI Song'\n"
        "consent:\n"
        "  status: 'institutional_bss'\n"
        "  performer_name: 'Artist'\n"
        "  institutional_partner: 'BSS'\n"
        "---\n"
        "Lyrics\n",
        encoding="utf-8",
    )

    # CLI verify
    assert main(["verify", str(tmp_path)]) == 0

    # CLI load
    assert main(["load", str(tmp_path), "--db", str(db_file)]) == 0
