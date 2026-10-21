from __future__ import annotations

import pytest

from keystroke2tei.converter import (
    RevisionEpisode,
    WritingAction,
    _build_tei_tree,
    _segment_by_sentences,
    _visible_text,
    convert,
)
from keystroke2tei.models import Event, EventType, NodeKind


def event(number: int, output: str, position: int, length: int,
          kind: EventType = EventType.KEYBOARD) -> Event:
    return Event(kind, number, output, 0, 0, number * 1000, number * 1000,
                 0, "", 0, position, length)


def test_replacement_text_is_assigned_to_each_final_sentence() -> None:
    events = [event(i, char, i - 1, i - 1) for i, char in enumerate("old", 1)]
    events.append(event(4, "[0:3] New. Second sentence.", 0, 3,
                        EventType.REPLACEMENT))

    result = convert(events)

    assert result.final_text == "New. Second sentence."
    assert "".join(_visible_text(seg) for seg in result.segments) == result.final_text
    assert len(result.segments) == 2
    assert not any("TEI reading text differs" in d.message for d in result.diagnostics)


def test_replacement_split_preserves_deleted_text_only_once() -> None:
    action = WritingAction(
        "replace", 0, text="A. B.", deleted_text="old",
        final_positions=list(range(5)),
    )
    groups = _segment_by_sentences(
        [RevisionEpisode(actions=[action], is_revision=True)], "A. B.",
    )

    assert [ep.actions[0].text for group in groups for ep in group] == ["A. ", "B."]
    assert [ep.actions[0].deleted_text for group in groups for ep in group] == ["old", ""]


def test_paste_spanning_sentences_keeps_source_classification() -> None:
    action = WritingAction(
        "paste", 0, text="A. B.", deleted_text="source",
        final_positions=list(range(5)),
    )
    groups = _segment_by_sentences([RevisionEpisode(actions=[action])], "A. B.")

    assert [ep.actions[0].text for group in groups for ep in group] == ["A. ", "B."]
    assert all(ep.actions[0].deleted_text == "source"
               for group in groups for ep in group)


@pytest.mark.parametrize("first_pos, second_pos", [(0, 2), (2, 0)])
def test_raw_adjacent_runs_stay_separate_when_final_positions_are_not_adjacent(
    first_pos: int, second_pos: int,
) -> None:
    first = RevisionEpisode(actions=[WritingAction(
        "insert", 0, "A", event=event(1, "A", 0, 0), final_positions=[first_pos],
    )])
    second = RevisionEpisode(actions=[WritingAction(
        "insert", 1, "C", event=event(2, "C", 1, 1), final_positions=[second_pos],
    )])

    segment = _build_tei_tree([first, second])

    additions = [child for child in segment.children if child.kind == NodeKind.ADD]
    assert len(additions) == 2
    assert [node.evidence for node in additions] == ["1", "2"]


def test_replacement_fragments_retain_original_event_evidence() -> None:
    events = [event(1, "a", 0, 0), event(2, "[0:1] A. B.", 0, 1,
                                           EventType.REPLACEMENT)]
    result = convert(events)
    def visit(node):
        yield node
        for child in node.children:
            yield from visit(child)

    additions = [node for seg in result.segments for node in visit(seg)
                 if node.kind == NodeKind.ADD and node.evidence == "2"]
    assert len(additions) == 2
    assert "".join(_visible_text(node) for node in additions) == result.final_text
