from bhasha_lib.english import (
    BODO_PROTECTED_WORDS,
    is_english_word,
    load_english_words,
)


def test_bodo_protected_words_contents():
    assert "ang" in BODO_PROTECTED_WORDS
    assert "za" in BODO_PROTECTED_WORDS
    assert "gaham" in BODO_PROTECTED_WORDS
    assert "siphung" in BODO_PROTECTED_WORDS


def test_load_english_words():
    words = load_english_words()
    assert isinstance(words, frozenset)
    assert len(words) > 5000
    assert "grammar" in words
    assert "language" in words
    assert "village" in words


def test_is_english_word_standard():
    assert is_english_word("grammar")
    assert is_english_word("language")
    assert is_english_word("collection")
    assert is_english_word("rhymes")
    assert is_english_word("tales")
    assert is_english_word("tiger")
    assert is_english_word("brother")
    assert is_english_word("yesterday")


def test_is_english_word_inflections():
    # Suffixes: -ed, -ing, -ly, -s, -'s
    assert is_english_word("walked")
    assert is_english_word("running")
    assert is_english_word("clearly")
    assert is_english_word("villages")


def test_is_english_word_bodo_protected():
    # Core Bodo words must NEVER be flagged as English
    assert not is_english_word("ang")
    assert not is_english_word("nwng")
    assert not is_english_word("bi")
    assert not is_english_word("zong")
    assert not is_english_word("za")
    assert not is_english_word("da")
    assert not is_english_word("ha")
    assert not is_english_word("ba")
    assert not is_english_word("bo")
    assert not is_english_word("ma")
    assert not is_english_word("no")
    assert not is_english_word("gaham")
    assert not is_english_word("mosa")
    assert not is_english_word("mosau")
    assert not is_english_word("kham")
    assert not is_english_word("siphung")
    assert not is_english_word("serja")
    assert not is_english_word("bodo")
    assert not is_english_word("boro")
    assert not is_english_word("kachari")


def test_is_english_word_bodo_compounds():
    # Hyphenated agglutinative Bodo words should not be flagged as English
    assert not is_english_word("hd-su-nai-khai")
    assert not is_english_word("man-a")
    assert not is_english_word("a-ba")
    assert not is_english_word("zong-fur")


def test_is_english_word_short_or_empty():
    assert not is_english_word("")
    assert not is_english_word("a")
    assert not is_english_word("   ")
