from pathlib import Path

import pytest

from bhasha_lib.archive import (
    ARCHIVE_CATEGORIES,
    get_archive_path,
    list_archive_files,
    verify_archive_structure,
)


def test_archive_folders_exist():
    root = Path(__file__).resolve().parent.parent
    base_data = root / "data" / "archive" / "bodo"
    assert base_data.is_dir()

    expected_categories = {"books", "datasets", "history", "culture", "folk_songs"}
    assert set(ARCHIVE_CATEGORIES) == expected_categories

    for category in expected_categories:
        cat_dir = base_data / category
        assert cat_dir.is_dir(), f"Expected directory {cat_dir} does not exist"


def test_verify_archive_structure():
    root = Path(__file__).resolve().parent.parent
    base_data = root / "data" / "archive" / "bodo"
    status = verify_archive_structure(base_data)
    assert all(status.values())


def test_get_archive_path_invalid():
    with pytest.raises(ValueError):
        get_archive_path("unsupported_category")


def test_list_archive_files():
    root = Path(__file__).resolve().parent.parent
    base_data = root / "data" / "archive" / "bodo"
    # When include_gitkeep=False, empty directories return []
    files = list_archive_files("books", base_dir=base_data, include_gitkeep=False)
    assert isinstance(files, list)

    # When include_gitkeep=True, .gitkeep should be listed
    files_with_keep = list_archive_files(
        "books", base_dir=base_data, include_gitkeep=True
    )
    assert any(f.name == ".gitkeep" for f in files_with_keep)
