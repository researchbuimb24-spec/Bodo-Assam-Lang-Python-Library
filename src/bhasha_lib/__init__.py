"""bhasha_lib - Python library for Indian language processing and linguistic data."""

from __future__ import annotations

from typing import Any

from bhasha_lib.archive import (
    ARCHIVE_CATEGORIES,
    get_archive_base_dir,
    get_archive_path,
    list_archive_files,
    verify_archive_structure,
)
from bhasha_lib.config import (
    LanguageConfig,
    find_default_config,
    get_bodo_config,
    load_config,
)
from bhasha_lib.consent import (
    ConsentError,
    ConsentRecord,
    ConsentStatus,
    validate_consent_dict,
)
from bhasha_lib.db import (
    DEFAULT_DB_PATH,
    add_culture_item,
    add_occurrence,
    add_source,
    add_word,
    init_db,
    search_word,
    update_word_meaning,
)
from bhasha_lib.english import BODO_PROTECTED_WORDS, is_english_word
from bhasha_lib.tokenizer import normalize, tokenize, tokenize_roman
from bhasha_lib.unicode import (
    calculate_coverage,
    filter_devanagari,
    is_char_in_range,
    is_devanagari,
    parse_unicode_range,
)

__version__ = "0.1.0"


def __getattr__(name: str) -> Any:
    """Lazy-load modules to avoid runpy warnings when running modules with -m."""
    if name == "extract_file":
        from bhasha_lib.extract import extract_file

        return extract_file
    if name == "load_aksharantar":
        from bhasha_lib.loaders.aksharantar import load_aksharantar

        return load_aksharantar
    if name == "load_culture_dir":
        from bhasha_lib.culture import load_culture_dir

        return load_culture_dir
    if name == "related":
        from bhasha_lib.culture import related

        return related
    if name == "import_sources_csv":
        from bhasha_lib.sources_import import import_sources_csv

        return import_sources_csv
    if name == "load_historical_book":
        from bhasha_lib.loaders.archive_org import load_historical_book

        return load_historical_book
    if name == "export_for_review":
        from bhasha_lib.meanings import export_for_review

        return export_for_review
    if name == "export_meanings_csv":
        from bhasha_lib.meanings import export_meanings_csv

        return export_meanings_csv
    if name == "import_meanings":
        from bhasha_lib.meanings import import_meanings

        return import_meanings
    if name == "import_meanings_csv":
        from bhasha_lib.meanings import import_meanings_csv

        return import_meanings_csv
    if name == "bootstrap_seed_meanings":
        from bhasha_lib.meanings import bootstrap_seed_meanings

        return bootstrap_seed_meanings
    if name == "get_meanings_stats":
        from bhasha_lib.meanings import get_meanings_stats

        return get_meanings_stats
    if name == "load_folk_song_file":
        from bhasha_lib.folk_songs import load_folk_song_file

        return load_folk_song_file
    if name == "load_folk_songs_dir":
        from bhasha_lib.folk_songs import load_folk_songs_dir

        return load_folk_songs_dir
    if name == "verify_folk_songs_dir":
        from bhasha_lib.folk_songs import verify_folk_songs_dir

        return verify_folk_songs_dir
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ARCHIVE_CATEGORIES",
    "BODO_PROTECTED_WORDS",
    "ConsentError",
    "ConsentRecord",
    "ConsentStatus",
    "DEFAULT_DB_PATH",
    "LanguageConfig",
    "__version__",
    "add_culture_item",
    "add_occurrence",
    "add_source",
    "add_word",
    "bootstrap_seed_meanings",
    "calculate_coverage",
    "export_for_review",
    "export_meanings_csv",
    "extract_file",
    "filter_devanagari",
    "find_default_config",
    "get_archive_base_dir",
    "get_archive_path",
    "get_bodo_config",
    "get_meanings_stats",
    "import_meanings",
    "import_meanings_csv",
    "import_sources_csv",
    "init_db",
    "is_char_in_range",
    "is_devanagari",
    "is_english_word",
    "list_archive_files",
    "load_aksharantar",
    "load_config",
    "load_culture_dir",
    "load_folk_song_file",
    "load_folk_songs_dir",
    "load_historical_book",
    "normalize",
    "parse_unicode_range",
    "related",
    "search_word",
    "tokenize",
    "tokenize_roman",
    "update_word_meaning",
    "validate_consent_dict",
    "verify_archive_structure",
    "verify_folk_songs_dir",
]
