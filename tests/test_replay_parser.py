from __future__ import annotations

import json

from keystroke2tei.cli import _process_single
from keystroke2tei.converter import WritingAction, convert
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


def test_editorial_context_is_captured_before_the_edit():
    event = Event(
        EventType.REPLACEMENT, 1, "[6:11] Earth", 0, 0, 0, 0, 0, "", 0, 6, 12,
    )
    result = convert([event], initial_text="Hello world.")
    assert result.actions[0].context_at_edit == "Hello |world."
    assert result.final_document_text == "Hello Earth."


def test_editorial_candidates_follow_source_actions_and_include_edit_time_context():
    from keystroke2tei.classifier import _build_revisions_text, _order_by_source

    earlier = TEINode(NodeKind.DEL, text="one", revision_type="typo", evidence="10")
    later = TEINode(NodeKind.DEL, text="two", revision_type="context", evidence="20")
    events = [
        Event(EventType.KEYBOARD, event_id, "BACK", 0, 0, 0, 0, 0, "", 0, 0, 0)
        for event_id in (10, 20)
    ]
    actions = [
        WritingAction("delete", 0, deleted_text="one", event=events[0],
                      context_at_edit="before|one"),
        WritingAction("delete", 0, deleted_text="two", event=events[1],
                      context_at_edit="before|two"),
    ]
    ordered = _order_by_source([(1, later), (2, earlier)], actions)
    candidates = [json.loads(line) for line in _build_revisions_text(ordered, actions).splitlines()]
    assert [item["source_evidence"] for item in candidates] == ["10", "20"]
    assert [item["id"] for item in candidates] == [1, 2]
    assert [item["context_before_edit"] for item in candidates] == [
        "before|one", "before|two",
    ]


def test_new_text_after_revision_is_selected_in_source_order():
    from keystroke2tei.classifier import _collect_classifiable_nodes

    deletion = TEINode(NodeKind.DEL, text="old", revision_type="typo", evidence="10")
    addition = TEINode(NodeKind.ADD, text="new", revision_type="nt", evidence="20")
    segment = TEINode(NodeKind.SEG, children=[addition, deletion])
    events = [
        Event(EventType.KEYBOARD, event_id, "", 0, 0, 0, 0, 0, "", 0, 0, 0)
        for event_id in (10, 20)
    ]
    actions = [
        WritingAction("delete", 0, event=events[0]),
        WritingAction("insert", 0, event=events[1]),
    ]
    assert [node.evidence for _, node in _collect_classifiable_nodes([segment], actions)] == [
        "10", "20",
    ]


def test_compound_continuations_are_not_sent_for_base_reclassification():
    from keystroke2tei.classifier import _collect_classifiable_nodes

    compound = TEINode(NodeKind.ADD, text="more", revision_type="nt|continue")
    existing_mod = TEINode(NodeKind.MOD, text="later", revision_type="continue|continue")
    assert _collect_classifiable_nodes([compound, existing_mod]) == []


def test_ai_can_keep_new_text_and_cannot_relabel_modification(monkeypatch):
    from keystroke2tei import classifier

    addition = TEINode(NodeKind.ADD, text="new", revision_type="pre-context", evidence="1")
    modification = TEINode(NodeKind.MOD, text="more", revision_type="continue", evidence="2")
    monkeypatch.setattr(
        classifier, "_call_openrouter",
        lambda prompt: '[{"id": 1, "type": "nt"}, {"id": 2, "type": "typo"}]',
    )
    assert classifier.reclassify_with_llm([addition, modification], "") == 1
    assert addition.revision_type == "nt"
    assert modification.revision_type == "continue"
