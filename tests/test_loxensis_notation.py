from __future__ import annotations

from lxml import etree

from keystroke2tei.converter import (
    RevisionEpisode, WritingAction, _group_into_episodes, _segment_by_sentences, convert,
)
from keystroke2tei.models import Event, EventType
from keystroke2tei.writer import write_tei

NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def event(i: int, output: str, pos: int, length: int, kind: EventType = EventType.KEYBOARD) -> Event:
    return Event(kind, i, output, 0, 0, i * 1000, i * 1000, 0, "", 0, pos, length)


def typed(text: str) -> list[Event]:
    return [event(i, ch, i - 1, i - 1) for i, ch in enumerate(text, 1)]


def tree(events: list[Event]) -> etree._Element:
    result = convert(events)
    return etree.fromstring(write_tei(result.segments, focus_sources=result.focus_sources).encode())


def test_each_continuously_typed_sentence_gets_a_segment():
    root = tree(typed("Hi. Bye."))
    segments = root.xpath(".//tei:seg", namespaces=NS)
    assert ["".join(seg.itertext()).strip() for seg in segments] == ["Hi.", "Bye."]


def test_sentence_boundaries_track_insertions_made_later():
    events = typed("Hi. Bye.") + [
        event(9, "LEFT Click", 1, 8, EventType.MOUSE),
        event(10, "X", 1, 8),
    ]
    root = tree(events)
    segments = root.xpath(".//tei:seg", namespaces=NS)
    assert len(segments) == 2
    assert segments[0].xpath(".//tei:add[@type='context']", namespaces=NS)
    assert not segments[1].xpath(".//tei:add[@type='context']", namespaces=NS)
    assert ["".join(seg.itertext()).strip() for seg in segments] == ["HXi.", "Bye."]


def test_unfinished_sentence_insertion_is_pre_context():
    events = typed("Hello") + [
        event(6, "LEFT Click", 2, 5, EventType.MOUSE),
        event(7, "X", 2, 5),
    ]
    root = tree(events)
    assert root.xpath(".//tei:add[@type='pre-context']", namespaces=NS)


def test_word_change_is_pre_context_and_spelling_correction_is_typo():
    word_change = typed("you") + [
        event(4, "BACK", 3, 3), event(5, "BACK", 2, 2), event(6, "BACK", 1, 1),
        event(7, "w", 0, 0), event(8, "e", 1, 1),
    ]
    spelling = typed("aper") + [
        event(5, "BACK", 4, 4), event(6, "BACK", 3, 3),
        event(7, "BACK", 2, 2), event(8, "BACK", 1, 1),
    ] + [event(i, ch, i - 9, i - 9) for i, ch in enumerate("paper", 9)]
    assert tree(word_change).xpath(".//tei:del[@type='pre-context']", namespaces=NS)
    assert tree(spelling).xpath(".//tei:del[@type='typo']", namespaces=NS)


def test_relocated_capitalization_can_be_a_typo():
    events = typed("he") + [
        event(3, "LEFT Click", 0, 2, EventType.MOUSE),
        event(4, "DELETE", 0, 2),
        event(5, "H", 0, 1),
    ]
    root = tree(events)
    assert root.xpath(".//tei:del[@type='typo']", namespaces=NS)
    assert root.xpath(".//tei:add[@type='typo']", namespaces=NS)


def test_source_markup_has_manual_attributes():
    root = tree([event(1, "Chrome", 0, 0, EventType.FOCUS)])
    assert root.xpath(".//tei:body/tei:p[@source='keystrokes']", namespaces=NS)
    focus = root.xpath(".//tei:body/tei:p[@source='sources']/tei:add", namespaces=NS)[0]
    assert focus.get("seq") == "000001"
    assert focus.get("evidence") == "1"
    assert focus.find("tei:media", namespaces=NS).get("url") == "Chrome"
    assert focus.find("tei:media", namespaces=NS).get("mimeType") == "Application"


def test_focus_name_with_spaces_has_schema_safe_url():
    root = tree([event(1, "Word Log", 0, 0, EventType.FOCUS)])
    media = root.xpath(".//tei:media", namespaces=NS)[0]
    assert media.get("url") == "Word%20Log"
    assert media.find("tei:desc", namespaces=NS).text == "Word Log"


def test_unrepresentable_unique_evidence_is_reported():
    result = convert([
        event(1, "a", 0, 0),
        event(2, "[0:1] b", 0, 1, EventType.REPLACEMENT),
    ])
    assert any("repeated @evidence=2" in d.message for d in result.diagnostics)


def test_missing_source_timestamp_is_reported():
    replacement = event(2, "[0:1] b", 0, 1, EventType.REPLACEMENT)
    replacement.start_time = 0
    result = convert([event(1, "a", 0, 0), replacement])
    assert any("missing @seq" in d.message for d in result.diagnostics)


def test_recorded_zero_timestamp_is_valid_sequence():
    first = event(1, "a", 0, 0)
    first.start_time = 0
    root = tree([first])
    assert root.xpath(".//tei:add", namespaces=NS)[0].get("seq") == "000000"


def test_linebreaks_before_deletion_remain_in_reading_text():
    events = typed("A. B") + [
        event(5, "LEFT Click", 2, 4, EventType.MOUSE),
        event(6, "RETURN", 2, 4),
        event(7, "RETURN", 3, 5),
        event(8, "DELETE", 4, 6),
    ]
    result = convert(events)
    root = etree.fromstring(write_tei(result.segments).encode())
    assert len(root.xpath(".//tei:lb", namespaces=NS)) == 2
    assert result.final_text == "A.\n\nB"
    assert not any("TEI reading text differs" in d.message for d in result.diagnostics)


def test_linebreak_followed_by_delete_starts_a_new_episode():
    episodes = _group_into_episodes(convert([
        event(1, "A", 0, 0), event(2, "RETURN", 1, 1),
        event(3, "BACK", 2, 2),
    ]).actions)
    assert [a.kind for a in episodes[-2].actions] == ["insert", "linebreak"]
    assert [a.kind for a in episodes[-1].actions] == ["delete"]


def test_insertion_run_splits_around_later_inserted_character():
    episode = RevisionEpisode(actions=[
        WritingAction("insert", 0, "a", final_positions=[0]),
        WritingAction("insert", 1, "c", final_positions=[2]),
    ])
    groups = _segment_by_sentences([episode], "abc")
    assert [part.net_text for part in groups[0]] == ["a", "c"]
    assert groups[0][1].force_new_add
