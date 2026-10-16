from pathlib import Path

import pytest

from bhasha_lib.config import LanguageConfig, get_bodo_config, load_config


def test_bodo_config_file_exists():
    root = Path(__file__).resolve().parent.parent
    bodo_yaml = root / "bodo.yaml"
    assert bodo_yaml.exists(), f"bodo.yaml should exist at {bodo_yaml}"


def test_bodo_config_fields():
    root = Path(__file__).resolve().parent.parent
    config = load_config(root / "bodo.yaml")

    assert config.code == "brx"
    assert config.script == "Devanagari"
    assert config.unicode_range == "0900-097F"
    assert config.tonal is True
    assert config.unicode_start == 0x0900
    assert config.unicode_end == 0x097F


def test_get_bodo_config_default():
    config = get_bodo_config()
    assert config.code == "brx"
    assert config.script == "Devanagari"
    assert config.unicode_range == "0900-097F"
    assert config.tonal is True


def test_language_config_to_dict():
    cfg = LanguageConfig(
        code="brx",
        script="Devanagari",
        unicode_range="0900-097F",
        tonal=True,
        name="Bodo",
    )
    d = cfg.to_dict()
    assert d["code"] == "brx"
    assert d["script"] == "Devanagari"
    assert d["unicode_range"] == "0900-097F"
    assert d["tonal"] is True
    assert d["name"] == "Bodo"


def test_load_nonexistent_config():
    with pytest.raises(FileNotFoundError):
        load_config(Path("nonexistent_path/fake.yaml"))
