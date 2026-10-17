import csv
import json

from bhasha_lib.db import add_source, add_word, init_db
from bhasha_lib.export_verified import EXPORT_COLUMNS, export_verified, main


def test_export_verified_skips_unverified_and_words_without_meaning(tmp_path):
    """Verify only verified words ('community' or 'expert') with meaning are exported.
    """
    db_file = tmp_path / "export_filter.sqlite"
    init_db(db_file)

    # Word 1: community + English meaning -> EXPORT
    add_word(
        "हाग्रा",
        roman="hagra",
        meaning_en="forest",
        origin="bodo",
        status="community",
        verified_by="Contributor 1",
        db_path=db_file,
    )
    # Word 2: expert + Hindi meaning -> EXPORT
    add_word(
        "दै",
        roman="dwi",
        meaning_hi="पानी",
        origin="bodo",
        status="expert",
        verified_by="Expert 1",
        db_path=db_file,
    )
    # Word 3: unverified with meaning -> SKIP (unverified)
    add_word(
        "अखा",
        roman="okha",
        meaning_en="rain",
        origin="bodo",
        status="unverified",
        db_path=db_file,
    )
    # Word 4: community with empty meanings -> SKIP (no meaning)
    add_word(
        "खाम",
        roman="kham",
        meaning_hi="",
        meaning_en="   ",
        origin="bodo",
        status="community",
        verified_by="Contributor 2",
        db_path=db_file,
    )
    # Word 5: expert with None meanings -> SKIP (no meaning)
    add_word(
        "बिलाइ",
        roman="bilai",
        meaning_hi=None,
        meaning_en=None,
        origin="bodo",
        status="expert",
        verified_by="Expert 2",
        db_path=db_file,
    )
    # Word 6: unverified without meaning -> SKIP
    add_word(
        "आफा",
        roman="afa",
        status="unverified",
        db_path=db_file,
    )

    out_dir = tmp_path / "export_output"
    summary = export_verified(out_dir, db_path=db_file)

    assert summary["count"] == 2
    assert summary["origin_counts"] == {"bodo": 2}

    # Verify CSV contents
    csv_file = out_dir / "lexicon_verified.csv"
    assert csv_file.is_file()
    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    words = [r["word"] for r in rows]
    assert words == ["दै", "हाग्रा"]  # Sorted alphabetically
    assert "अखा" not in words
    assert "खाम" not in words
    assert "बिलाइ" not in words
    assert "आफा" not in words


def test_exported_files_do_not_contain_verified_by(tmp_path):
    """Verify privacy requirement: verified_by is omitted from CSV and JSON exports."""
    db_file = tmp_path / "privacy_test.sqlite"
    init_db(db_file)

    add_word(
        "बर'",
        roman="boro",
        meaning_hi="बोडो",
        meaning_en="Bodo people or language",
        origin="bodo",
        status="community",
        verified_by="Confidential Contributor",
        db_path=db_file,
    )

    out_dir = tmp_path / "privacy_export"
    export_verified(out_dir, db_path=db_file)

    csv_file = out_dir / "lexicon_verified.csv"
    json_file = out_dir / "lexicon_verified.json"

    # 1. Check CSV headers and rows
    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == EXPORT_COLUMNS
        assert "verified_by" not in reader.fieldnames
        for row in reader:
            assert "verified_by" not in row
            assert "Confidential Contributor" not in row.values()

    # 2. Check JSON data
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert "verified_by" not in data[0]
    assert "Confidential Contributor" not in str(data[0])


def test_data_license_txt_lists_sources(tmp_path):
    """Verify DATA_LICENSE.txt contains source titles, licenses, and disclaimer."""
    db_file = tmp_path / "license_test.sqlite"
    init_db(db_file)

    add_source(
        title="Kachari Folk Tales",
        license="CC-BY-SA-4.0",
        db_path=db_file,
    )
    add_source(
        title="Historical Grammar Notes",
        license="public_domain",
        db_path=db_file,
    )

    # Add at least one verified word
    add_word(
        "गाहाम",
        meaning_en="good",
        status="community",
        verified_by="Reviewer",
        db_path=db_file,
    )

    out_dir = tmp_path / "license_export"
    export_verified(out_dir, db_path=db_file)

    license_file = out_dir / "DATA_LICENSE.txt"
    assert license_file.is_file()

    content = license_file.read_text(encoding="utf-8")
    assert "Each word list entry comes with the license of its source." in content
    assert "Kachari Folk Tales: CC-BY-SA-4.0" in content
    assert "Historical Grammar Notes: public_domain" in content
    assert "Contributor names are not published." in content


def test_export_verified_cli(tmp_path, capsys):
    """Verify CLI entry point python -m bhasha_lib.export_verified."""
    db_file = tmp_path / "cli_test.sqlite"
    init_db(db_file)

    add_word(
        "दै",
        roman="dwi",
        meaning_en="water",
        origin="bodo",
        status="community",
        verified_by="Volunteer",
        db_path=db_file,
    )
    add_word(
        "पेन",
        roman="pen",
        meaning_en="pen",
        origin="loan",
        status="expert",
        verified_by="Linguist",
        db_path=db_file,
    )

    out_dir = tmp_path / "cli_export"
    exit_code = main([str(out_dir), "--db", str(db_file)])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Exported 2 verified word(s)" in out
    assert "bodo: 1" in out
    assert "loan: 1" in out
    assert (out_dir / "lexicon_verified.csv").exists()
    assert (out_dir / "lexicon_verified.json").exists()
    assert (out_dir / "DATA_LICENSE.txt").exists()
