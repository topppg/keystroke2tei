from __future__ import annotations

import json

from keystroke2tei.cli import _process_single
from keystroke2tei.converter import convert
from keystroke2tei.models import Event, EventType, NodeKind, TEINode
from keystroke2tei.replay_parser import parse_replay_html


def test_replay_supplies_baseline_and_independent_final_text(tmp_path):
    path = tmp_path / "replay.html"
    data = {
        "T": "abX",
        "X": [[1, 0, 1, 0], [2, 1, -1, 1]],
        "S": {"t": [0, 100]},
    }
    path.write_text(
        '<html><script id="data" type="application/json">'
        + json.dumps(data) + '</script></html>', encoding="utf-8",
    )
    replay = parse_replay_html(path)
    assert replay.initial_text == "ab"
    assert replay.final_document_text == "aX"
    assert replay.final_added_text == "X"
    assert replay.inserted_chars == 1
    assert replay.deleted_initial_chars == 1


def test_replacement_preserves_leading_space_in_new_text():
    event = Event(
        EventType.REPLACEMENT, 1, "[0:2]  ", 0, 0, 0, 0, 0, "", 0, 0, 0,
    )
    result = convert([event], initial_text="ab")
    assert result.final_text == " "
    assert result.actions[0].deleted_text == "ab"


def test_idfx_conversion_uses_replay_baseline_and_reports_match(tmp_path):
    replay_path = tmp_path / "replay.html"
    replay_path.write_text(
        '<script id="data" type="application/json">'
        + json.dumps({
            "T": "abX",
            "X": [[1, 0, 1, 0], [2, 1, -1, 1]],
            "S": {"t": [0, 100]},
        }) + '</script>', encoding="utf-8",
    )
    idfx_path = tmp_path / "session.idfx"
    idfx_path.write_text(
        '<log>'
        '<meta><entry><key>__LogProgramVersion</key><value>9.6.0.0</value></entry></meta>'
        '<event id="1" type="keyboard">'
        '<part type="wordlog"><position>2</position><documentLength>2</documentLength>'
        '<replay>True</replay></part>'
        '<part type="winlog"><key>VK_BACK</key><startTime>1000</startTime></part>'
        '</event>'
        '<event id="2" type="keyboard">'
        '<part type="wordlog"><position>1</position><documentLength>1</documentLength>'
        '<replay>True</replay></part>'
        '<part type="winlog"><key>VK_X</key><value>X</value><startTime>2000</startTime></part>'
        '</event></log>', encoding="utf-8",
    )
    output_path = tmp_path / "session.tei.xml"
    assert _process_single(
        idfx_path, output_path, verbose=False, write_stats=False,
        review_report=True, replay_path=replay_path,
    )
    assert ">b</del>" in output_path.read_text()
    report = json.loads((tmp_path / "session.review.json").read_text())
    assert report["replay_comparison"]["final_typed_text_matches"] is True
    assert report["replay_comparison"]["final_document_matches"] is True
    assert report["replay_comparison"]["edit_counts_match"] is True


def test_ai_continue_does_not_turn_a_deletion_into_a_modification(monkeypatch):
    from keystroke2tei import classifier

    deletion = TEINode(NodeKind.DEL, text="old", revision_type="context")
    monkeypatch.setattr(classifier, "_call_openrouter", lambda prompt: '[{"id": 1, "type": "continue"}]')
    assert classifier.reclassify_with_llm([deletion], "") == 0
    assert deletion.kind == NodeKind.DEL
    assert deletion.revision_type == "context"
