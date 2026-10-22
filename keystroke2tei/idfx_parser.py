from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from keystroke2tei.models import Event, EventType, SessionMetadata

_INVALID_XML_CHAR = re.compile(r"&#x([0-9a-fA-F]+);")
_FRENCH_CIRCUMFLEX = str.maketrans("aeiouAEIOU", "âêîôûÂÊÎÔÛ")


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
    # OEM keys are keyboard-layout dependent. An empty value records no text;
    # using the key name as text invents characters and shifts the cursor.
    if key.startswith("VK_OEM_") and not value:
        return "UNKNOWN"
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


def _pre_key_state(
    key: str, output: str, position: int, doclength: int, *, already_pre: bool = False,
) -> tuple[int, int]:
    """Normalize Wordlog cursor and length to their pre-key values."""
    if already_pre:
        return position, doclength
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
    wordlog_pre_key = False
    relative_creation_ms: int | None = None
    local_creation: datetime | None = None
    pending_circumflex = False

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
                try:
                    local_creation = datetime.strptime(val, "%d/%m/%y %H:%M:%S.%f")
                except ValueError:
                    warnings.append("invalid __LogCreationDate; retaining relative event times")
            elif key == "__LogRelativeCreationDate":
                try:
                    relative_creation_ms = int(val)
                except ValueError:
                    warnings.append("invalid __LogRelativeCreationDate; retaining relative event times")
            elif key == "__MainDocument":
                metadata.filepath = val
            elif key == "__LogProgramVersion":
                major = val.split(".", 1)[0]
                wordlog_pre_key = major.isdigit() and int(major) >= 9

    def wall_clock_ms(relative_ms: int) -> int:
        if not relative_ms or local_creation is None or relative_creation_ms is None:
            return relative_ms
        wall_time = local_creation + timedelta(milliseconds=relative_ms - relative_creation_ms)
        delta = wall_time - datetime(1970, 1, 1)
        return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000

    source_events = list(root.iter("event"))
    for event_index, event_el in enumerate(source_events):
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
                if pending_circumflex:
                    if len(value) == 1 and value in "aeiouAEIOU":
                        value = value.translate(_FRENCH_CIRCUMFLEX)
                    pending_circumflex = False
                if key_name == "VK_OEM_6" and not value and metadata.language.upper() == "FR":
                    pending_circumflex = True
                start_time = _int(winlog.find("startTime") if winlog is not None else None)
                end_time = _int(winlog.find("endTime") if winlog is not None else None)

                output = _idfx_key_to_output(key_name, value)
                position, doclength = _pre_key_state(
                    key_name, output, position, doclength, already_pre=wordlog_pre_key)

                events.append(Event(
                    event_type=EventType.KEYBOARD,
                    event_id=event_id,
                    output=output,
                    char_production=0,
                    action_time=end_time - start_time if end_time > start_time else 0,
                    start_time=wall_clock_ms(start_time),
                    end_time=wall_clock_ms(end_time),
                    pause_location=0,
                    pause_location_full="",
                    pause_time=0,
                    position=position,
                    doclength=doclength,
                    replay=(wordlog is None or _text(wordlog.find("replay")) != "False"),
                ))

            elif event_type_str == "replacement":
                wordlog = event_el.find("part[@type='wordlog']")
                if wordlog is not None:
                    start = _int(wordlog.find("start"))
                    end = _int(wordlog.find("end"))
                    newtext_el = wordlog.find("newtext")
                    newtext = (newtext_el.text or "") if newtext_el is not None else ""
                    if event_index > 0:
                        preceding = source_events[event_index - 1]
                        preceding_log = preceding.find("part[@type='wordlog']")
                        if (
                            preceding.get("type") == "keyboard"
                            and preceding_log is not None
                            and _text(preceding_log.find("replay")) == "False"
                            and preceding.findtext("part[@type='winlog']/key") == "VK_BACK"
                        ):
                            # A non-replayed backspace removes the selection.
                            # Wordlog's newtext is a stale character snapshot.
                            newtext = ""
                            if event_index + 1 < len(source_events):
                                after = source_events[event_index + 1]
                                after_log = after.find("part[@type='wordlog']")
                                if after.get("type") == "selection" and after_log is not None:
                                    cursor_start = _int(after_log.find("start"))
                                    cursor_end = _int(after_log.find("end"))
                                    if cursor_start == cursor_end and cursor_start < start:
                                        # Wordlog sometimes omits the character
                                        # immediately before the selected range
                                        # from the replacement span. The cursor
                                        # after deletion records the full extent.
                                        start = cursor_start
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
