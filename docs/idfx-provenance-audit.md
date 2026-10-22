# IDFX provenance and editorial audit

The KLiCKe WritingTask corpus includes an IDFX log, a CSV log, and a saved
final `.txt` document for each session. The saved document is an independent
check on the replayed text; agreement between TEI and replay alone does not
establish agreement with the writer's final document.

## Event fields

An inspection of all 4,992 IDFX logs found 99,342 `<event
type="replacement">` elements. Every one has only a `wordlog` part with
`start`, `end`, and `newtext`; none has an event timestamp or a `winlog` part.
Most are bracketed by timed keyboard events, but those only give a time
interval, not the replacement's exact time. The paired CSV log does not have
a matching replacement event ID. An exact `@seq` for these operations cannot
be recovered from these sources.

The KLiCKe corpus uses Wordlog 7. Its IDFX keyboard `wordlog/position` and
`wordlog/documentLength` describe the state **after** the key. The converter
replays keys using the cursor and length **before** the key, so the parser
normalizes these values for insertion, backspace, and delete keys. Wordlog 9
logs, such as AC_33, record the pre-key state directly. The parser selects
the interpretation from `__LogProgramVersion`. This correction does not
impute a timestamp or alter the source event ID.

One replacement can produce a `<del>` and an `<add>` with the same ID, and a
single operation can be split into several TEI elements at sentence or
crossing-edit boundaries. The resulting repeated `@evidence` values remain
visible as warnings: assigning a different source ID to either element
would break the link to the log.

## Sample against saved documents

The audit compared every 50th IDFX file in sorted filename order (100
sessions) with the corresponding saved `.txt` file. Similarity here is
Python `difflib.SequenceMatcher` with `autojunk=False`; it is a triage measure,
not a claim of editorial equivalence.

| Measure | Before cursor correction | After cursor correction |
| --- | ---: | ---: |
| Mean text similarity | 0.94144 | 0.98226 |
| Sessions improved | — | 100 of 100 |
| Sessions regressed | — | 0 of 100 |

Two traced sessions show the scale of the correction: `81294539` rose from
0.94372 to 0.99963 similarity to its saved document; `10024141` rose from
0.93461 to 0.99222. Remaining differences include punctuation, whitespace,
and text affected by replacement or unrecorded key values.

The sample also contains cases requiring editorial investigation. Session
`76924690` has 260 replacement events, empty key values for `VK_OEM_7`, and
0.72842 similarity after correction. Session `94457320` has a long passage
in the saved document that the current IDFX replay does not recover (0.86266
similarity). These are not safe to repair by copying final text into TEI:
that would assign no source writing action to the inserted content.

Sentence boundaries and revision types still require reading the source
session. This review found a false boundary at `U.S. citizens`; the sentence
splitter now keeps an acronym with a following lowercase word. The review
report lists every remaining boundary and inferred type; a final
document comparison should be used alongside it, particularly for sessions
with replacement events or unsupported virtual keys.

## Replay HTML for Wordlog 9

For AC_33, the Inputlog replay HTML contains the initial document and a
character-level record of every edit. The saved Word document is useful for
comparison but does not preserve this edit history. With the replay HTML as
the initial document, conversion matches the replay's 1,308 surviving typed
characters and 88,600-character final document exactly. It also agrees on
1,562 inserted characters and 739 deleted characters (254 typed and 485
from the initial document). The report records these checks; inferred
revision types and sentence boundaries still need editorial review.

## Cross-corpus check of replay rules

A 100-file systematic sample of the Wordlog 7 WritingTask corpus and all 22
locally available SCR logs were checked against the AC_33 parser rules. The
Wordlog 7 sample contained 885 same-length replacements followed by a matching
selection. That pattern alone does not prove the replacement is a snapshot:
discarding it reduced similarity to the independently saved document for
session `30098353` from 0.96860 to 0.95316. The parser now retains these
events and lets the converter skip a replacement only when its `newtext`
actually matches the current document span. AC_33 still matches its replay
exactly with this correction.

The same sample contained 563 replacements after non-replayed backspaces;
all had empty `newtext`. The 22 SCR logs had another 27, also empty. The
nonempty stale values corrected for AC_33 have not been observed in these
other sources, so that correction remains provisional for other logs.
