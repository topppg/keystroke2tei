from __future__ import annotations

from pathlib import Path

from lxml import html

from keystroke2tei.models import Event, EventType, SessionMetadata

# Column indices in the event table (0-based)
_COL_ID = 0
_COL_TYPE = 1
_COL_OUTPUT = 2
_COL_POSITION = 3       # class="position"
_COL_POSITION_FULL = 4  # class="positionFull"
_COL_DOCLENGTH = 5      # class="doclength"
_COL_DOCLENGTH_FULL = 6 # class="doclengthFull"
_COL_CHAR_PROD = 7
_COL_START_TIME = 8
# 9 = StartClock (skip)
_COL_END_TIME = 10
# 11 = EndClock (skip)
_COL_ACTION_TIME = 12
_COL_PAUSE_TIME = 13
_COL_PAUSE_LOC = 14      # class="pauseLocation"
_COL_PAUSE_LOC_FULL = 15 # class="pauseLocationFull"
# 16 = IntervalFixedSize (skip)
# 17 = IntervalFixedNumber (skip)
_COL_X = 18
_COL_Y = 19
# 20-22 = Revision fields (skip)

_EXPECTED_COLS = 23


def _parse_int(val: str) -> int:
    if not val:
        return 0
    try:
        return int(val.strip())
    except ValueError:
        return 0


def _cell(tds: list, idx: int) -> str:
    if idx >= len(tds):
        return ""
    return (tds[idx].text_content() or "").strip()


def _extract_metadata(root: html.HtmlElement) -> SessionMetadata:
    meta: dict[str, str] = {}
    for table in root.findall(".//table"):
        for tr in table.findall(".//tr"):
            tds = tr.findall("td")
            if len(tds) == 2:
                key = (tds[0].text_content() or "").strip()
                val = (tds[1].text_content() or "").strip()
                meta[key] = val
        # Stop after first table (meta table)
        break
    return SessionMetadata(
        participant=meta.get("Participant", ""),
        language=meta.get("Text Language", ""),
        date=meta.get("Log Creation", ""),
        session=meta.get("Session", ""),
        filepath=meta.get("Logfile", ""),
    )


def parse_html(path: Path) -> tuple[list[Event], SessionMetadata, list[str]]:
    events: list[Event] = []
    warnings: list[str] = []

    tree = html.parse(str(path))
    root = tree.getroot()

    metadata = _extract_metadata(root)

    tables = root.findall(".//table")
    if len(tables) < 2:
        warnings.append("no event table found")
        return events, metadata, warnings

    tbody = tables[1].find(".//tbody")
    if tbody is None:
        warnings.append("event table has no tbody")
        return events, metadata, warnings

    for row_num, tr in enumerate(tbody.findall("tr"), start=1):
        tds = tr.findall("td")
        if len(tds) != _EXPECTED_COLS:
            warnings.append(f"row {row_num}: expected {_EXPECTED_COLS} cols, got {len(tds)}, skipped")
            continue

        et_val = _cell(tds, _COL_TYPE)
        if not et_val:
            continue
        try:
            et = EventType(et_val.lower())
        except ValueError:
            continue

        position = _parse_int(_cell(tds, _COL_POSITION)) or _parse_int(_cell(tds, _COL_POSITION_FULL))
        doclength = _parse_int(_cell(tds, _COL_DOCLENGTH)) or _parse_int(_cell(tds, _COL_DOCLENGTH_FULL))
        x_val = _parse_int(_cell(tds, _COL_X)) or None
        y_val = _parse_int(_cell(tds, _COL_Y)) or None

        try:
            events.append(Event(
                event_type=et,
                event_id=_parse_int(_cell(tds, _COL_ID)),
                output=_cell(tds, _COL_OUTPUT),
                char_production=_parse_int(_cell(tds, _COL_CHAR_PROD)),
                action_time=_parse_int(_cell(tds, _COL_ACTION_TIME)),
                start_time=_parse_int(_cell(tds, _COL_START_TIME)),
                end_time=_parse_int(_cell(tds, _COL_END_TIME)),
                pause_location=_parse_int(_cell(tds, _COL_PAUSE_LOC)),
                pause_location_full=_cell(tds, _COL_PAUSE_LOC_FULL),
                pause_time=_parse_int(_cell(tds, _COL_PAUSE_TIME)),
                position=position,
                doclength=doclength,
                x=x_val,
                y=y_val,
            ))
        except Exception as e:
            warnings.append(f"row {row_num}: skipped ({e})")

    return events, metadata, warnings
