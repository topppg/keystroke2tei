# Wordlog 9 command evidence

For a session with existing text, conversion reads the original DOCX as the
starting document and applies IDFX events in their recorded order. The saved
final DOCX is used to resolve otherwise ambiguous one-character Word insertions
and to compare the completed TEI reading with the saved document. Replay HTML
is an optional comparison and never supplies conversion text.

The [Keystroke Loxensis addition](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/additions/)
and [deletion](https://extant-cmg.github.io/eXtant-wiki/loxensis/encoding/deletions/)
rules specify the **TEI meaning** of an action. IDFX interpretation is a
separate, source-specific step. The command mappings below apply when the
recorded selection, keyboard action, and subsequent document change agree.

| IDFX evidence | Conversion | TEI evidence |
| --- | --- | --- |
| Selected text, Ctrl+X, document contraction, then matching Ctrl+V and insertion | Pair the removed and inserted text as a move | `<del type="translocation">` points to the Ctrl+X keyboard event; `<add type="translocation">` points to Ctrl+V. Each `@seq` uses that key event's clock. |
| Selected text and Ctrl+X without a confirmed matching paste | Preserve a deletion without claiming a move | The cut event identifies the deletion; its contextual type remains subject to the usual revision rules. |
| Selected text, Ctrl+C, then Ctrl+V | Preserve an insertion and the unchanged source | Do not label the insertion `translocation`, because no text was removed. |
| Word `replacement` or `insert` after a keyboard action | Use the Word event to confirm document change, selection, or insertion length | Prefer the triggering keyboard event for `@evidence` and `@seq` when the operation is established. Untimed Word events alone cannot supply an exact `@seq`. |

A matching final document confirms the **resulting text**, not the operation
that produced it. For example, AC_21 moves “tellement” within its sentence:
the original and final DOCX establish its old and new positions, while IDFX
events 23 and 36 establish Ctrl+X and Ctrl+V. The deleted occurrence remains in
genetic TEI, but the final reading includes only the added occurrence.

The saved final DOCX can also differ from the logged end state. Conversion
reports those differences and does not copy unexplained final-document text
into TEI. Source-paste classification and editorial labels such as `typo`
versus `context` still require review when the IDFX evidence is insufficient.
