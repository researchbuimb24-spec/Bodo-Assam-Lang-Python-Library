import pytest

from bhasha_lib.unicode import (
    calculate_coverage,
    filter_devanagari,
    is_char_in_range,
    is_devanagari,
    parse_unicode_range,
)


def test_parse_unicode_range():
    start, end = parse_unicode_range("0900-097F")
    assert start == 0x0900
    assert end == 0x097F


def test_parse_invalid_unicode_range():
    with pytest.raises(ValueError):
        parse_unicode_range("invalid_range")


def test_is_char_in_range():
    # 'क' is U+0915
    assert is_char_in_range("क", "0900-097F")
    # 'A' is U+0041
    assert not is_char_in_range("A", "0900-097F")


def test_is_devanagari():
    assert is_devanagari("बर'")
    assert is_devanagari("बर' राव")
    assert not is_devanagari("Bodo language")
    assert not is_devanagari("")


def test_filter_devanagari():
    text = "Bodo बर' राव 123"
    assert filter_devanagari(text) == " बर' राव "


def test_calculate_coverage():
    coverage_pure = calculate_coverage("बर' राव")
    assert coverage_pure > 0.8
    assert calculate_coverage("English only") == 0.0
