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
- **`@seq` as timestamp** — `hhmmss` for logs without a clock anchor; IDFX files with
  creation-clock metadata use `yyyymmddhhmmss` local wall time
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

The converter replays actions at their pre-event cursor position. The KLiCKe
CSV parser and older Wordlog 7 IDFX logs normalize recorded post-key positions.
Wordlog 9 IDFX logs already record pre-key positions and document lengths.
For IDFX, an OEM key with no recorded character is treated as a non-text key;
the key name is not inserted into the document. On French layouts, an empty
`VK_OEM_6` dead key composes with the following vowel. IDFX events marked
`replay=False` are represented by their following replacement event; selection
snapshots are checked against the current text. For a Wordlog 9 session that
starts with existing text, the original Word document supplies the baseline
needed to reconstruct selections, Word-generated insertions, clipboard edits,
and keys typed in dialogs. When the log supplies both
`__LogCreationDate` and `__LogRelativeCreationDate`, event times are anchored
to the recorded local clock, including sessions crossing midnight.
A position-indexed character map (`CharMap`)
tracks characters explicitly seen in the log. Autocomplete/spellcheck
insertions are tracked as unknown (`None`) rather than guessed.

Validated against:
- 4,992 KLiCKe CSV files and 4,992 corresponding IDFX files: all converted without exceptions, and all 9,984 TEI reading texts matched the replayed texts. Source-attribute and editorial review findings remain.
- 1 Inputlog CSV and 4 TEIoKEY HTML files: all converted with matching reading text.

All 9,984 KLiCKe outputs pass the bundled TEI schema. The Loxensis audit still
flags IDFX replacement operations without source-derived `@seq` and operations
sharing a source event ID. The IDFX files do not record timestamps for
replacement events. The cursor correction and a sample comparison with saved
final documents are documented in
[the IDFX provenance audit](docs/idfx-provenance-audit.md).
The Wordlog 9 development and held-out replay checks are in
[the replay audit](docs/wordlog9-replay-audit.md).

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

For a Wordlog 9 IDFX session that starts with existing text, supply its
original Word document as the baseline. A saved final Word document can resolve
single-character Word insertions whose exact position is absent from the IDFX log:

```bash
uv run keystroke2tei session.idfx -o session.tei.xml \
  --original-docx original_session.docx --final-docx final_session.docx \
  --review-report
```

The resulting XML includes the full final document, including surviving text
from the starting document. In the keystroke paragraph, text inside `<add>`
comes from logged writing; unmarked text survives from the starting document.
The final Word document is used only to locate and identify ambiguous
one-character insertions; it is not substituted for the reconstructed text.
If no final DOCX is supplied and such an insertion survives, the converter
warns because the IDFX and original document cannot determine its exact value
and location. AC_21 has one such insertion.

If an Inputlog replay HTML is available, add `--replay-html replay_session.html`
to compare the original DOCX with its starting text and the reconstructed
document, serialized XML reading text, and edit counts with the replay. A
mismatch is printed as a warning; `--validate` also makes it a conversion error.
The replay is optional: without it, the original DOCX still supplies the
baseline and the XML reading text is checked against the reconstruction. For
older workflows without an original DOCX, `--replay-html` can also supply the
starting text. A replay HTML generated from the same IDFX and Word files is a
detailed cross-check, but is not independent evidence for every editorial
decision.

`--classify` makes an optional model call only for editorial revision labels.
Text reconstruction and replay checks stay deterministic. The classifier sees
candidate edits in source-action order with a short snapshot of the document
immediately before each edit; its labels remain subject to editorial review.

### Validate and prepare editorial review

```bash
uv run keystroke2tei data/input/doc.csv -o data/output/ --validate --review-report
uv run keystroke2tei data/input/doc.csv -o data/output/ --validate --review-report --overrides data/input/doc.overrides.json
```

`--validate` checks the output against the bundled TEI P5 4.12.0 Relax NG schema
and machine-checkable Loxensis rules. Validation errors and reading-text
mismatches give the command a nonzero exit status; the XML is still written
for inspection. Warnings, such as
evidence IDs reused by paired replacement operations, are shown but do not fail
the command. `--review-report` writes `<name>.review.json` beside the TEI file.
For batch conversion, `--overrides` can name a directory containing
`<input-stem>.overrides.json` files.
The bundled schema is from the TEI Consortium; its license is in
`keystroke2tei/schemas/LICENSE-TEI.md`.

### Python API

```python
from keystroke2tei import parse_csv, convert, write_tei

events, metadata, warnings = parse_csv("data/input/doc.csv")
result = convert(events, metadata=metadata)
xml = write_tei(result.segments, metadata=metadata)

print(result.final_text)
print(result.final_document_text)
print(result.stats.to_dict())
print(result.diagnostics)
```

`final_text` is the surviving logged text; `final_document_text` includes the
starting document when one was supplied.

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
│   ├── validation.py       # TEI schema and Loxensis rule checks
│   ├── review.py           # editorial report and explicit overrides
│   └── cli.py              # conversion, validation, and review CLI
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

## Editorial review

The conversion result can be inspected as a JSON review report. It lists inferred
revision types, every boundary between `<seg>` elements, missing `@seq`, `@type`,
or `@evidence`, repeated evidence values, and any difference between the TEI
reading text and the replayed text. These are review prompts, not proof that a
particular interpretation is wrong. The [Loxensis additions manual](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/additions/)
requires `@seq`, `@type`, and `@evidence` on `<add>` and treats the distinction
between `typo`, `pre-context`, and `context` as an editorial classification.

```python
import json
from keystroke2tei.review import apply_overrides, build_review_report, load_overrides
from keystroke2tei.writer import write_tei

# `result` is a ConversionResult returned by convert(...).
report = build_review_report(result)
with open("review.json", "w", encoding="utf-8") as file:
    json.dump(report, file, indent=2, ensure_ascii=False)

apply_overrides(result, load_overrides("overrides.json"))
tei = write_tei(result.segments, result.metadata, result.focus_sources)
updated_report = build_review_report(result)
```

Copy a node's `target` from the report into an override file. The source
`kind`, `evidence`, and `occurrence` identify the operation; `path` locates an
operation when its evidence is missing. A stale target raises an error rather
than editing a different node. All entries are checked before any change is
applied.

```json
{
  "format_version": 1,
  "overrides": [
    {
      "target": {"kind": "add", "evidence": "2", "occurrence": 0, "path": [0, 0, 1]},
      "set": {"seq": "000002", "revision_type": "typo"}
    }
  ]
}
```

`set` accepts `revision_type` (serialized as `@type`), `seq`, and `evidence`.
Supply values only when the source log or editorial evidence supports them.
Structural decisions such as moving a sentence boundary or resolving crossing
revisions still require inspection and editing of the TEI XML. The report's
`source_diagnostics` retain the original conversion warnings even after an
override; the `issues` list is recalculated from the current tree.

## Known limitations

- **Deleted text from autocomplete is empty.** When a backspace deletes a character inserted by autocomplete (not by the writer), the `<del>` element has empty text. By design.
- **Sentence detection is heuristic.** The final-text punctuation rule can split abbreviations or miss unusual sentence boundaries. Review `<seg>` boundaries in complex sessions.
- **Editorial types are inferred.** Keystroke order and cursor position cannot establish a writer's intent. In particular, distinguishing a spelling correction from a word choice change requires review. The converter reports uncertain word replacements.
- **Overlapping revisions can resist tree encoding.** Some crossing insertions require an operation to be split into multiple XML elements. That can repeat its source `@evidence`; the validator and review report flag this. The converter also reports any reading-text mismatch found in new input.
- **Source attributes may be incomplete.** Some IDFX replacement events lack a timestamp, so `@seq` cannot be derived. A single replacement can create both `<del>` and `<add>` with the same source event ID; the converter reports the repeated `@evidence` instead of inventing an identifier.
- **Starting documents require a baseline.** Use `--original-docx` to include
  surviving original text and recover the exact text removed during the
  session. A replay HTML can supply that starting text if the original DOCX
  is unavailable. Without either, the XML can represent only text known from
  the log.
- **Deep nesting is heuristic.** Complex edits may need manual adjustment.

The corpus figures above measure conversion and text fidelity. They do not certify every inferred revision type or sentence boundary; those remain editorial decisions.

## License

This project is licensed under the [MIT License](LICENSE). The bundled TEI
schema retains the [TEI Consortium's separate license](keystroke2tei/schemas/LICENSE-TEI.md).

## References

- Bekius, L. (2021). [The Reconstruction of the Author's Movement Through the Text](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding). Keystroke Loxensis encoding manual.
- Leijten, M. & Van Waes, L. (2013). [Keystroke Logging in Writing Research](https://journals.sagepub.com/doi/10.1177/0741088313491692). Written Communication.
- Tian, Y., Crossley, S., & Van Waes, L. (2025). [The KLiCKe Corpus](https://github.com/terryyutian/KLiCKe-Corpus). Journal of Writing Research.

## Next steps

- Multi-session linking (`<linkGrp>`)
- Richer `<teiHeader>` (duration, start time, `<respStmt>`)
- JSON/flat export format
