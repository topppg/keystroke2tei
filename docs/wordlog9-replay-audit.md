# Wordlog 9 replay audit

This records an earlier replay-backed audit. Current conversion takes its
starting document from `--original-docx`; replay HTML is optional verification
only. See [Wordlog 9 command evidence](wordlog9-command-mapping.md).

Five Wordlog 9.6 French IDFX sessions were supplied with an original Word
document, saved final Word document, and HTML replay. AC_12, AC_27, AC_41,
and AC_15 were used to refine the deterministic replay rules. AC_21 was kept
out of that process and run once as a held-out check.

| Group | Session | Before: final text matched replay | After: typed text / full document / edit counts |
| --- | --- | --- | --- |
| 1 | AC_12 | No | Yes / Yes / Yes |
| 2 | AC_27 | No | Yes / Yes / Yes |
| 3 | AC_41 | No | Yes / Yes / Yes |
| 4 | AC_15 | No | Yes / Yes / Yes |
| 5, held out | AC_21 | Not inspected before rule freeze | Yes / Yes / Yes |

The fuller replay uses the original document and IDFX selection events to
separate keyboard edits from selection snapshots. It also handles Word
`insert` events, clipboard edits, keys typed in dialogs, and a smart-space
deletion after a selected-text edit. A saved final document is an optional
constraint for locating and identifying single-character Word insertions whose
exact position and character are absent from IDFX. The optimization is limited
to one-character insertions tied to an IDFX `insert` event; it does not import
unlogged passages.

The original Word document matched each replay's starting text exactly. The
saved final Word documents do not all match the corresponding replay exactly:
the character-level difference sizes are 3, 8, 12, 5,319, and 1 for groups
1–5 respectively. In the held-out AC_21 case the one-character difference is
`bôîte` in the replay versus `boîte` in the saved Word document. The HTML
replays were generated from IDFX and Word files by the supplied replay script,
so agreement with them checks implementation consistency rather than providing
a fully independent record of the writing process.

All five outputs pass the bundled TEI P5 schema. The stricter Loxensis check
reports missing `@seq` on untimed IDFX replacement or Word-insert operations
(15, 48, 69, 25, and 22 elements respectively). IDFX supplies no exact time
for these operations; the converter does not invent one. Duplicate-evidence
warnings also remain when one source event yields more than one TEI operation.
