from __future__ import annotations

import sys
from importlib.resources import files

import pytest
from lxml import etree

from keystroke2tei.cli import main
from keystroke2tei.converter import _ms_to_seq, convert
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
        '<meta><entry><key>__LogProgramVersion</key><value>9.6.0.0</value></entry></meta>'
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


def test_idfx_wordlog_pre_key_positions_replay_at_recorded_cursor(tmp_path):
    path = tmp_path / "pre-key.idfx"
    path.write_text(
        '<log>'
        '<meta><entry><key>__LogProgramVersion</key><value>9.6.0.0</value></entry></meta>'
        '<event id="1" type="keyboard">'
        '<part type="wordlog"><position>0</position><documentLength>0</documentLength></part>'
        '<part type="winlog"><key>VK_A</key><value>a</value><startTime>1000</startTime></part>'
        '</event>'
        '<event id="2" type="keyboard">'
        '<part type="wordlog"><position>1</position><documentLength>1</documentLength></part>'
        '<part type="winlog"><key>VK_B</key><value>b</value><startTime>2000</startTime></part>'
        '</event>'
        '<event id="3" type="keyboard">'
        '<part type="wordlog"><position>2</position><documentLength>2</documentLength></part>'
        '<part type="winlog"><key>VK_BACK</key><startTime>3000</startTime></part>'
        '</event>'
        '</log>',
        encoding="utf-8",
    )
    events, _, warnings = parse_idfx(path)
    assert warnings == []
    assert [(event.position, event.doclength) for event in events] == [(0, 0), (1, 1), (2, 2)]
    result = convert(events)
    assert result.final_text == "a"


def test_idfx_wordlog_7_post_key_positions_are_normalized(tmp_path):
    path = tmp_path / "post-key.idfx"
    path.write_text(
        '<log><meta><entry><key>__LogProgramVersion</key>'
        '<value>7.0.0.2</value></entry></meta>'
        '<event id="1" type="keyboard">'
        '<part type="wordlog"><position>1</position><documentLength>1</documentLength></part>'
        '<part type="winlog"><key>VK_A</key><value>a</value><startTime>1000</startTime></part>'
        '</event>'
        '<event id="2" type="keyboard">'
        '<part type="wordlog"><position>2</position><documentLength>2</documentLength></part>'
        '<part type="winlog"><key>VK_B</key><value>b</value><startTime>2000</startTime></part>'
        '</event>'
        '<event id="3" type="keyboard">'
        '<part type="wordlog"><position>1</position><documentLength>1</documentLength></part>'
        '<part type="winlog"><key>VK_BACK</key><startTime>3000</startTime></part>'
        '</event></log>', encoding="utf-8",
    )
    events, _, warnings = parse_idfx(path)
    assert warnings == []
    assert [(event.position, event.doclength) for event in events] == [
        (0, 0), (1, 1), (2, 2),
    ]
    assert convert(events).final_text == "a"


def test_idfx_empty_oem_key_does_not_create_text_or_shift_cursor(tmp_path):
    path = tmp_path / "dead-key.idfx"
    path.write_text(
        '<log>'
        '<meta><entry><key>__LogProgramVersion</key><value>9.6.0.0</value></entry></meta>'
        '<event id="1" type="keyboard">'
        '<part type="wordlog"><position>0</position><documentLength>0</documentLength></part>'
        '<part type="winlog"><key>VK_A</key><value>a</value><startTime>1000</startTime></part>'
        '</event>'
        '<event id="2" type="keyboard">'
        '<part type="wordlog"><position>1</position><documentLength>1</documentLength><replay>False</replay></part>'
        '<part type="winlog"><key>VK_OEM_6</key><value /><startTime>1500</startTime></part>'
        '</event>'
        '<event id="3" type="keyboard">'
        '<part type="wordlog"><position>1</position><documentLength>1</documentLength></part>'
        '<part type="winlog"><key>VK_B</key><value>b</value><startTime>2000</startTime></part>'
        '</event>'
        '</log>', encoding="utf-8",
    )
    events, _, warnings = parse_idfx(path)
    assert warnings == []
    assert events[1].output == "UNKNOWN"
    assert (events[1].position, events[1].doclength) == (1, 1)
    assert convert(events).final_text == "ab"


def test_idfx_selection_snapshot_and_non_replayed_backspace(tmp_path):
    path = tmp_path / "selection.idfx"
    path.write_text(
        '<log>'
        '<event id="1" type="replacement"><part type="wordlog">'
        '<start>0</start><end>3</end><newtext>abc</newtext>'
        '</part></event>'
        '<event id="2" type="selection"><part type="wordlog">'
        '<start>0</start><end>3</end></part></event>'
        '<event id="3" type="keyboard">'
        '<part type="wordlog"><position>0</position><documentLength>3</documentLength>'
        '<replay>False</replay></part>'
        '<part type="winlog"><key>VK_BACK</key><startTime>1000</startTime></part>'
        '</event>'
        '<event id="4" type="replacement"><part type="wordlog">'
        '<start>0</start><end>3</end><newtext>a</newtext>'
        '</part></event>'
        '<event id="5" type="selection"><part type="wordlog">'
        '<start>0</start><end>0</end></part></event>'
        '</log>', encoding="utf-8",
    )
    events, _, warnings = parse_idfx(path)
    assert warnings == []
    assert [event.event_id for event in events] == [1, 3, 4]
    assert events[1].replay is False
    result = convert(events, initial_text="abc")
    assert result.final_text == ""
    assert [action.deleted_text for action in result.actions if action.kind == "replace"] == ["abc"]


def test_idfx_same_length_replacement_followed_by_selection_is_preserved(tmp_path):
    path = tmp_path / "same-length.idfx"
    path.write_text(
        '<log><event id="1" type="replacement"><part type="wordlog">'
        '<start>0</start><end>3</end><newtext>dog</newtext>'
        '</part></event>'
        '<event id="2" type="selection"><part type="wordlog">'
        '<start>0</start><end>3</end></part></event></log>',
        encoding="utf-8",
    )
    events, _, warnings = parse_idfx(path)
    assert warnings == []
    assert [event.event_id for event in events] == [1]
    assert convert(events, initial_text="cat").final_document_text == "dog"


def test_idfx_french_dead_key_composes_following_vowel(tmp_path):
    path = tmp_path / "accent.idfx"
    path.write_text(
        '<log><meta><entry><key>__LogProgramVersion</key><value>9.6.0.0</value>'
        '</entry></meta><session><entry><key>Text Language</key><value>FR</value>'
        '</entry></session>'
        '<event id="1" type="keyboard">'
        '<part type="wordlog"><position>0</position><documentLength>0</documentLength>'
        '<replay>False</replay></part>'
        '<part type="winlog"><key>VK_OEM_6</key><value /><startTime>1000</startTime></part>'
        '</event>'
        '<event id="2" type="keyboard">'
        '<part type="wordlog"><position>0</position><documentLength>0</documentLength>'
        '<replay>True</replay></part>'
        '<part type="winlog"><key>VK_E</key><value>e</value><startTime>1100</startTime></part>'
        '</event></log>', encoding="utf-8",
    )
    events, _, _ = parse_idfx(path)
    assert events[1].output == "ê"
    assert convert(events).final_text == "ê"


def test_idfx_backspace_replacement_uses_post_delete_cursor(tmp_path):
    path = tmp_path / "backspace-range.idfx"
    path.write_text(
        '<log>'
        '<event id="1" type="keyboard">'
        '<part type="wordlog"><position>1</position><documentLength>4</documentLength>'
        '<replay>False</replay></part>'
        '<part type="winlog"><key>VK_BACK</key><startTime>1000</startTime></part>'
        '</event>'
        '<event id="2" type="replacement"><part type="wordlog">'
        '<start>1</start><end>4</end><newtext>.</newtext>'
        '</part></event>'
        '<event id="3" type="selection"><part type="wordlog">'
        '<start>0</start><end>0</end></part></event>'
        '</log>', encoding="utf-8",
    )
    events, _, _ = parse_idfx(path)
    assert events[1].output == "[0:4] "
    result = convert(events, initial_text=" abc")
    assert result.final_document_text == ""
    assert result.actions[0].deleted_text == " abc"


def test_idfx_clock_anchor_produces_valid_date_sequences_across_midnight(tmp_path):
    path = tmp_path / "clock.idfx"
    path.write_text(
        '<log><meta>'
        '<entry><key>__LogCreationDate</key><value>24/09/26 23:59:59.500</value></entry>'
        '<entry><key>__LogRelativeCreationDate</key><value>1000</value></entry>'
        '</meta>'
        '<event id="1" type="keyboard">'
        '<part type="wordlog"><position>1</position><documentLength>1</documentLength></part>'
        '<part type="winlog"><key>VK_A</key><value>a</value><startTime>1500</startTime></part>'
        '</event>'
        '<event id="2" type="keyboard">'
        '<part type="wordlog"><position>2</position><documentLength>2</documentLength></part>'
        '<part type="winlog"><key>VK_B</key><value>b</value><startTime>3000</startTime></part>'
        '</event>'
        '</log>', encoding="utf-8",
    )
    events, metadata, warnings = parse_idfx(path)
    assert warnings == []
    assert [_ms_to_seq(event.start_time) for event in events] == [
        "20260925000000", "20260925000001",
    ]
    result = convert(events, metadata=metadata)
    xml = write_tei(result.segments, metadata=metadata)
    assert 'seq="20260925000000"' in xml


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
