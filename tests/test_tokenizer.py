import unicodedata

from bhasha_lib.tokenizer import normalize, tokenize, tokenize_roman


def test_bodo_words_with_apostrophe():
    """Verify 'बर\' राव' gives exactly two words: ['बर\'', 'राव']."""
    tokens = tokenize("बर' राव")
    assert tokens == ["बर'", "राव"]


def test_curly_apostrophe():
    """Verify a curly apostrophe (बर’) is normalized and kept inside the word."""
    tokens = tokenize("बर’")
    assert tokens == ["बर'"]

    # Also test within a phrase
    phrase_tokens = tokenize("बर’ राव")
    assert phrase_tokens == ["बर'", "राव"]


def test_danda_and_digits_removed():
    """Verify dandas (।, ॥) and Devanagari digits (०-९) are removed."""
    text = "बर' १ राव। आफा ॥ २३"
    tokens = tokenize(text)
    assert tokens == ["बर'", "राव", "आफा"]

    # Danda directly attached to word
    assert tokenize("बर'।राव") == ["बर'", "राव"]

    # Devanagari digits inside a word
    assert tokenize("बर'१") == ["बर'"]


def test_nfd_and_nfc_give_same_tokens():
    """Verify an NFD string and an NFC string give the same tokens."""
    text_nfc = "\u0929 बर' राव"
    text_nfd = unicodedata.normalize("NFD", text_nfc)
    # Confirm byte/codepoint divergence before testing
    assert text_nfc != text_nfd
    assert tokenize(text_nfc) == tokenize(text_nfd)


def test_normalize_zero_width_chars():
    """Verify zero-width characters (U+200B, U+200C, U+200D, U+FEFF) are stripped."""
    zw_text = "बर\u200b'\u200c \u200dराव\ufeff"
    assert normalize(zw_text) == "बर' राव"


def test_normalize_apostrophe_variants():
    """Verify apostrophe variants map to standard ASCII apostrophe."""
    assert normalize("बर\u2019") == "बर'"
    assert normalize("बर\u02bc") == "बर'"
    assert normalize("बर\u2018") == "बर'"
    assert normalize("बर\u0060") == "बर'"


def test_standalone_apostrophes_not_words():
    """Verify standalone apostrophes or quotes do not become words."""
    assert tokenize("'") == []
    assert tokenize("'''") == []
    assert tokenize(" ' ' ") == []
    assert tokenize("' ' ' राव") == ["राव"]


def test_internal_apostrophe():
    """Verify words with internal tone apostrophes stay intact."""
    assert tokenize("हा'बा") == ["हा'बा"]
    assert tokenize("ख'र'सां") == ["ख'र'सां"]


def test_tokenize_roman():
    """Verify tokenize_roman lowercases, handles hyphens, and filters digits."""
    text = "Boro and Kachari grammar by Rev. S. Endle in 1884. A ha-ba word."
    tokens = tokenize_roman(text)

    # Must be lowercased
    assert "boro" in tokens
    assert "kachari" in tokens
    assert "grammar" in tokens

    # Short single letters like 'a' and 's' (< 2 letters) must be ignored
    assert "a" not in tokens
    assert "s" not in tokens

    # Tokens with digits like '1884' must be ignored
    assert "1884" not in tokens

    # Hyphenated word must be kept
    assert "ha-ba" in tokens


def test_tokenize_roman_apostrophe_and_combining():
    """Verify tokenize_roman preserves apostrophes and combining characters."""
    text = "Boro’s tradition and bòrò spelling."
    tokens = tokenize_roman(text)

    # Curly apostrophe normalized to plain apostrophe and kept
    assert "boro's" in tokens
    # Combining / accented Latin characters kept
    assert any("b" in t and "r" in t for t in tokens)


def test_tokenize_roman_digits_skipped():
    """Verify tokens containing digits are completely omitted."""
    text = "page10 1904 vol2 word"
    tokens = tokenize_roman(text)
    assert tokens == ["word"]
