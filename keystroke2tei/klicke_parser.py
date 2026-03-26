from __future__ import annotations

import csv
from pathlib import Path

from keystroke2tei.models import Event, EventType, SessionMetadata


def _parse_int(val: str) -> int:
    val = val.strip().strip('"')
    if not val:
        return 0
    try:
        return int(val)
    except ValueError:
        return 0


def parse_klicke(path: Path) -> tuple[list[Event], SessionMetadata, list[str]]:
    events: list[Event] = []
    warnings: list[str] = []
    metadata = SessionMetadata(
        participant=path.stem,
        filepath=str(path),
    )

    from keystroke2tei.parser import _detect_encoding
    encoding = _detect_encoding(path)

    with open(path, encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            try:
                down_event = row.get("DownEvent", "").strip().strip('"')
                text_change = row.get("TextChange", "").strip().strip('"')
                activity = row.get("Activity", "").strip().strip('"')
                cursor_pos = _parse_int(row.get("CursorPosition", "0"))
                down_time = _parse_int(row.get("DownTime", "0"))
                up_time = _parse_int(row.get("UpTime", "0"))
                pause_time = _parse_int(row.get("PauseTime", "0"))

                if activity == "Nonproduction" and down_event in ("Shift", "Control", "Alt"):
                    continue

                if down_event == "Leftclick" or down_event == "Rightclick":
                    events.append(Event(
                        event_type=EventType.MOUSE,
                        event_id=row_num,
                        output=f"LEFT Click" if down_event == "Leftclick" else "RIGHT Click",
                        char_production=0,
                        action_time=up_time - down_time if up_time > down_time else 0,
                        start_time=down_time,
                        end_time=up_time,
                        pause_location=0,
                        pause_location_full="",
                        pause_time=pause_time,
                        position=cursor_pos,
                        doclength=0,
                    ))
                    continue

                if activity == "Remove/Cut" or down_event == "Backspace":
                    events.append(Event(
                        event_type=EventType.KEYBOARD,
                        event_id=row_num,
                        output="BACK",
                        char_production=0,
                        action_time=up_time - down_time if up_time > down_time else 0,
                        start_time=down_time,
                        end_time=up_time,
                        pause_location=0,
                        pause_location_full="",
                        pause_time=pause_time,
                        position=cursor_pos + 1,
                        doclength=0,
                    ))
                    continue

                if down_event == "Delete":
                    events.append(Event(
                        event_type=EventType.KEYBOARD,
                        event_id=row_num,
                        output="DELETE",
                        char_production=0,
                        action_time=up_time - down_time if up_time > down_time else 0,
                        start_time=down_time,
                        end_time=up_time,
                        pause_location=0,
                        pause_location_full="",
                        pause_time=pause_time,
                        position=cursor_pos,
                        doclength=0,
                    ))
                    continue

                if activity == "Input" and text_change and text_change != "NoChange":
                    output = text_change
                    if output == " ":
                        output = "SPACE"

                    pos = max(0, cursor_pos - len(text_change))

                    events.append(Event(
                        event_type=EventType.KEYBOARD,
                        event_id=row_num,
                        output=output,
                        char_production=0,
                        action_time=up_time - down_time if up_time > down_time else 0,
                        start_time=down_time,
                        end_time=up_time,
                        pause_location=0,
                        pause_location_full="",
                        pause_time=pause_time,
                        position=pos,
                        doclength=0,
                    ))
                    continue

                if down_event in ("Space", "Enter", "Tab"):
                    mapping = {"Space": "SPACE", "Enter": "RETURN", "Tab": "TAB"}
                    events.append(Event(
                        event_type=EventType.KEYBOARD,
                        event_id=row_num,
                        output=mapping[down_event],
                        char_production=0,
                        action_time=up_time - down_time if up_time > down_time else 0,
                        start_time=down_time,
                        end_time=up_time,
                        pause_location=0,
                        pause_location_full="",
                        pause_time=pause_time,
                        position=max(0, cursor_pos - 1),
                        doclength=0,
                    ))

            except Exception as e:
                warnings.append(f"row {row_num}: skipped ({e})")

    return events, metadata, warnings
