"""Tests for ethical consent register CLI and verification."""

from __future__ import annotations

import csv
import datetime

import pytest

from bhasha_lib.consent import (
    REGISTER_COLUMNS,
    add_consent,
    check_consents,
    compute_sha256,
    main,
    verify_consent_document,
)
from bhasha_lib.culture import load_culture_dir, validate_folk_song_header
from bhasha_lib.db import init_db


def test_consent_add_creates_header_and_row(tmp_path):
    """Verify add creates register.csv on first use with correct header and row."""
    doc_file = tmp_path / "form.pdf"
    doc_file.write_bytes(b"%PDF-1.4 sample consent form data")

    reg_file = tmp_path / "consents" / "register.csv"

    # Add row
    row = add_consent(
        file_path=doc_file,
        contributor="Field Collector",
        permission_type="written",
        date_str="2026-01-15",
        scope="Archive documentation and preservation",
        register_path=reg_file,
    )

    assert reg_file.is_file()
    assert row["consent_id"] == "1"
    assert row["sha256"] == compute_sha256(doc_file)
    assert row["contributor"] == "Field Collector"
    assert row["permission_type"] == "written"
    assert row["date"] == "2026-01-15"
    assert row["scope"] == "Archive documentation and preservation"

    # Verify CSV content and header
    with open(reg_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        data_row = next(reader)

    assert header == REGISTER_COLUMNS
    assert data_row[0] == "1"
    assert data_row[2] == compute_sha256(doc_file)

    # Add second row to test sequential ID
    doc_file2 = tmp_path / "audio.wav"
    doc_file2.write_bytes(b"RIFF sample audio")
    row2 = add_consent(
        file_path=doc_file2,
        contributor="Archive Contributor",
        permission_type="recorded",
        date_str="2026-02-01",
        scope="Academic research",
        register_path=reg_file,
    )
    assert row2["consent_id"] == "2"


def test_consent_add_via_cli(tmp_path, capsys):
    """Verify CLI add command works and reports success."""
    doc_file = tmp_path / "doc.pdf"
    doc_file.write_bytes(b"sample bytes")
    reg_file = tmp_path / "reg.csv"

    exit_code = main(
        [
            "add",
            "--file",
            str(doc_file),
            "--contributor",
            "Collector",
            "--permission-type",
            "public_domain",
            "--date",
            "2026-01-01",
            "--scope",
            "General usage",
            "--register",
            str(reg_file),
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Added consent record ID 1" in out


def test_consent_add_refusals(tmp_path):
    """Verify add refuses when file is missing, args are empty, or date is invalid."""
    reg_file = tmp_path / "reg.csv"
    valid_file = tmp_path / "ok.pdf"
    valid_file.write_bytes(b"content")

    # 1. Non-existent file
    with pytest.raises(FileNotFoundError, match="File does not exist"):
        add_consent(
            file_path=tmp_path / "ghost.pdf",
            contributor="Collector",
            permission_type="written",
            date_str="2026-01-01",
            scope="Scope",
            register_path=reg_file,
        )

    # 2. Empty file path
    with pytest.raises(ValueError, match="File path cannot be empty"):
        add_consent(
            file_path="",
            contributor="Collector",
            permission_type="written",
            date_str="2026-01-01",
            scope="Scope",
            register_path=reg_file,
        )

    # 3. Empty contributor
    with pytest.raises(ValueError, match="Contributor name cannot be empty"):
        add_consent(
            file_path=valid_file,
            contributor="   ",
            permission_type="written",
            date_str="2026-01-01",
            scope="Scope",
            register_path=reg_file,
        )

    # 4. Invalid permission_type
    with pytest.raises(ValueError, match="Invalid permission_type"):
        add_consent(
            file_path=valid_file,
            contributor="Collector",
            permission_type="unauthorized",
            date_str="2026-01-01",
            scope="Scope",
            register_path=reg_file,
        )

    # 5. Invalid date format
    with pytest.raises(ValueError, match="Invalid date format"):
        add_consent(
            file_path=valid_file,
            contributor="Collector",
            permission_type="written",
            date_str="not-a-date",
            scope="Scope",
            register_path=reg_file,
        )

    # 6. Future date
    future_date = (
        datetime.date.today() + datetime.timedelta(days=10)
    ).strftime("%Y-%m-%d")
    with pytest.raises(ValueError, match="Date cannot be in the future"):
        add_consent(
            file_path=valid_file,
            contributor="Collector",
            permission_type="written",
            date_str=future_date,
            scope="Scope",
            register_path=reg_file,
        )

    # 7. Empty scope
    with pytest.raises(ValueError, match="Scope cannot be empty"):
        add_consent(
            file_path=valid_file,
            contributor="Collector",
            permission_type="written",
            date_str="2026-01-01",
            scope="   ",
            register_path=reg_file,
        )


def test_consent_check_passes_on_valid_files(tmp_path, capsys):
    """Verify check passes when all registered files exist with matching hashes."""
    doc_file = tmp_path / "valid.pdf"
    doc_file.write_bytes(b"valid consent form data")
    reg_file = tmp_path / "reg.csv"

    add_consent(
        file_path=doc_file,
        contributor="Field Collector",
        permission_type="written",
        date_str="2026-01-01",
        scope="Educational use",
        register_path=reg_file,
    )

    exit_code, results = check_consents(register_path=reg_file)
    assert exit_code == 0
    assert len(results) == 1
    assert results[0]["status"] == "OK"

    # Also test check via CLI
    cli_code = main(["check", "--register", str(reg_file)])
    assert cli_code == 0
    out = capsys.readouterr().out
    assert "[OK]" in out


def test_consent_check_detects_mismatch_after_editing_file(tmp_path, capsys):
    """Verify check detects mismatch after editing a registered file."""
    doc_file = tmp_path / "signed.pdf"
    doc_file.write_bytes(b"original consent text")
    reg_file = tmp_path / "reg.csv"

    add_consent(
        file_path=doc_file,
        contributor="Field Collector",
        permission_type="written",
        date_str="2026-01-01",
        scope="Archival copy",
        register_path=reg_file,
    )

    # Edit the file
    doc_file.write_bytes(b"edited and altered content")

    # Check function returns 1 and status MISMATCH
    exit_code, results = check_consents(register_path=reg_file)
    assert exit_code == 1
    assert len(results) == 1
    assert results[0]["status"] == "MISMATCH"

    # CLI check command returns 1 and prints [MISMATCH]
    cli_code = main(["check", "--register", str(reg_file)])
    assert cli_code == 1
    err_out = capsys.readouterr().err
    assert "[MISMATCH]" in err_out


def test_consent_check_detects_missing_file(tmp_path, capsys):
    """Verify check reports missing file when file is deleted."""
    doc_file = tmp_path / "deleted.pdf"
    doc_file.write_bytes(b"temporary")
    reg_file = tmp_path / "reg.csv"

    add_consent(
        file_path=doc_file,
        contributor="Collector",
        permission_type="written",
        date_str="2026-01-01",
        scope="Scope",
        register_path=reg_file,
    )
    doc_file.unlink()

    exit_code, results = check_consents(register_path=reg_file)
    assert exit_code == 1
    assert results[0]["status"] == "MISSING"

    cli_code = main(["check", "--register", str(reg_file)])
    assert cli_code == 1
    err_out = capsys.readouterr().err
    assert "[MISSING]" in err_out


def test_consent_list_hides_names_by_default(tmp_path, capsys):
    """Verify list hides contributor names unless --show-names is given."""
    doc_file = tmp_path / "consent.pdf"
    doc_file.write_bytes(b"content")
    reg_file = tmp_path / "reg.csv"

    secret_name = "Confidential Elder Name"
    add_consent(
        file_path=doc_file,
        contributor=secret_name,
        permission_type="written",
        date_str="2026-01-01",
        scope="Bodo cultural archive",
        register_path=reg_file,
    )

    # 1. Default list (hide names)
    capsys.readouterr()
    exit_code = main(["list", "--register", str(reg_file)])
    assert exit_code == 0
    out_default = capsys.readouterr().out
    assert secret_name not in out_default
    assert "consent.pdf" in out_default
    assert "Bodo cultural archive" in out_default

    # 2. list with --show-names
    exit_code = main(["list", "--show-names", "--register", str(reg_file)])
    assert exit_code == 0
    out_names = capsys.readouterr().out
    assert secret_name in out_names


def test_culture_guard_rejects_unregistered_document(tmp_path):
    """Verify folk guard rejects notes whose consent_document is not in register."""
    consent_file = tmp_path / "unregistered_doc.pdf"
    consent_file.write_bytes(b"valid pdf content")

    reg_file = tmp_path / "empty_register.csv"
    reg_file.write_text("consent_id,file,sha256,contributor,permission_type,date,scope\n")

    header = {
        "category": "folk_song",
        "title": "Unregistered Song",
        "source": "Source Archive",
        "consent_document": consent_file.as_posix(),
        "contributor": "Collector",
        "permission_type": "written",
        "permission_date": "2026-01-01",
        "source_recording": "Audio cassette from 1995 field trip",
    }

    failures = validate_folk_song_header(
        header, file_path=tmp_path / "song.md", register_path=reg_file
    )
    assert any("not registered in consent register" in f for f in failures)

    # Verify load_culture_dir rejects it
    culture_dir = tmp_path / "folk_songs"
    culture_dir.mkdir()
    (culture_dir / "song.md").write_text(
        f"""---
category: folk_song
title: Unregistered Song
source: Source Archive
consent_document: {consent_file.as_posix()}
contributor: Collector
permission_type: written
permission_date: 2026-01-01
source_recording: Audio cassette from 1995 field trip
---
Song body text.
""",
        encoding="utf-8",
    )

    db_file = tmp_path / "db.sqlite"
    init_db(db_file)
    res = load_culture_dir(culture_dir, db_path=db_file, register_path=reg_file)
    assert res.summary["inserted"] == 0


def test_culture_guard_rejects_hash_mismatch(tmp_path):
    """Verify folk guard rejects notes whose consent_document hash mismatches."""
    consent_file = tmp_path / "signed_doc.pdf"
    consent_file.write_bytes(b"initial valid content")

    reg_file = tmp_path / "register.csv"
    add_consent(
        file_path=consent_file,
        contributor="Field Worker",
        permission_type="written",
        date_str="2026-01-01",
        scope="Tribal folklore project",
        register_path=reg_file,
    )

    # Tamper with file
    consent_file.write_bytes(b"altered content after registration")

    culture_dir = tmp_path / "folk_songs"
    culture_dir.mkdir()
    (culture_dir / "tampered_song.md").write_text(
        f"""---
category: folk_song
title: Tampered Song
source: Source Archive
consent_document: {consent_file.as_posix()}
contributor: Field Worker
permission_type: written
permission_date: 2026-01-01
source_recording: Audio cassette from 1995 field trip
---
Song body text.
""",
        encoding="utf-8",
    )

    db_file = tmp_path / "db_mismatch.sqlite"
    init_db(db_file)
    res = load_culture_dir(culture_dir, db_path=db_file, register_path=reg_file)
    assert res.summary["inserted"] == 0


def test_verify_consent_document_helper(tmp_path):
    """Verify verify_consent_document helper returns correct boolean and messages."""
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"original data")
    reg = tmp_path / "register.csv"

    # Non-existent register
    ok, err = verify_consent_document(doc, register_path=tmp_path / "missing.csv")
    assert not ok
    assert "Consent register not found" in err

    # Add to register
    add_consent(
        file_path=doc,
        contributor="Collector",
        permission_type="written",
        date_str="2026-01-01",
        scope="Scope",
        register_path=reg,
    )

    # Valid check
    ok, err = verify_consent_document(doc, register_path=reg)
    assert ok
    assert err == ""

    # Tamper with file
    doc.write_bytes(b"tampered")
    ok, err = verify_consent_document(doc, register_path=reg)
    assert not ok
    assert "SHA-256 does not match" in err
