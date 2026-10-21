from __future__ import annotations

import sys
from importlib.resources import files

import pytest
from lxml import etree

from keystroke2tei.cli import main
from keystroke2tei.converter import convert
from keystroke2tei.idfx_parser import parse_idfx
from keystroke2tei.klicke_parser import parse_klicke
from keystroke2tei.models import Event, EventType
from keystroke2tei.writer import write_tei


def test_classification_template_available():
    assert files("keystroke2tei").joinpath("prompts/classify_revisions.j2").is_file()


def test_whitespace_only_addition_is_preserved():
    event = Event(EventType.KEYBOARD, 1, "SPACE", 0, 0, 100, 100, 0, "", 0, 0, 0)
    result = convert([event])
    body = etree.fromstring(write_tei(result.segments).encode()).find(".//{*}body")
    assert result.final_text == " "
    assert body.find(".//{*}add").text == " "


def test_klicke_text_change_preserves_spaces_and_quotes(tmp_path):
    path = tmp_path / "log.csv"
    path.write_text(
        'DownEvent,TextChange,Activity,CursorPosition,DownTime,UpTime,PauseTime\n'
        'x,"a ",Input,2,1,2,0\n'
        'x,"""b""",Input,5,3,4,0\n',
        encoding="utf-8",
    )
    events, _, warnings = parse_klicke(path)
    assert warnings == []
    assert [(event.output, event.position) for event in events] == [("a ", 0), ('"b"', 2)]
    assert convert(events).final_text == 'a "b"'


def test_idfx_replacement_preserves_spaces_and_uses_no_stale_doclength(tmp_path):
    path = tmp_path / "log.idfx"
    path.write_text(
        '<log>'
        '<event id="1" type="keyboard">'
        '<part type="wordlog"><position>0</position><documentLength>9</documentLength></part>'
        '<part type="winlog"><key>VK_A</key><value>a</value><startTime>1</startTime></part>'
        '</event>'
        '<event id="2" type="replacement">'
        '<part type="wordlog"><start>0</start><end>1</end><newtext> b </newtext></part>'
        '</event>'
        '</log>',
        encoding="utf-8",
    )
    events, _, warnings = parse_idfx(path)
    assert warnings == []
    assert events[1].output == "[0:1]  b "
    assert events[1].doclength == 0


def test_batch_rejects_single_output_file(tmp_path, monkeypatch):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.touch()
    second.touch()
    output = tmp_path / "out.xml"
    monkeypatch.setattr(sys, "argv", ["keystroke2tei", str(first), str(second), "-o", str(output)])
    with pytest.raises(SystemExit, match="2"):
        main()
    assert not output.exists()


def test_batch_rejects_colliding_input_stems(tmp_path, monkeypatch):
    csv_path = tmp_path / "same.csv"
    idfx_path = tmp_path / "same.idfx"
    csv_path.touch()
    idfx_path.touch()
    monkeypatch.setattr(
        sys, "argv", ["keystroke2tei", str(csv_path), str(idfx_path), "-o", str(tmp_path / "out")],
    )
    with pytest.raises(SystemExit, match="2"):
        main()
