from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

from keystroke2tei.models import Event, EventType, SessionMetadata

_INVALID_XML_CHAR = re.compile(r"&#x([0-9a-fA-F]+);")


def _sanitize_xml(raw: str) -> str:
    """Remove XML character references for control chars (0x00-0x1F except 0x09/0x0A/0x0D)."""
    def _replace(m: re.Match[str]) -> str:
        code = int(m.group(1), 16)
        if code in (0x09, 0x0A, 0x0D) or code >= 0x20:
            return m.group(0)
        return ""
    return _INVALID_XML_CHAR.sub(_replace, raw)


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _int(el: ET.Element | None) -> int:
    t = _text(el)
    if not t:
        return 0
    try:
        return int(t)
    except ValueError:
        return 0


def _idfx_key_to_output(key: str, value: str) -> str:
    """Convert IDFX key names (VK_A, VK_RETURN, etc.) to Inputlog-style output."""
    if key.startswith("VK_"):
        name = key[3:]
    else:
        name = key

    if len(name) == 1:
        return value if value else name

    mapping: dict[str, str] = {
        "SPACE": "SPACE",
        "RETURN": "RETURN",
        "BACK": "BACK",
        "DELETE": "DELETE",
        "TAB": "TAB",
        "LEFT": "LEFT",
        "RIGHT": "RIGHT",
        "UP": "UP",
        "DOWN": "DOWN",
        "HOME": "HOME",
        "END": "END",
        "PRIOR": "PAGEUP",
        "NEXT": "PAGEDOWN",
        "ESCAPE": "ESCAPE",
        "INSERT": "INSERT",
        "CAPITAL": "CAPSLOCK",
        "NUMLOCK": "NUMLOCK",
        "SCROLL": "SCROLL",
        "SHIFT": "LSHIFT",
        "CONTROL": "LCTRL",
        "LSHIFT": "LSHIFT",
        "RSHIFT": "RSHIFT",
        "LCONTROL": "LCTRL",
        "RCONTROL": "RCTRL",
    }

    mapped = mapping.get(name)
    if mapped:
        return mapped

    if name.startswith("F") and name[1:].isdigit():
        return name

    if value and len(value) >= 1:
        return value

    return name


def _pre_key_state(key: str, output: str, position: int, doclength: int) -> tuple[int, int]:
    """Convert Wordlog's post-key cursor and length to pre-key values.

    The converter replays a keystroke at its pre-key cursor. Inputlog IDFX
    records the cursor and document length after the key has taken effect.
    Navigation and modifier keys do not change either value.
    """
    if output == "BACK":
        return position + 1, doclength + 1
    if output == "DELETE":
        return position, doclength + 1
    if output in {"SPACE", "RETURN", "TAB"}:
        width = 1
    elif key in {"VK_LEFT", "VK_RIGHT", "VK_UP", "VK_DOWN", "VK_HOME", "VK_END",
                 "VK_PRIOR", "VK_NEXT", "VK_SHIFT", "VK_LSHIFT", "VK_RSHIFT",
                 "VK_CONTROL", "VK_LCONTROL", "VK_RCONTROL", "VK_CAPITAL",
                 "VK_ESCAPE", "VK_INSERT"} or (key.startswith("VK_F") and key[4:].isdigit()):
        width = 0
    elif output.isprintable() and output not in {"UNKNOWN", "MODIFIER"}:
        width = len(output)
    else:
        width = 0
    return max(0, position - width), max(0, doclength - width)


def parse_idfx(path: Path) -> tuple[list[Event], SessionMetadata, list[str]]:
    events: list[Event] = []
    warnings: list[str] = []
    metadata = SessionMetadata()

    raw = path.read_text(encoding="utf-8-sig")
    # Strip garbage before XML declaration (some IDFX files have stray key names prepended)
    xml_start = raw.find("<?xml")
    if xml_start < 0:
        xml_start = raw.find("<log")
    if xml_start > 0:
        warnings.append(f"stripped {xml_start} bytes of garbage before XML declaration")
        raw = raw[xml_start:]
    sanitized = _sanitize_xml(raw)
    root = ET.fromstring(sanitized)

    session_el = root.find("session")
    if session_el is not None:
        for entry in session_el.findall("entry"):
            key = _text(entry.find("key"))
            val = _text(entry.find("value"))
            if key == "Participant":
                metadata.participant = val
            elif key == "Text Language":
                metadata.language = val
            elif key == "Session":
                metadata.session = val

    meta_el = root.find("meta")
    if meta_el is not None:
        for entry in meta_el.findall("entry"):
            key = _text(entry.find("key"))
            val = _text(entry.find("value"))
            if key == "__LogCreationDate":
                metadata.date = val
            elif key == "__MainDocument":
                metadata.filepath = val

    for event_el in root.iter("event"):
        event_id = int(event_el.get("id", "0"))
        event_type_str = event_el.get("type", "")

        try:
            if event_type_str == "keyboard":
                wordlog = event_el.find("part[@type='wordlog']")
                winlog = event_el.find("part[@type='winlog']")

                position = _int(wordlog.find("position") if wordlog is not None else None)
                doclength = _int(wordlog.find("documentLength") if wordlog is not None else None)

                key_name = _text(winlog.find("key") if winlog is not None else None)
                value = _text(winlog.find("value") if winlog is not None else None)
                start_time = _int(winlog.find("startTime") if winlog is not None else None)
                end_time = _int(winlog.find("endTime") if winlog is not None else None)

                output = _idfx_key_to_output(key_name, value)
                position, doclength = _pre_key_state(key_name, output, position, doclength)

                events.append(Event(
                    event_type=EventType.KEYBOARD,
                    event_id=event_id,
                    output=output,
                    char_production=0,
                    action_time=end_time - start_time if end_time > start_time else 0,
                    start_time=start_time,
                    end_time=end_time,
                    pause_location=0,
                    pause_location_full="",
                    pause_time=0,
                    position=position,
                    doclength=doclength,
                ))

            elif event_type_str == "replacement":
                wordlog = event_el.find("part[@type='wordlog']")
                if wordlog is not None:
                    start = _int(wordlog.find("start"))
                    end = _int(wordlog.find("end"))
                    newtext_el = wordlog.find("newtext")
                    newtext = (newtext_el.text or "") if newtext_el is not None else ""
                    output = f"[{start}:{end}] {newtext}"

                    events.append(Event(
                        event_type=EventType.REPLACEMENT,
                        event_id=event_id,
                        output=output,
                        char_production=0,
                        action_time=0,
                        start_time=0,
                        end_time=0,
                        pause_location=0,
                        pause_location_full="",
                        pause_time=0,
                        position=start,
                        doclength=0,
                    ))

            elif event_type_str in ("focus", "mouse"):
                continue

        except Exception as e:
            warnings.append(f"event {event_id}: skipped ({e})")

    return events, metadata, warnings
