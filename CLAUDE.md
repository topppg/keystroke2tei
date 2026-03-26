# keystroke2tei — Project Instructions

## What this project does

Converts keystroke logging data (Inputlog CSV, IDFX, KLiCKe CSV) into TEI XML genetic editions for writing process research. The core pipeline: parse events → replay with CharMap → split at insert/delete transitions → classify episodes → build nested TEI tree → serialize XML.

## Architecture

- **src layout**: package source is in `keystroke2tei/`
- **CSV positions are absolute truth**: the converter never maintains a synchronized document buffer. It uses a `CharMap` (position-indexed `list[str | None]`) that only tracks characters explicitly seen in the log. `None` = unknown (autocomplete-inserted).
- **Episode splitting**: every insert↔delete transition in the action list creates a new episode. This is what produces clean inline `<del>` elements instead of garbled aggregated text.
- **Three parsers**: `parser.py` (Inputlog CSV), `idfx_parser.py` (IDFX XML), `klicke_parser.py` (KLiCKe CSV). The CLI auto-detects format by file extension and CSV header sniffing.

## Key files

- `keystroke2tei/converter.py` — the core: `CharMap`, `_process_events()`, `_group_into_episodes()`, `_build_tei_tree()`. Most changes happen here.
- `keystroke2tei/models.py` — all dataclasses: `Event`, `TEINode`, `Diagnostic`, `ConversionStats`, `SessionMetadata`
- `keystroke2tei/writer.py` — TEI XML serialization via lxml. Handles `text`/`tail` for nested elements.
- `keystroke2tei/cli.py` — CLI entry point. Format detection, batch processing, verbose diagnostics, stats JSON sidecar.

## Development

```bash
uv sync                           # install deps
uv run pytest                     # 28 tests
uv run keystroke2tei data/input/ -o data/output/ -v --stats   # test conversion
uv run keystroke2tei data/corpora/ -o data/output/          # test against 31 corpus files
```

## Testing

- Unit tests for `CharMap`, `_classify_key`, `_process_events`, `_group_into_episodes`
- E2E test processes `data/input/doc.csv` and asserts on output structure
- `tests/compare.py` does structural comparison against `data/input/doc.xml` (hand-annotated reference)
- `data/corpora/` has 22 IDFX files (THEtool, German) + 9 KLiCKe CSVs (English essays) for batch validation

## Design decisions to preserve

- **Never maintain a document buffer.** The v1 `DocumentState` approach caused position drift with autocomplete. The `CharMap` approach is correct by construction.
- **Always emit move actions for mouse clicks.** Even if position matches cursor — clicks are episode boundaries.
- **Split at every insert↔delete transition.** This is what produces clean, per-correction `<del>` nodes. Don't merge episodes back.
- **Post-revision inserts become TEXT nodes, not `<add>`.** Continuation text flows inside the parent `<add>` as inline text. Only new typing bursts (after mouse clicks or segment breaks) create new `<add>` parents.
- **Diagnostics are structured, not logged.** They're `Diagnostic` dataclass instances in `ConversionResult`, not print statements. The CLI renders them when `-v` is passed.

## Conventions

- Python 3.12+, type hints everywhere
- No docstrings unless logic is non-obvious
- `uv` for package management
- Tests via pytest, all in `tests/test_converter.py`
- One-line commit messages, conventional commits format

## Known sensitive areas

- `_build_tei_tree()` — the `current_add` tracking logic is subtle. It determines whether text is appended to an existing parent or creates a new one. Test any changes against the full 31-file corpus.
- `_group_into_episodes()` — the insert↔delete transition splitting. This is the core of output quality. Changing the grouping logic will change every output file.
- IDFX parser `_sanitize_xml()` — handles invalid XML character references (control chars like `&#x8;`) and garbage-prefixed files. Real-world IDFX files are messy.
- KLiCKe parser position mapping — KLiCKe `CursorPosition` is post-event, Inputlog `position` is pre-event. The parser adjusts for BACK events (`position=cursor_pos + 1`).
