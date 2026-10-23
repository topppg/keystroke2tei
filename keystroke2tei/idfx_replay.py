"""Normalize Wordlog 9 document edits when the initial document is available.

The IDFX log includes cursor selections and Word-generated insertions that a
keyboard-only replay cannot represent. This module resolves those operations
before the ordinary TEI converter groups and classifies them.
"""

from __future__ import annotations

from dataclasses import replace
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree as ET

from keystroke2tei.idfx_parser import _sanitize_xml, parse_idfx
from keystroke2tei.models import Event, EventType, SessionMetadata

_DEAD = str.maketrans("aeiouAEIOU", "âêîôûÂÊÎÔÛ")
_MODIFIERS = {"VK_CAPITAL", "VK_SHIFT", "VK_LSHIFT", "VK_RSHIFT",
              "VK_CONTROL", "VK_LCONTROL", "VK_RCONTROL", "VK_MENU", "VK_LMENU", "VK_RMENU"}


def _parse_once(
    path: Path, initial_text: str, fixes: dict[int, tuple[int | None, str]] | None = None,
) -> tuple[list[Event], SessionMetadata, list[str], dict]:
    """Replay once and retain character identities for ambiguous Word insertions."""
    fixes = fixes or {}
    parsed, metadata, warnings = parse_idfx(path)
    source_by_id = {event.event_id: event for event in parsed}
    raw = path.read_text(encoding="utf-8-sig")
    xml_start = raw.find("<?xml")
    if xml_start < 0:
        xml_start = raw.find("<log")
    root = ET.fromstring(_sanitize_xml(raw[xml_start:] if xml_start > 0 else raw))
    version = next((entry.findtext("value") or "" for entry in root.findall("./meta/entry")
                    if entry.findtext("key") == "__LogProgramVersion"), "")
    major = version.split(".", 1)[0]
    if not major.isdigit() or int(major) < 9:
        raise ValueError("full-document IDFX conversion requires Wordlog 9 or later")
    source = list(root.iter("event"))

    # A keyboard event can belong to a Word dialog instead of the document.
    # Such keys leave both the document length and cursor unchanged.
    ghost: set[int] = set()
    previous_key: tuple[int, int, int] | None = None
    touched = False
    for element in source:
        kind = element.get("type")
        if kind in {"replacement", "insert"}:
            touched = True
        elif kind == "keyboard":
            part = element.find("part[@type='wordlog']")
            if part is None:
                continue
            length = int(part.findtext("documentLength") or 0)
            position = int(part.findtext("position") or 0)
            if previous_key and previous_key[1] == length and (
                not touched or previous_key[2] == position
            ):
                ghost.add(previous_key[0])
            previous_key = (int(element.get("id", "0")), length, position) if part.findtext("replay") == "True" else None
            touched = False

    document = list(initial_text)
    identities = list(range(len(document)))
    next_identity = len(document)
    automatic_inserts: list[tuple[int, int]] = []
    events: list[Event] = []
    selection = (0, 0)
    last: dict | None = None
    pending_space: int | None = None
    pending_insert: dict | None = None
    clipboard: dict | None = None
    paired_cuts: set[int] = set()
    paste: dict | None = None
    paste_anchor: dict | None = None
    control = False
    find_mode = False
    undo = False
    clicked = False
    dead = False

    def replace_range(
        start: int, end: int, text: str, source_id: int, *, key_output: str | None = None,
        automatic: bool = False, revision_operation: str = "",
    ) -> None:
        nonlocal next_identity
        start = max(0, min(start, len(document)))
        end = max(start, min(end, len(document)))
        text = text.replace("\r", "\n")
        if document[start:end] == list(text):
            return
        if paste_anchor is not None:
            anchor = paste_anchor["position"]
            if start == end:
                if start < anchor:
                    paste_anchor["position"] = anchor + len(text)
            elif end <= anchor:
                paste_anchor["position"] = anchor + len(text) - (end - start)
            elif start < anchor:
                paste_anchor["position"] = start + len(text)
        document[start:end] = list(text)
        added_ids = list(range(next_identity, next_identity + len(text)))
        identities[start:end] = added_ids
        next_identity += len(text)
        if automatic and len(added_ids) == 1:
            automatic_inserts.append((source_id, added_ids[0]))
        if key_output is not None and source_id in source_by_id:
            key_position = end if key_output == "BACK" else start
            events.append(replace(
                source_by_id[source_id], output=key_output,
                position=key_position, doclength=0,
            ))
            return
        source_event = source_by_id.get(source_id)
        events.append(Event(
            event_type=EventType.REPLACEMENT, event_id=source_id,
            output=f"[{start}:{end}] {text}", char_production=0,
            action_time=0,
            start_time=source_event.start_time if revision_operation and source_event else 0,
            end_time=source_event.end_time if revision_operation and source_event else 0,
            pause_location=0,
            pause_location_full="", pause_time=0, position=start, doclength=0,
            revision_operation=revision_operation,
        ))

    def apply_insert(record: dict, length: int) -> None:
        nonlocal paste_anchor
        if length <= 0:
            return
        if record["paste"]:
            text = record["paste"]["text"]
            while len(text) > length and text.endswith(" "):
                text = text[:-1]
            while len(text) > length and text.startswith(" "):
                text = text[1:]
            text = (" " * (length - len(text)) + text)[:length]
            position = record["paste"]["position"]
        else:
            before = record["before"].replace("\r", "\n")
            text = before[-length:] if len(before) >= length else " " * (length - len(before)) + before
            position = record["position"] - length
        fix = fixes.get(record["id"])
        if fix and length == 1:
            left_id, text = fix
            if left_id is None:
                position = 0
            elif left_id in identities:
                position = identities.index(left_id) + 1
        paste_anchor = None
        paste = record["paste"]
        cut_id = paste.get("cut_id") if paste else None
        paired = bool(
            cut_id is not None and not paste["clipboard"]["moved"]
            and (text == paste["text"] or (text.strip() and text.strip() == paste["text"].strip()))
            and any(event.event_id == cut_id and event.revision_operation == "cut" for event in events)
        )
        before_count = len(events)
        replace_range(
            position, position, text,
            paste["event_id"] if paste else record["id"],
            automatic=not bool(paste),
            revision_operation=("paste" if paired else "copy") if paste else "",
        )
        if paired and len(events) > before_count:
            paired_cuts.add(cut_id)
            paste["clipboard"]["moved"] = True

    for element in source:
        kind = element.get("type")
        source_id = int(element.get("id", "0"))
        wordlog = element.find("part[@type='wordlog']")
        winlog = element.find("part[@type='winlog']")

        if kind == "mouse":
            if winlog is not None and winlog.findtext("type") == "click":
                clicked = True
                find_mode = False
            continue
        if kind == "selection" and wordlog is not None:
            find_mode = False
            a = min(int(wordlog.findtext("start") or 0), len(document))
            b = min(int(wordlog.findtext("end") or 0), len(document))
            selection = (a, b)
            last = None
            if pending_space is not None:
                if selection == (pending_space - 1, pending_space - 1) and pending_space > 0:
                    replace_range(pending_space - 1, pending_space, "", source_id)
                pending_space = None
            continue
        if kind == "insert" and wordlog is not None:
            pending_insert = {
                "id": source_id,
                "position": int(wordlog.findtext("position") or 0),
                "before": wordlog.findtext("before") or "",
                "paste": paste,
            }
            paste = None
            continue
        if kind == "replacement" and wordlog is not None:
            start = int(wordlog.findtext("start") or 0)
            end = int(wordlog.findtext("end") or 0)
            new_text = wordlog.findtext("newtext") or ""
            selected = last["selection"] if last and last["selection"] else None
            if undo or (last is None and not new_text and end > start):
                replace_range(start, end, new_text, source_id)
                undo = False
            elif selected and selected[0] <= start <= selected[0] + 1:
                a, b = selected
                typed = last["value"] not in ("", "\x08")
                cut = not typed and last.get("control") and last.get("key") == "VK_X"
                operation_id = last["id"] if cut else source_id
                if start == a and (end >= b or (not typed and not new_text)):
                    replace_range(
                        start, end, new_text if typed else "", operation_id,
                        revision_operation="cut" if cut else "",
                    )
                    cursor = start + (len(new_text) if typed else 0)
                else:
                    q = end if start == a + 1 and not new_text else b
                    replace_range(
                        a, q, last["value"] if typed else "", operation_id,
                        revision_operation="cut" if cut else "",
                    )
                    cursor = a + (1 if typed else 0)
                pending_space = None if typed else cursor
            # Otherwise this is a Word snapshot of selected text, not an edit.
            last = None
            continue
        if kind != "keyboard" or wordlog is None or winlog is None:
            continue

        position = int(wordlog.findtext("position") or 0)
        length = int(wordlog.findtext("documentLength") or 0)
        replay = wordlog.findtext("replay") != "False"
        key = winlog.findtext("key") or ""
        value = winlog.findtext("value") or ""
        if source_id in ghost or find_mode:
            continue
        if pending_insert is not None:
            inserted = length - len(document)
            if inserted > 0:
                apply_insert(pending_insert, inserted)
                pending_space = None
            elif paste is None:
                paste = pending_insert["paste"]
            pending_insert = None
        elif clicked and length > len(document) and pending_space is None:
            apply_insert({"id": source_id, "position": position, "before": "", "paste": None},
                         length - len(document))
        clicked = False
        if pending_space is not None:
            if len(document) == length + 1 and pending_space < len(document):
                replace_range(pending_space, pending_space + 1, "", source_id)
            pending_space = None
        if len(document) != length and key not in _MODIFIERS:
            warnings.append(
                f"event {source_id}: recorded document length {length} differs from "
                f"reconstructed document length {len(document)}"
            )

        is_control = key in {"VK_LCONTROL", "VK_RCONTROL", "VK_CONTROL"}
        if not replay and control and key in {"VK_Z", "VK_Y"}:
            undo = True
        if not replay and control and key in {"VK_F", "VK_H"}:
            find_mode = True
        if not replay and control and key in {"VK_C", "VK_X"} and selection[0] != selection[1]:
            clipboard = {
                "text": "".join(document[selection[0]:selection[1]]),
                "cut_id": source_id if key == "VK_X" else None,
                "moved": False,
            }
        if not replay and control and key == "VK_V" and clipboard and clipboard["text"]:
            paste = {
                "text": clipboard["text"], "position": position,
                "event_id": source_id, "cut_id": clipboard["cut_id"],
                "clipboard": clipboard,
            }
            paste_anchor = paste
            pending_insert = {"id": source_id, "position": position, "before": "", "paste": paste}
            last = None
        elif not replay and key in _MODIFIERS and last and last["selection"]:
            pass
        elif not replay:
            if key == "VK_OEM_6":
                dead = True
            selected = selection if selection[0] != selection[1] and selection[0] == position else None
            last = {"selection": selected, "value": value,
                    "key": key, "control": control, "id": source_id}
        else:
            last = None
            position = min(position, len(document))
            if key == "VK_BACK" or value == "\x08":
                if position > 0:
                    replace_range(position - 1, position, "", source_id, key_output="BACK")
            elif key == "VK_RETURN":
                replace_range(position, position, "\n", source_id, key_output="RETURN")
            elif value:
                if dead and len(value) == 1 and value in "aeiouAEIOU":
                    value = value.translate(_DEAD)
                replace_range(position, position, value, source_id,
                              key_output="SPACE" if value == " " else value)
                dead = False
        control = is_control or (control and key in {"VK_LSHIFT", "VK_RSHIFT", "VK_SHIFT"})

    for event in events:
        if event.revision_operation == "cut" and event.event_id not in paired_cuts:
            event.revision_operation = ""

    return events, metadata, warnings, {
        "final": "".join(document), "identities": identities,
        "automatic_inserts": automatic_inserts,
    }


def _difference_ops(actual: str, reference: str) -> list[tuple[str, int, int, int, int]]:
    """Character differences only inside paragraphs that differ."""
    left = actual.split("\n")
    right = reference.split("\n")
    left_offsets = [0]
    right_offsets = [0]
    for paragraph in left:
        left_offsets.append(left_offsets[-1] + len(paragraph) + 1)
    for paragraph in right:
        right_offsets.append(right_offsets[-1] + len(paragraph) + 1)
    result = []
    for tag, i, j, k, l in SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        a, b = left_offsets[i], min(left_offsets[j], len(actual))
        c, d = right_offsets[k], min(right_offsets[l], len(reference))
        for item in SequenceMatcher(None, actual[a:b], reference[c:d], autojunk=False).get_opcodes():
            if item[0] != "equal":
                result.append((item[0], a + item[1], a + item[2], c + item[3], c + item[4]))
    return result


def _difference_size(ops: list[tuple[str, int, int, int, int]]) -> int:
    return sum(max(end - start, right_end - right_start)
               for _, start, end, right_start, right_end in ops)


def parse_idfx_with_initial_text(
    path: Path, initial_text: str, final_text: str | None = None,
) -> tuple[list[Event], SessionMetadata, list[str]]:
    """Replay IDFX edits against a known baseline, preserving source IDs.

    A saved final document can resolve the position of single-character Word
    insertions whose IDFX events contain only a cursor and surrounding text.
    """
    events, metadata, warnings, trace = _parse_once(path, initial_text)
    if final_text is None:
        unresolved = sum(
            inserted_id in trace["identities"]
            for _, inserted_id in trace["automatic_inserts"]
        )
        if unresolved:
            warnings.append(
                f"{unresolved} surviving one-character Word insertion(s) cannot be "
                "verified from IDFX and the original document alone; "
                "provide --final-docx to resolve them"
            )
        return events, metadata, warnings
    if not trace["automatic_inserts"]:
        return events, metadata, warnings

    fixes: dict[int, tuple[int | None, str]] = {}
    ops = _difference_ops(trace["final"], final_text)
    best = _difference_size(ops)
    for event_id, inserted_id in trace["automatic_inserts"]:
        identities = trace["identities"]
        if inserted_id not in identities:
            continue
        position = identities.index(inserted_id)
        automatic_ids = {item[1] for item in trace["automatic_inserts"]}
        candidates: list[tuple[int, int | None, str]] = []
        for tag, start, end, right_start, right_end in ops:
            if abs(start - position) > 3000:
                continue
            if tag in {"insert", "replace"}:
                left = start - 1
                while left >= 0 and identities[left] in automatic_ids:
                    left -= 1
                left_id = identities[left] if left >= 0 else None
                for index in range(right_start, right_end):
                    candidates.append((abs(start - position), left_id, final_text[index]))
            if tag in {"delete", "replace"} and end > start:
                left = end - 1
                while left >= 0 and identities[left] in automatic_ids:
                    left -= 1
                left_id = identities[left] if left >= 0 else None
                candidates.append((abs(end - position), left_id, trace["final"][position]))
        seen: set[tuple[int | None, str]] = set()
        for _, left_id, char in sorted(candidates, key=lambda item: item[0]):
            if (left_id, char) in seen:
                continue
            seen.add((left_id, char))
            if len(seen) > 12:
                break
            trial = {**fixes, event_id: (left_id, char)}
            test_events, test_metadata, test_warnings, test_trace = _parse_once(path, initial_text, trial)
            test_ops = _difference_ops(test_trace["final"], final_text)
            score = _difference_size(test_ops)
            if score < best:
                fixes, events, metadata, warnings, trace, ops, best = (
                    trial, test_events, test_metadata, test_warnings, test_trace, test_ops, score,
                )
    if fixes:
        warnings.append(
            f"resolved {len(fixes)} ambiguous Word insertion(s) using the saved final document"
        )
    return events, metadata, warnings
