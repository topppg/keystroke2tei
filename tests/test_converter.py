from __future__ import annotations

from pathlib import Path

from keystroke2tei.converter import CharMap, _classify_key, _process_events, _group_into_episodes, convert
from keystroke2tei.models import Event, EventType


def _kb(event_id: int, output: str, position: int, doclength: int, start_time: int = 0) -> Event:
    return Event(
        event_type=EventType.KEYBOARD, event_id=event_id, output=output,
        char_production=0, action_time=0, start_time=start_time, end_time=start_time,
        pause_location=0, pause_location_full="", pause_time=0,
        position=position, doclength=doclength,
    )


def _mouse(event_id: int, output: str, position: int, doclength: int, start_time: int = 0) -> Event:
    return Event(
        event_type=EventType.MOUSE, event_id=event_id, output=output,
        char_production=0, action_time=0, start_time=start_time, end_time=start_time,
        pause_location=0, pause_location_full="", pause_time=0,
        position=position, doclength=doclength,
    )


def _replacement(event_id: int, output: str, position: int, doclength: int, start_time: int = 0) -> Event:
    return Event(
        event_type=EventType.REPLACEMENT, event_id=event_id, output=output,
        char_production=0, action_time=0, start_time=start_time, end_time=start_time,
        pause_location=0, pause_location_full="", pause_time=0,
        position=position, doclength=doclength,
    )


# --- CharMap ---

class TestCharMap:
    def test_insert_and_get_text(self):
        cm = CharMap()
        cm.insert(0, "a")
        cm.insert(1, "b")
        cm.insert(2, "c")
        assert cm.get_text() == "abc"
        assert cm.length == 3

    def test_insert_at_middle(self):
        cm = CharMap()
        cm.insert(0, "a")
        cm.insert(1, "c")
        cm.insert(1, "b")
        assert cm.get_text() == "abc"

    def test_delete_known_char(self):
        cm = CharMap()
        cm.insert(0, "a")
        cm.insert(1, "b")
        deleted = cm.delete(0)
        assert deleted == "a"
        assert cm.get_text() == "b"

    def test_delete_unknown_char(self):
        cm = CharMap()
        cm.pad_to(3)
        deleted = cm.delete(1)
        assert deleted == ""
        assert cm.length == 2

    def test_pad_only_grows(self):
        cm = CharMap()
        cm.insert(0, "x")
        cm.pad_to(5)
        assert cm.length == 5
        cm.pad_to(3)  # should not shrink
        assert cm.length == 5

    def test_get_text_skips_none(self):
        cm = CharMap()
        cm.insert(0, "a")
        cm.pad_to(3)
        cm.insert(3, "b")
        assert cm.get_text() == "ab"

    def test_replace_range(self):
        cm = CharMap()
        for ch in "hello":
            cm.insert(cm.length, ch)
        old = cm.replace_range(1, 4, "XY")
        assert old == "ell"
        assert cm.get_text() == "hXYo"

    def test_replace_range_with_unknowns(self):
        cm = CharMap()
        cm.insert(0, "a")
        cm.pad_to(4)
        cm.insert(4, "e")
        old = cm.replace_range(1, 4, "bc")
        assert old == ""  # all unknowns
        assert cm.get_text() == "abce"


# --- _classify_key ---

class TestClassifyKey:
    def test_single_char(self):
        assert _classify_key("a") == "a"
        assert _classify_key("Z") == "Z"
        assert _classify_key("é") == "é"

    def test_special_keys(self):
        assert _classify_key("SPACE") == " "
        assert _classify_key("BACK") == "BACK"
        assert _classify_key("DELETE") == "DELETE"
        assert _classify_key("RETURN") == "\n"
        assert _classify_key("TAB") == "\t"

    def test_nav_keys(self):
        assert _classify_key("LEFT") == "NAV"
        assert _classify_key("RIGHT") == "NAV"
        assert _classify_key("HOME") == "NAV"
        assert _classify_key("END") == "NAV"

    def test_modifier(self):
        assert _classify_key("LCTRL + C") == "MODIFIER"
        assert _classify_key("RSHIFT + A") == "MODIFIER"

    def test_unknown(self):
        assert _classify_key("CAPSLOCK") == "UNKNOWN"

    def test_aliases(self):
        assert _classify_key("ENTER") == "\n"
        assert _classify_key("BACKSPACE") == "BACK"
        assert _classify_key("DEL") == "DELETE"
        assert _classify_key("SPACEBAR") == " "
        assert _classify_key("ESPACE") == " "
        assert _classify_key("RETOUR") == "BACK"
        assert _classify_key("SUPPR") == "DELETE"

    def test_multi_char(self):
        assert _classify_key("你好") == "你好"
        assert _classify_key("œ") == "œ"


# --- _process_events ---

class TestProcessEvents:
    def test_simple_typing(self):
        events = [
            _kb(1, "h", position=0, doclength=0, start_time=100),
            _kb(2, "i", position=1, doclength=1, start_time=200),
        ]
        actions, text, diags = _process_events(events)
        assert text == "hi"
        assert len(actions) == 2
        assert all(a.kind == "insert" for a in actions)

    def test_typing_and_backspace(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "b", position=1, doclength=1, start_time=200),
            _kb(3, "BACK", position=2, doclength=2, start_time=300),
        ]
        actions, text, diags = _process_events(events)
        assert text == "a"
        assert actions[-1].kind == "delete"
        assert actions[-1].deleted_text == "b"

    def test_mouse_click_creates_move(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "b", position=1, doclength=1, start_time=200),
            _mouse(3, "LEFT Click", position=0, doclength=2, start_time=300),
        ]
        actions, text, diags = _process_events(events)
        assert actions[-1].kind == "move"
        assert actions[-1].position == 0

    def test_mouse_movement_ignored(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _mouse(2, "Movement", position=0, doclength=1, start_time=200),
        ]
        actions, text, diags = _process_events(events)
        assert len(actions) == 1

    def test_doclength_drift_emits_diagnostic(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "BACK", position=2, doclength=3, start_time=200),
        ]
        actions, text, diags = _process_events(events)
        warnings = [d for d in diags if d.level == "warning"]
        assert any("drift" in d.message for d in warnings)

    def test_replacement(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "b", position=1, doclength=1, start_time=200),
            _replacement(3, "[0:1] X", position=0, doclength=2, start_time=300),
        ]
        actions, text, diags = _process_events(events)
        assert text == "Xb"
        replace_actions = [a for a in actions if a.kind == "replace"]
        assert len(replace_actions) == 1
        assert replace_actions[0].deleted_text == "a"
        assert replace_actions[0].text == "X"

    def test_identity_replacement_skipped(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _replacement(2, "[0:1] a", position=0, doclength=1, start_time=200),
        ]
        actions, text, diags = _process_events(events)
        replace_actions = [a for a in actions if a.kind == "replace"]
        assert len(replace_actions) == 0
        assert any("identity" in d.message for d in diags)

    def test_nav_key_skipped(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "LEFT", position=1, doclength=1, start_time=200),
        ]
        actions, text, diags = _process_events(events)
        assert len(actions) == 1
        assert actions[0].kind == "insert"

    def test_multi_char_insert(self):
        events = [
            _kb(1, "你好", position=0, doclength=0, start_time=100),
        ]
        actions, text, diags = _process_events(events)
        assert text == "你好"
        assert actions[0].text == "你好"

    def test_key_alias(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "BACKSPACE", position=1, doclength=1, start_time=200),
        ]
        actions, text, diags = _process_events(events)
        assert text == ""
        assert actions[-1].kind == "delete"


# --- Episode grouping ---

class TestEpisodeGrouping:
    def test_forward_typing_single_episode(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "b", position=1, doclength=1, start_time=200),
            _kb(3, "c", position=2, doclength=2, start_time=300),
        ]
        actions, _, _ = _process_events(events)
        episodes = _group_into_episodes(actions)
        assert len(episodes) == 1
        assert not episodes[0].is_revision

    def test_click_then_back_is_revision(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "b", position=1, doclength=1, start_time=200),
            _mouse(3, "LEFT Click", position=0, doclength=2, start_time=300),
            _kb(4, "BACK", position=1, doclength=2, start_time=400),
        ]
        actions, _, _ = _process_events(events)
        episodes = _group_into_episodes(actions)
        assert len(episodes) >= 2
        revision_eps = [ep for ep in episodes if ep.is_revision]
        assert len(revision_eps) >= 1


# --- End-to-end ---

class TestEndToEnd:
    def test_doc_csv(self):
        csv_path = Path(__file__).parent.parent / "data/input/doc.csv"
        if not csv_path.exists():
            return

        from keystroke2tei.parser import parse_csv
        from keystroke2tei.writer import write_tei

        events, metadata, warnings = parse_csv(csv_path)
        result = convert(events, metadata=metadata, parse_warnings=len(warnings))

        assert "Longtemps" in result.final_text
        assert len(result.episodes) >= 2
        assert len(result.segments) >= 1

        xml = write_tei(result.segments, metadata=metadata)
        assert "<TEI" in xml
        assert "<add " in xml
        assert "<del " in xml
        assert "couché" in xml
        assert metadata.participant == "Zahra"
        assert metadata.language == "FR"

        assert len(result.diagnostics) > 0

        assert result.stats.typed_chars > 0
        assert result.stats.deletions > 0
        assert result.stats.total_events > 0
