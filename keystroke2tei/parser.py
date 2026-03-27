from __future__ import annotations

import csv
from pathlib import Path

from keystroke2tei.models import Event, EventType, SessionMetadata


def _parse_int(val: str) -> int:
    if not val:
        return 0
    try:
        return int(val)
    except ValueError:
        return 0


def _parse_event_type(val: str) -> EventType:
    return EventType(val.strip().lower())


def _detect_encoding(path: Path) -> str:
    bom = path.read_bytes()[:2]
    if bom in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            path.read_text(encoding=enc)
            return enc
        except (UnicodeDecodeError, ValueError):
            continue
    return "latin-1"


def _detect_delimiter(path: Path, encoding: str) -> str:
    with open(path, encoding=encoding) as f:
        sample = f.read(4096)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        return dialect.delimiter
    except csv.Error:
        return ";"


def _extract_metadata(row: dict[str, str]) -> SessionMetadata:
    return SessionMetadata(
        participant=row.get("sessionID_Participant__S_", "").strip(),
        language=row.get("sessionID_Text_Language__SL_", "").strip(),
        date=row.get("sessionID_LogCreationDate__S_", "").strip(),
        session=row.get("sessionID_Session__S_", "").strip(),
        filepath=row.get("sessionID_filepath__S_", "").strip(),
    )


def parse_csv(path: Path) -> tuple[list[Event], SessionMetadata, list[str]]:
    events: list[Event] = []
    warnings: list[str] = []
    metadata = SessionMetadata()

    encoding = _detect_encoding(path)
    delimiter = _detect_delimiter(path, encoding)

    with open(path, encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row_num, row in enumerate(reader, start=2):
            if not metadata.participant:
                metadata = _extract_metadata(row)

            try:
                et_val = row.get("event_type__E_", "")
                if not et_val:
                    continue
                et = _parse_event_type(et_val)
            except ValueError:
                continue

            try:
                events.append(Event(
                    event_type=et,
                    event_id=_parse_int(row.get("event_id__E_", "")),
                    output=row.get("event_output__E_", ""),
                    char_production=_parse_int(row.get("event_charProduction__E_", "")),
                    action_time=_parse_int(row.get("event_actionTime__E_", "")),
                    start_time=_parse_int(row.get("event_startTime__E_", "")),
                    end_time=_parse_int(row.get("event_endTime__E_", "")),
                    pause_location=_parse_int(row.get("event_pauseLocation__E_", "")),
                    pause_location_full=row.get("event_pauseLocationFull__E_", ""),
                    pause_time=_parse_int(row.get("event_pauseTime__E_", "")),
                    position=(
                        _parse_int(row.get("event_position__E_", ""))
                        or _parse_int(row.get("event_positionFull__E_", ""))
                    ),
                    doclength=(
                        _parse_int(row.get("event_doclength__E_", ""))
                        or _parse_int(row.get("event_doclengthFull__E_", ""))
                    ),
                    x=_parse_int(row.get("event_x__E_", "")) or None,
                    y=_parse_int(row.get("event_y__E_", "")) or None,
                ))
            except Exception as e:
                warnings.append(f"row {row_num}: skipped ({e})")

    return events, metadata, warnings
