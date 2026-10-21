# keystroke2tei

Convert keystroke logging data into [TEI XML](https://tei-c.org/) genetic editions, following the [Keystroke Loxensis](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding) encoding conventions.

Supports three input formats:
- **Inputlog CSV** — the standard [Inputlog](https://www.inputlog.net/) export
- **IDFX** — Inputlog's native XML format
- **KLiCKe CSV** — the web-based logger from the [KLiCKe Corpus](https://github.com/terryyutian/KLiCKe-Corpus)

## The problem

Writing process research captures every keystroke, mouse click, and revision a writer makes. The output is a flat log with thousands of low-level events.

Researchers need this data in **TEI XML** format — a structured representation where text additions (`<add>`), deletions (`<del>`), and modifications are nested hierarchically, preserving the temporal layering of the writing process.

## The solution

`keystroke2tei` automates this conversion. It reads a keystroke log, replays the writing events, and produces a valid TEI XML genetic edition following the [Keystroke Loxensis encoding conventions](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding):

- **Inline corrections** — each typo fix appears as `<del>` nested inside the flowing text
- **Flowing text** — one `<add>` per writing burst with inline `<del>` markers, not fragmented elements
- **Loxensis type classification**: `nt` for new text, `typo` for likely spelling corrections, `context` for edits to a completed sentence, and `pre-context` for edits before completion
- **`@seq` as timestamp** — `hhmmss` format from the event's start time
- **`@evidence` as event ID** — single ID or range (e.g. `"380-398"`) linking back to the raw log
- **Sentence segments** (`<seg>`) based on the replayed final text
- **`<teiHeader>`** populated from session metadata (participant, language, date)
- **Diagnostics** — structured warnings for autocomplete drift, unknown deletions, missing source attributes, and mismatches between the TEI reading text and replayed text

### Example output

```xml
<seg>
  <add seq="000046" type="nt" evidence="5-71">I ve<del seq="000047"
  type="typo" evidence="9-10">ve</del>believe most people are more likely
  to be happy if they focur<del seq="000103" type="typo"
  evidence="72">r</del>s on meeting their own <del seq="000114"
  type="typo" evidence="96-105">their own </del>or pursuing their
  personal goals.</add>
</seg>
```

Each `<del>` shows exactly what the writer typed and then deleted. `@seq` gives the timestamp, `@evidence` links to the event ID(s) in the original log.

### Architecture

The converter trusts **CSV positions as absolute truth**. It uses a position-indexed character map (`CharMap`) that only tracks characters explicitly seen in the log. Autocomplete/spellcheck insertions are tracked as unknown (`None`) rather than guessed.

Validated against:
- 4,992 KLiCKe CSV files and 4,992 corresponding IDFX files: all converted without exceptions; the TEI reading text matched the replayed text in 4,906 CSV and 4,860 IDFX files. The remaining files emit a warning for editorial review.
- 1 Inputlog CSV and 4 TEIoKEY HTML files: all converted with matching reading text.

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

## Usage

### Single file

```bash
uv run keystroke2tei data/input/doc.csv -o data/output/
```

### Batch mode (directory)

```bash
uv run keystroke2tei data/input/ -o data/output/
# Processes all .csv and .idfx files, writes .tei.xml to output/
```

### With diagnostics and stats

```bash
uv run keystroke2tei data/input/ -o data/output/ -v --stats
```

- `-v` prints diagnostics, including cases that need editorial review
- `--stats` writes a JSON sidecar per file with conversion statistics

### Python API

```python
from keystroke2tei import parse_csv, convert, write_tei

events, metadata, warnings = parse_csv("data/input/doc.csv")
result = convert(events, metadata=metadata)
xml = write_tei(result.segments, metadata=metadata)

print(result.final_text)
print(result.stats.to_dict())
print(result.diagnostics)
```

## Running tests

```bash
uv run pytest
```

Tests cover CharMap operations, key classification, event processing, episode grouping, parsing edge cases, and end-to-end conversion.

## Project structure

```
keystroke2tei/
├── keystroke2tei/      # Package source
│   ├── parser.py           # Inputlog CSV parsing (auto-detect encoding/delimiter)
│   ├── idfx_parser.py      # IDFX XML parsing (with control char sanitization)
│   ├── klicke_parser.py    # KLiCKe web-logger CSV parsing
│   ├── converter.py        # CharMap, event replay, episode grouping, TEI tree
│   ├── writer.py           # TEI XML serialization via lxml
│   ├── models.py           # Event, TEINode, Diagnostic, ConversionStats
│   └── cli.py              # CLI (single/batch/verbose/stats)
├── data/
│   ├── input/              # Drop your CSV/IDFX files here
│   └── corpora/            # Test corpus files (KLiCKe, THEtool)
│   └── output/             # Generated TEI XML + stats JSON
├── tests/
│   ├── test_converter.py   # Unit + integration + E2E tests
│   └── compare.py          # Structural comparison (generated vs reference)
└── pyproject.toml
```

## How it works

1. **Parse** — Read keystroke log (CSV/IDFX/KLiCKe), extract events and session metadata. Auto-detect encoding and delimiter for CSVs.
2. **Replay** — Process events using a `CharMap` (position -> character). CSV positions are absolute truth. Unknown characters (autocomplete) are `None`.
3. **Split** — Split actions at every insert/delete transition. Each contiguous typing run or deletion run becomes its own episode.
4. **Classify** — Label episodes per [Loxensis conventions](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/additions): `typo` for inline backspace corrections, `context` for cursor-relocated revisions, `nt` for new text.
5. **Segment** — Assign surviving actions to sentence `<seg>` elements using the replayed final text.
6. **Build tree** — Nest `<del>` elements inside parent `<add>` nodes. Continuation text flows as inline text within the parent.
7. **Serialize** — Write valid TEI XML with `@seq` (timestamp), `@evidence` (event ID range), and TEI namespace.

## Encoding conventions

This tool follows the [Keystroke Loxensis](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding) encoding manual (Bekius, 2021):

| Attribute | Format | Example |
|-----------|--------|---------|
| `@seq` | `hhmmss` timestamp | `"001423"` (14 min 23 sec) |
| `@evidence` | Event ID or range | `"380"` or `"380-398"` |
| `@type` | Revision category | `"nt"`, `"typo"`, `"context"`, `"pre-context"` |

**Type classification rules:**
- `nt` — new text production (forward typing)
- `typo` — likely spelling or case correction, including some relocated edits
- `context` — edit to an already completed sentence
- `pre-context` — edit made before the sentence was complete

## Known limitations

- **Deleted text from autocomplete is empty.** When a backspace deletes a character inserted by autocomplete (not by the writer), the `<del>` element has empty text. By design.
- **Sentence detection is heuristic.** The final-text punctuation rule can split abbreviations or miss unusual sentence boundaries. Review `<seg>` boundaries in complex sessions.
- **Editorial types are inferred.** Keystroke order and cursor position cannot establish a writer's intent. In particular, distinguishing a spelling correction from a word choice change requires review. The converter reports uncertain word replacements.
- **Overlapping revisions can resist tree encoding.** Some crossing insertions cannot be represented as nested XML without splitting a revision. The converter reports when the TEI reading text differs from replayed text; review those files before using them as editions.
- **Source attributes may be incomplete.** Some IDFX replacement events lack a timestamp, so `@seq` cannot be derived. A single replacement can create both `<del>` and `<add>` with the same source event ID; the converter reports the repeated `@evidence` instead of inventing an identifier.
- **Deep nesting is heuristic.** Complex edits may need manual adjustment.

The corpus figures above measure conversion and text fidelity. They do not certify every inferred revision type or sentence boundary; those remain editorial decisions.

## References

- Bekius, L. (2021). [The Reconstruction of the Author's Movement Through the Text](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding). Keystroke Loxensis encoding manual.
- Leijten, M. & Van Waes, L. (2013). [Keystroke Logging in Writing Research](https://journals.sagepub.com/doi/10.1177/0741088313491692). Written Communication.
- Tian, Y., Crossley, S., & Van Waes, L. (2025). [The KLiCKe Corpus](https://github.com/terryyutian/KLiCKe-Corpus). Journal of Writing Research.

## Next steps

- TEI RelaxNG schema validation of output
- Editorial review workflow for ambiguous classifications and overlapping revisions
- Multi-session linking (`<linkGrp>`)
- Richer `<teiHeader>` (duration, start time, `<respStmt>`)
- JSON/flat export format
