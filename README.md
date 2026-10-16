# bhasha_lib

`bhasha_lib` is an open-source Python library designed to document, process, and preserve endangered and regional languages. It provides standardized tools for managing language configurations, lexicons, script-aware tokenizers, corpus extraction pipelines, and cultural archives.

The first supported language is **Bodo (`brx`)**.

---

## Installation

Install the library in editable mode:

```bash
git clone https://github.com/<YOUR-USERNAME>/bhasha-lib.git
cd bhasha-lib
pip install -e .
```

To install development dependencies (`pytest`, `ruff`):

```bash
pip install -e ".[dev]"
```

---

## Quick Start

### Python API

```python
from bhasha_lib import (
    add_source,
    extract_file,
    init_db,
    load_aksharantar,
    load_culture_dir,
    related,
    tokenize,
    tokenize_roman,
)

# 1. Initialize Database
init_db("data/lexicon.sqlite")

# 2. Add a Source Record
source_id = add_source(
    title="Example Corpus",
    type="book",
    license="public_domain",
    db_path="data/lexicon.sqlite",
)

# 3. Extract Words from Text
# Devanagari script (default)
extract_file(
    "path/to/bodo_text.txt",
    db_path="data/lexicon.sqlite",
    source_id=source_id,
    license="public_domain",
)

# Latin script (for historical books)
extract_file(
    "path/to/latin_text.txt",
    db_path="data/lexicon.sqlite",
    source_id=source_id,
    license="public_domain",
    script="latin",
)

# 4. Load Aksharantar Dataset
load_aksharantar(
    "data/archive/bodo/datasets/brx.zip",
    db_path="data/lexicon.sqlite",
    license="CC0",
)

# 5. Load Culture Markdown Notes
load_culture_dir(
    "data/archive/bodo/culture",
    db_path="data/lexicon.sqlite",
)

# 6. Query Related Terms & Culture Items
res = related("Bagurumba", db_path="data/lexicon.sqlite")
print(res["culture_items"])
```

### Command Line Tools

```bash
# Extract words from text (Devanagari)
python -m bhasha_lib.extract document.txt --source-id 1 --license public_domain

# Extract words from text (Latin script with English marking or filtering)
python -m bhasha_lib.extract latin_book.txt --source-id 2 --license public_domain --script latin --mark-english
python -m bhasha_lib.extract latin_book.txt --source-id 2 --license public_domain --script latin --filter-english

# Ingest historical books directly from archive.org (Anderson 1895, Endle 1884)
python -m bhasha_lib.loaders.archive_org --list
python -m bhasha_lib.loaders.archive_org --book anderson_1895 --db data/lexicon.sqlite

# Load Aksharantar dataset zip directly into database
python -m bhasha_lib.loaders.aksharantar path/to/brx.zip --license "CC0" --db data/lexicon.sqlite

# Ingest culture markdown notes
python -m bhasha_lib.culture data/archive/bodo/culture --db data/lexicon.sqlite

# Import bibliography sources from CSV
python -m bhasha_lib.sources_import sources.csv --db data/lexicon.sqlite
```

---

## Project Structure

```
bhasha-lib/
├── LICENSE                            # MIT License (for CODE only)
├── pyproject.toml                     # Package dependencies and tool settings
├── bodo.yaml                          # Bodo language specification
├── configs/
│   └── bodo.yaml                      # Secondary config reference
├── data/
│   └── archive/
│       └── bodo/
│           ├── culture/               # Cultural markdown drafts (.md tracked)
│           │   ├── bagurumba.md
│           │   ├── bathou.md
│           │   ├── bwisagu.md
│           │   └── kherai.md
│           ├── history/               # Historical notes (.md tracked)
│           ├── books/                 # Raw texts & books (excluded by .gitignore)
│           ├── datasets/              # External dataset archives (excluded by .gitignore)
│           └── folk_songs/            # Folk songs & audio (excluded by .gitignore)
├── src/
│   └── bhasha_lib/
│       ├── __init__.py                # Package exports & lazy loaders
│       ├── archive.py                 # Archive path resolution
│       ├── config.py                  # YAML LanguageConfig loader
│       ├── culture.py                 # Markdown frontmatter parser & related() query
│       ├── db.py                      # SQLite database operations & context manager
│       ├── english.py                 # English detection & Bodo protected vocabulary
│       ├── extract.py                 # Text extraction & frequency pipeline
│       ├── loaders/
│       │   ├── __init__.py
│       │   ├── aksharantar.py         # AI4Bharat Aksharantar zip loader
│       │   └── archive_org.py         # Archive.org historical books loader
│       ├── resources/
│       │   └── english_words.txt      # Curated English vocabulary list
│       ├── py.typed                   # PEP 561 type annotation marker
│       ├── sources_import.py          # CSV bibliography importer
│       ├── tokenizer.py               # Devanagari & Latin tokenizers
│       └── unicode.py                 # Unicode script validation
└── tests/                             # Pytest test suite
```

---

## Data and Licensing

- **Code License**: The codebase is licensed under the **MIT License**.
- **Data License**: Data retains the license of each individual source.
- **Mandatory License Field**: Every source entered into the database (`sources` table) must have a non-empty `license` field. This rule is strictly enforced by the software layer.
- **Excluded Data**: Raw books, dataset archives, audio files, and local database files (`lexicon.sqlite`) are **NOT included in the repository** and are excluded by `.gitignore`.

---

## Where to Get Data

- **AI4Bharat Aksharantar**: Available on Hugging Face at [`ai4bharat/Aksharantar`](https://huggingface.co/datasets/ai4bharat/Aksharantar). Always review its license terms on the dataset page before use (mined data subsets are released under CC0; the manual benchmark is under CC-BY).
- **Public Domain Books**: Available on [archive.org](https://archive.org) (e.g. historical Bodo language works by Rev. Sidney Endle, J. D. Anderson).
- **Bodo-Dimasa Archive**: [bododimasaarchive.org](https://bododimasaarchive.org) provides reference material, oral traditions, and cultural heritage documentation.

---

## Known Limitations

- **Inflected Forms & Loanwords**: Datasets like Aksharantar contain inflected grammatical word-forms (with case and plural suffixes such as `-नि` or `-फोरखौ`) rather than lemmatized dictionary headwords, as well as transliterated loanwords (such as English terms written in Bodo script).
- **Empty Meanings**: Current vocabulary imports provide word forms and transliterations; definition fields (`meaning_hi`, `meaning_en`) are mostly empty and require future lexical annotation.
- **Latin-Script Verification**: Words extracted from older Latin-script books may include English words from bilingual sections or older non-standard spellings, requiring manual verification before being considered authoritative.

---

## Contributing

We welcome community contributions to expand regional language preservation.

### Adding a Culture Note
1. Create a markdown file in `data/archive/<language>/culture/<item_name>.md`.
2. Include the required YAML frontmatter:
   ```markdown
   ---
   category: dance
   title: Bagurumba
   region: Assam
   source: Verified source reference
   related_words: []
   ---
   Description text goes here...
   ```
3. Run the culture loader to ingest:
   ```bash
   python -m bhasha_lib.culture data/archive/<language>/culture
   ```

### Adding a Source
- Use `add_source()` in Python or import via CSV using `python -m bhasha_lib.sources_import sources.csv`.
- An explicit, valid license is mandatory for all sources.

### Community Consent Policy
Community contributors must provide **written consent** from language speakers and cultural custodians for any traditional folk songs, oral stories, or audio recordings contributed to the archive.

---

## Roadmap

- **More Regional Languages**: Extend language configurations and tokenizers to additional endangered and regional Indian languages.
- **Audio Integration**: Ingest spoken audio, phoneme alignments, and pronunciation recordings.
- **Meanings & Lexical Annotation**: Add Hindi and English meanings, parts of speech, and root lemma relationships to the vocabulary.
