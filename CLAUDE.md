# keystroke2tei — Project Instructions

## What this project does

Converts keystroke logging data (Inputlog CSV, IDFX, KLiCKe CSV) into TEI XML genetic editions for writing process research, following the [Keystroke Loxensis](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding) encoding conventions. Output is compatible with the [Keystroke Loxensis visualizer](https://github.com/eXtant-CMG/Keystroke-Loxensis).

Core pipeline: parse events → replay with CharMap → split at insert/delete transitions → classify episodes → build nested TEI tree → serialize XML.

No other open source tool automates this conversion. The encoding step was previously done manually by researchers.

## Architecture

- **Flat package layout**: source is in `keystroke2tei/` (not src layout)
- **CSV positions are absolute truth**: the converter uses a `CharMap` (position-indexed `list[str | None]`) that only tracks characters explicitly seen in the log. `None` = unknown (autocomplete-inserted). No document buffer.
- **Episode splitting**: every insert↔delete transition creates a new episode. This produces clean inline `<del>` elements.
- **Three parsers**: `parser.py` (Inputlog CSV), `idfx_parser.py` (IDFX XML), `klicke_parser.py` (KLiCKe CSV). Auto-detected by extension + header sniffing.
- **Loxensis conventions**: `@seq` = timestamp (hhmmss), `@evidence` = event ID range, `@type` = typo/context/nt/pre-context based on cursor relocation (not text length).

## Key files

- `keystroke2tei/converter.py` — the core: `CharMap`, `_process_events()`, `_group_into_episodes()`, `_build_tei_tree()`, `_classify_revision_type()`. Most changes happen here.
- `keystroke2tei/models.py` — all dataclasses: `Event`, `TEINode`, `Diagnostic`, `ConversionStats`, `SessionMetadata`
- `keystroke2tei/writer.py` — TEI XML serialization via lxml. Handles `text`/`tail` for nested elements.
- `keystroke2tei/cli.py` — CLI entry point. Format detection, batch processing, verbose diagnostics, stats JSON sidecar.
- `keystroke2tei/parser.py` — Inputlog CSV parser with auto-detect encoding (utf-8/cp1252/latin-1) and delimiter.
- `keystroke2tei/idfx_parser.py` — IDFX XML parser with control char sanitization and garbage-prefix handling.
- `keystroke2tei/klicke_parser.py` — KLiCKe web-logger CSV parser.

## Data

Data directories are **gitignored** — not committed:
- `data/input/` — user input files (CSV, IDFX)
- `data/output/` — generated TEI XML + stats JSON
- `data/corpora/` — test corpus files (KLiCKe, THEtool)

Test data must be obtained separately:
- KLiCKe: https://github.com/terryyutian/KLiCKe-Corpus (Google Drive, ~5000 CSVs)
- THEtool: https://github.com/mulasik/wta (IDFX files in data/ directory)

## Development

```bash
uv sync                                                    # install deps
uv run pytest                                              # 28 tests
uv run keystroke2tei data/input/ -o data/output/ -v --stats  # test conversion
uv run keystroke2tei data/corpora/ -o data/output/           # test against corpus
```

## Stress test results

- **4992/4992 KLiCKe CSVs** processed successfully (100%), 57 seconds
- **22/22 IDFX files** from THEtool corpus, 0 errors
- **1/1 Inputlog CSV** (original test file), 0 errors
- Range: 34–720 deletions, 42–4858 typed chars, 1–19 segments per file

## Design decisions to preserve

- **Never maintain a document buffer.** The v1 `DocumentState` approach caused position drift with autocomplete. `CharMap` is correct by construction.
- **Always emit move actions for mouse clicks.** Even if position matches cursor — clicks are episode boundaries.
- **Split at every insert↔delete transition.** This produces clean per-correction `<del>` nodes. Don't merge episodes.
- **Post-revision inserts become TEXT nodes, not `<add>`.** Continuation text flows inside the parent `<add>` as inline text. Only new typing bursts (after mouse clicks or segment breaks) create new `<add>` parents.
- **Type classification by cursor relocation, not text length.** Per Loxensis: inline backspace = `typo`, mouse-click revision = `context`. Old v1 used character count which was wrong.
- **`@seq` is a timestamp, `@evidence` is event ID.** Per Loxensis spec. Not incrementing counters.
- **Diagnostics are structured.** `Diagnostic` dataclass instances in `ConversionResult`, not print statements. CLI renders them with `-v`.
- **Encoding detection reads full file.** Not just first 4096 bytes — some files have non-UTF-8 bytes deep in the file (smart quotes, em dashes).

## Conventions

- Python 3.12+, type hints everywhere
- No docstrings unless logic is non-obvious
- `uv` for package management
- Tests via pytest, all in `tests/test_converter.py`
- One-line commit messages, conventional commits format
- Data files are never committed — gitignored

## Known sensitive areas

- `_build_tei_tree()` — the `current_add` and `had_move_since_last_add` tracking is subtle. Determines text flow vs new `<add>` creation. Test changes against full corpus.
- `_group_into_episodes()` — insert↔delete transition splitting. Core of output quality.
- `_classify_revision_type()` — Loxensis compliance. `cursor_moved_back` distinguishes typo from context.
- IDFX `_sanitize_xml()` — handles `&#x8;` and garbage-prefixed files.
- KLiCKe parser — `CursorPosition` is post-event (vs Inputlog pre-event). Adjusts BACK positions.
- `_detect_encoding()` in parser.py — reads full file, not sample. Required for KLiCKe files with cp1252 smart quotes.
