from __future__ import annotations

import json

from lxml import etree

from keystroke2tei import cli
from keystroke2tei.models import Event, EventType, SessionMetadata


def test_cli_writes_validated_review_report_and_applies_editorial_override(tmp_path, monkeypatch):
    source = tmp_path / "sample.csv"
    source.write_text("source log", encoding="utf-8")
    output = tmp_path / "sample.tei.xml"
    event = Event(EventType.KEYBOARD, 1, "a", 0, 0, 1000, 1000, 0, "", 0, 0, 0)
    monkeypatch.setattr(cli, "_is_klicke_csv", lambda _: False)
    monkeypatch.setattr(cli, "parse_csv", lambda _: ([event], SessionMetadata(), []))

    assert cli._process_single(source, output, False, False, review_report=True, validate=True)
    report_path = tmp_path / "sample.review.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["validation_issues"] == []

    root = etree.fromstring(output.read_bytes())
    add = root.find(".//{*}add")
    assert add.get("type") == "nt"

    override_path = tmp_path / "override.json"
    override_path.write_text(json.dumps({
        "format_version": 1,
        "overrides": [{
            "target": {"kind": "add", "evidence": "1", "occurrence": 0, "path": [0, 0]},
            "set": {"revision_type": "typo"},
        }],
    }), encoding="utf-8")
    assert cli._process_single(
        source, output, False, False, review_report=True,
        overrides_path=override_path, validate=True,
    )
    root = etree.fromstring(output.read_bytes())
    assert root.find(".//{*}add").get("type") == "typo"


def test_cli_validation_fails_when_source_cannot_supply_sequence(tmp_path, monkeypatch):
    source = tmp_path / "replacement.csv"
    source.write_text("source log", encoding="utf-8")
    output = tmp_path / "replacement.tei.xml"
    events = [
        Event(EventType.KEYBOARD, 1, "a", 0, 0, 1000, 1000, 0, "", 0, 0, 0),
        Event(EventType.REPLACEMENT, 2, "[0:1] b", 0, 0, 0, 0, 0, "", 0, 0, 1),
    ]
    monkeypatch.setattr(cli, "_is_klicke_csv", lambda _: False)
    monkeypatch.setattr(cli, "parse_csv", lambda _: (events, SessionMetadata(), []))

    assert not cli._process_single(source, output, False, False, validate=True)
    assert output.is_file()
