from __future__ import annotations

from pathlib import Path

from keystroke2tei.converter import CharMap, RevisionEpisode, WritingAction, _classify_key, _process_events, _group_into_episodes, convert, _build_tei_tree, _interleave_text_with_revisions, _segment_by_sentences, _find_sentence_ranges
from keystroke2tei.models import Event, EventType, NodeKind, TEINode


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
        assert _classify_key("RETURN") == "RETURN"
        assert _classify_key("TAB") == "\t"

    def test_nav_keys(self):
        assert _classify_key("LEFT") == "NAV"
        assert _classify_key("RIGHT") == "NAV"
        assert _classify_key("HOME") == "NAV"
        assert _classify_key("END") == "NAV"

    def test_modifier(self):
        assert _classify_key("LCTRL + C") == "CTRL+C"
        assert _classify_key("RSHIFT + A") == "MODIFIER"
        assert _classify_key("LCTRL + Z") == "MODIFIER"

    def test_unknown(self):
        assert _classify_key("CAPSLOCK") == "UNKNOWN"

    def test_aliases(self):
        assert _classify_key("ENTER") == "RETURN"
        assert _classify_key("BACKSPACE") == "BACK"
        assert _classify_key("DEL") == "DELETE"
        assert _classify_key("SPACEBAR") == " "
        assert _classify_key("ESPACE") == " "
        assert _classify_key("RETOUR") == "BACK"
        assert _classify_key("SUPPR") == "DELETE"

    def test_multi_char(self):
        assert _classify_key("你好") == "你好"
        assert _classify_key("œ") == "œ"

    def test_caps_lock_with_space(self):
        assert _classify_key("CAPS LOCK") == "UNKNOWN"

    def test_bare_modifiers(self):
        assert _classify_key("LCTRL") == "UNKNOWN"
        assert _classify_key("RCTRL") == "UNKNOWN"
        assert _classify_key("LALT") == "UNKNOWN"
        assert _classify_key("RALT") == "UNKNOWN"
        assert _classify_key("LSHIFT") == "UNKNOWN"
        assert _classify_key("RSHIFT") == "UNKNOWN"


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

    def test_return_produces_linebreak_action(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "RETURN", position=1, doclength=1, start_time=200),
            _kb(3, "b", position=2, doclength=2, start_time=300),
        ]
        actions, text, diags = _process_events(events)
        assert text == "a\nb"
        assert actions[1].kind == "linebreak"

    def test_bare_modifier_skipped(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "LSHIFT", position=1, doclength=1, start_time=200),
            _kb(3, "b", position=1, doclength=1, start_time=300),
        ]
        actions, text, diags = _process_events(events)
        assert len(actions) == 2
        assert text == "ab"


# --- Line break in TEI ---

class TestLineBreak:
    def test_lb_in_tei_output(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "RETURN", position=1, doclength=1, start_time=200),
            _kb(3, "b", position=2, doclength=2, start_time=300),
        ]
        actions, _, _ = _process_events(events)
        episodes = _group_into_episodes(actions)
        seg = _build_tei_tree(episodes)
        # Should have an <add> with text "a", <lb/>, text "b"
        assert len(seg.children) >= 1
        add_node = seg.children[0]
        lb_nodes = [c for c in add_node.children if c.kind == NodeKind.LB]
        assert len(lb_nodes) == 1

    def test_lb_serializes_to_xml(self):
        from keystroke2tei.writer import write_tei
        events = [
            _kb(1, "h", position=0, doclength=0, start_time=100),
            _kb(2, "i", position=1, doclength=1, start_time=200),
            _kb(3, "RETURN", position=2, doclength=2, start_time=300),
            _kb(4, "x", position=3, doclength=3, start_time=400),
        ]
        result = convert(events)
        xml = write_tei(result.segments)
        assert "<lb/>" in xml

    def test_linebreak_no_episode_split(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "RETURN", position=1, doclength=1, start_time=200),
            _kb(3, "b", position=2, doclength=2, start_time=300),
        ]
        actions, _, _ = _process_events(events)
        episodes = _group_into_episodes(actions)
        # linebreak should not split the episode
        assert len(episodes) == 1


# --- Empty seg filtering ---

class TestEmptySegFiltering:
    def test_empty_seg_filtered(self):
        events = [
            _mouse(1, "LEFT Click", position=0, doclength=0, start_time=100),
        ]
        result = convert(events)
        assert len(result.segments) == 0


# --- Pipe types (nt|continue) ---

class TestPipeContinue:
    def test_nt_continue_after_inline_typo(self):
        # Type "abc", backspace (typo correction), then type "de"
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "b", position=1, doclength=1, start_time=200),
            _kb(3, "c", position=2, doclength=2, start_time=300),
            _kb(4, "BACK", position=3, doclength=3, start_time=400),
            _kb(5, "d", position=2, doclength=2, start_time=500),
            _kb(6, "e", position=3, doclength=3, start_time=600),
        ]
        actions, _, _ = _process_events(events)
        episodes = _group_into_episodes(actions)
        seg = _build_tei_tree(episodes)

        # Should have: <add type="nt">abc<del type="typo">c</del></add>
        #              <add type="nt|continue">de</add>
        add_nodes = [c for c in seg.children if c.kind == NodeKind.ADD]
        assert len(add_nodes) == 2
        continue_node = add_nodes[1]
        assert continue_node.revision_type == "nt|continue"

    def test_nt_continue_in_xml(self):
        from keystroke2tei.writer import write_tei
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "b", position=1, doclength=1, start_time=200),
            _kb(3, "BACK", position=2, doclength=2, start_time=300),
            _kb(4, "c", position=1, doclength=1, start_time=400),
        ]
        result = convert(events)
        xml = write_tei(result.segments)
        assert 'type="nt|continue"' in xml


# --- Translocation (cut/paste) ---

class TestTranslocation:
    def test_ctrl_x_classified(self):
        assert _classify_key("LCTRL + X") == "CTRL+X"
        assert _classify_key("RCTRL + C") == "CTRL+C"
        assert _classify_key("LCTRL + V") == "CTRL+V"

    def test_cut_paste_translocation(self):
        from keystroke2tei.writer import write_tei
        # Type "abc", select+cut "b", move to end, paste
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "b", position=1, doclength=1, start_time=200),
            _kb(3, "c", position=2, doclength=2, start_time=300),
            # Select "b" (pos 1) and cut — doclength drops from 3 to 2
            _kb(4, "LCTRL + X", position=1, doclength=3, start_time=400),
            # Move to end and paste
            _mouse(5, "LEFT Click", position=2, doclength=2, start_time=500),
            _kb(6, "LCTRL + V", position=2, doclength=2, start_time=600),
        ]
        result = convert(events)
        xml = write_tei(result.segments)
        assert 'type="translocation"' in xml

    def test_ga_format_ctrl_combo(self):
        # GA format: bare LCTRL event followed by "c" event
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _kb(2, "LCTRL", position=1, doclength=1, start_time=200),
            _kb(3, "c", position=1, doclength=1, start_time=300),
        ]
        actions, _, _ = _process_events(events)
        # LCTRL + c → copy, no action emitted (just clipboard)
        assert len(actions) == 1  # only the initial insert


# --- pre-context fix ---

class TestPreContext:
    def test_precontext_insert_after_click_back(self):
        from keystroke2tei.converter import _classify_revision_type, RevisionEpisode
        # Simulate: cursor moved back, insertion only (no delete)
        ep = RevisionEpisode(is_revision=True, cursor_moved_back=True)
        ep.actions.append(WritingAction(kind="insert", position=5, text="x", timestamp=100))
        assert _classify_revision_type(ep) == "pre-context"

    def test_context_delete_after_click_back(self):
        from keystroke2tei.converter import _classify_revision_type, RevisionEpisode, WritingAction
        # Simulate: cursor moved back, has delete → context
        ep = RevisionEpisode(is_revision=True, cursor_moved_back=True)
        ep.actions.append(WritingAction(
            kind="delete", position=5, deleted_text="x", timestamp=100,
            context_complete=True,
        ))
        assert _classify_revision_type(ep) == "context"

    def test_precontext_e2e(self):
        from keystroke2tei.writer import write_tei
        # Type "hello", click to pos 2, type "X" (no delete)
        events = [
            _kb(1, "h", position=0, doclength=0, start_time=100),
            _kb(2, "e", position=1, doclength=1, start_time=200),
            _kb(3, "l", position=2, doclength=2, start_time=300),
            _kb(4, "l", position=3, doclength=3, start_time=400),
            _kb(5, "o", position=4, doclength=4, start_time=500),
            _mouse(6, "LEFT Click", position=2, doclength=5, start_time=600),
            _kb(7, "X", position=2, doclength=5, start_time=700),
        ]
        result = convert(events)
        xml = write_tei(result.segments)
        assert 'type="pre-context"' in xml


# --- mod type="continue" ---

class TestModContinue:
    def test_return_to_leading_edge(self):
        # Type "hello" → click at pos 1 → delete "e" → click back to pos 4 → type " world"
        events = [
            _kb(1, "h", position=0, doclength=0, start_time=100),
            _kb(2, "e", position=1, doclength=1, start_time=200),
            _kb(3, "l", position=2, doclength=2, start_time=300),
            _kb(4, "l", position=3, doclength=3, start_time=400),
            _kb(5, "o", position=4, doclength=4, start_time=500),
            # Click to pos 1 (before "e") — away from leading edge (5)
            _mouse(6, "LEFT Click", position=1, doclength=5, start_time=600),
            # Delete "e"
            _kb(7, "DELETE", position=1, doclength=5, start_time=700),
            # Click back to pos 4 (near leading edge)
            _mouse(8, "LEFT Click", position=4, doclength=4, start_time=800),
            # Resume typing
            _kb(9, "SPACE", position=4, doclength=4, start_time=900),
            _kb(10, "w", position=5, doclength=5, start_time=1000),
        ]
        actions, _, _ = _process_events(events)
        episodes = _group_into_episodes(actions)
        seg = _build_tei_tree(episodes)
        mod_nodes = [c for c in seg.children if c.kind == NodeKind.MOD]
        assert len(mod_nodes) == 1
        assert mod_nodes[0].revision_type == "continue"


# --- Focus events + source ---

def _focus(event_id: int, output: str, position: int, doclength: int, start_time: int = 0) -> Event:
    return Event(
        event_type=EventType.FOCUS, event_id=event_id, output=output,
        char_production=0, action_time=0, start_time=start_time, end_time=start_time,
        pause_location=0, pause_location_full="", pause_time=0,
        position=position, doclength=doclength,
    )


class TestFocusSource:
    def test_focus_creates_action(self):
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _focus(2, "Chrome", position=1, doclength=1, start_time=200),
        ]
        actions, _, _ = _process_events(events)
        focus_actions = [a for a in actions if a.kind == "focus"]
        assert len(focus_actions) == 1
        assert focus_actions[0].text == "Chrome"

    def test_source_paste_detection(self):
        from keystroke2tei.writer import write_tei
        # Type "a", focus out to Chrome, focus back, paste "xyz"
        events = [
            _kb(1, "a", position=0, doclength=0, start_time=100),
            _focus(2, "Chrome", position=1, doclength=1, start_time=200),
            _focus(3, "Word", position=1, doclength=1, start_time=300),
            _kb(4, "LCTRL + V", position=1, doclength=1, start_time=400),
            # Next event to resolve paste — doclength increased by 3
            _kb(5, "b", position=4, doclength=4, start_time=500),
        ]
        result = convert(events)
        xml = write_tei(result.segments, focus_sources=result.focus_sources)
        assert 'type="source"' in xml

    def test_focus_sources_in_xml(self):
        from keystroke2tei.writer import write_tei
        events = [
            _focus(1, "Chrome", position=0, doclength=0, start_time=100),
        ]
        result = convert(events)
        xml = write_tei(result.segments, focus_sources=result.focus_sources)
        assert 'source="sources"' in xml
        assert "<desc>Chrome</desc>" in xml
        assert '<media url="Chrome">' in xml


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


class TestTimestampSeq:
    def test_same_second_keeps_event_time(self):
        events = [
            _kb(1, "a", 0, 0, 100),
            _kb(2, "b", 1, 1, 200),
            _kb(3, "BACK", 2, 2, 300),
            _kb(4, "c", 1, 1, 400),
        ]
        result = convert(events)
        nodes = [node for seg in result.segments for node in seg.children]
        assert [node.seq for node in nodes] == ["000000", "000000"]
        assert nodes[0].children[-1].seq == "000000"


class TestInterleaveTextWithRevisions:
    def test_no_revisions_unchanged(self):
        text = TEINode(kind=NodeKind.TEXT, text="hello")
        add = TEINode(kind=NodeKind.ADD, start_pos=0, end_pos=5, children=[text])
        _interleave_text_with_revisions(add)
        assert len(add.children) == 1
        assert add.children[0].text == "hello"

    def test_basic_interleave(self):
        # "abcde" with "c" deleted at pos 2 and "X" inserted
        text = TEINode(kind=NodeKind.TEXT, text="abcde")
        del_node = TEINode(kind=NodeKind.DEL, text="c", start_pos=2, end_pos=3)
        add_node = TEINode(kind=NodeKind.ADD, start_pos=2, end_pos=3, children=[
            TEINode(kind=NodeKind.TEXT, text="X"),
        ])
        parent = TEINode(kind=NodeKind.ADD, start_pos=0, end_pos=5,
                         children=[text, del_node, add_node])
        _interleave_text_with_revisions(parent)
        # Expected: TEXT("ab") DEL("c") ADD("X") TEXT("de")
        assert len(parent.children) == 4
        assert parent.children[0].kind == NodeKind.TEXT
        assert parent.children[0].text == "ab"
        assert parent.children[1].kind == NodeKind.DEL
        assert parent.children[2].kind == NodeKind.ADD
        assert parent.children[3].kind == NodeKind.TEXT
        assert parent.children[3].text == "de"

    def test_multiple_revisions(self):
        # "abcde" with "b" deleted at pos 1 and "d" deleted at pos 3
        text = TEINode(kind=NodeKind.TEXT, text="abcde")
        del1 = TEINode(kind=NodeKind.DEL, text="b", start_pos=1, end_pos=2)
        del2 = TEINode(kind=NodeKind.DEL, text="d", start_pos=3, end_pos=4)
        parent = TEINode(kind=NodeKind.ADD, start_pos=0, end_pos=5,
                         children=[text, del1, del2])
        _interleave_text_with_revisions(parent)
        # Expected: TEXT("a") DEL("b") TEXT("c") DEL("d") TEXT("e")
        assert len(parent.children) == 5
        assert parent.children[0].text == "a"
        assert parent.children[1].kind == NodeKind.DEL
        assert parent.children[2].text == "c"
        assert parent.children[3].kind == NodeKind.DEL
        assert parent.children[4].text == "e"

    def test_le_repas_scenario(self):
        # "Le repas était bon et agréable" with "bon" at pos 15 deleted, "savoureux" added
        full_text = "Le repas était bon et agréable"
        text = TEINode(kind=NodeKind.TEXT, text=full_text)
        del_node = TEINode(kind=NodeKind.DEL, text="bon", start_pos=15, end_pos=18)
        add_node = TEINode(kind=NodeKind.ADD, start_pos=15, end_pos=24, children=[
            TEINode(kind=NodeKind.TEXT, text="savoureux"),
        ])
        parent = TEINode(kind=NodeKind.ADD, start_pos=0, end_pos=len(full_text),
                         children=[text, del_node, add_node])
        _interleave_text_with_revisions(parent)
        # Expected: TEXT("Le repas était ") DEL("bon") ADD("savoureux") TEXT(" et agréable")
        assert len(parent.children) == 4
        assert parent.children[0].kind == NodeKind.TEXT
        assert parent.children[0].text == "Le repas était "
        assert parent.children[1].kind == NodeKind.DEL
        assert parent.children[1].text == "bon"
        assert parent.children[2].kind == NodeKind.ADD
        assert parent.children[3].kind == NodeKind.TEXT
        assert parent.children[3].text == " et agréable"

    def test_deletion_at_start(self):
        text = TEINode(kind=NodeKind.TEXT, text="abcde")
        del_node = TEINode(kind=NodeKind.DEL, text="a", start_pos=0, end_pos=1)
        parent = TEINode(kind=NodeKind.ADD, start_pos=0, end_pos=5,
                         children=[text, del_node])
        _interleave_text_with_revisions(parent)
        # Expected: DEL("a") TEXT("bcde")
        assert len(parent.children) == 2
        assert parent.children[0].kind == NodeKind.DEL
        assert parent.children[1].text == "bcde"

    def test_deletion_at_end(self):
        text = TEINode(kind=NodeKind.TEXT, text="abcde")
        del_node = TEINode(kind=NodeKind.DEL, text="e", start_pos=4, end_pos=5)
        parent = TEINode(kind=NodeKind.ADD, start_pos=0, end_pos=5,
                         children=[text, del_node])
        _interleave_text_with_revisions(parent)
        # Expected: TEXT("abcd") DEL("e")
        assert len(parent.children) == 2
        assert parent.children[0].text == "abcd"
        assert parent.children[1].kind == NodeKind.DEL


class TestSentenceSegmentation:
    def test_find_sentence_ranges_single(self):
        ranges = _find_sentence_ranges("Hello world")
        assert ranges == [(0, 11)]

    def test_find_sentence_ranges_two_sentences(self):
        ranges = _find_sentence_ranges("Hello. Goodbye.")
        assert len(ranges) == 2
        assert ranges[0] == (0, 7)  # "Hello. "
        assert ranges[1] == (7, 15)  # "Goodbye."

    def test_find_sentence_ranges_question_exclamation(self):
        ranges = _find_sentence_ranges("What? Yes! Done.")
        assert len(ranges) == 3

    def test_find_sentence_ranges_empty(self):
        ranges = _find_sentence_ranges("")
        assert ranges == [(0, 0)]

    def test_segment_by_sentences_single_sentence(self):
        ep1 = RevisionEpisode(actions=[WritingAction(kind="insert", position=0, text="hello")])
        ep2 = RevisionEpisode(actions=[WritingAction(kind="delete", position=3, deleted_text="l")], is_revision=True)
        groups = _segment_by_sentences([ep1, ep2], "helo")
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_segment_by_sentences_two_sentences(self):
        ep1 = RevisionEpisode(actions=[WritingAction(kind="insert", position=0, text="Hi. ")])
        ep2 = RevisionEpisode(actions=[WritingAction(kind="insert", position=4, text="Bye.")])
        groups = _segment_by_sentences([ep1, ep2], "Hi. Bye.")
        assert len(groups) == 2

    def test_revision_groups_with_target_sentence(self):
        ep1 = RevisionEpisode(actions=[WritingAction(kind="insert", position=0, text="Hi. ")])
        ep2 = RevisionEpisode(actions=[WritingAction(kind="insert", position=4, text="Bye.")])
        ep3 = RevisionEpisode(actions=[WritingAction(kind="delete", position=1, deleted_text="i")], is_revision=True)
        groups = _segment_by_sentences([ep1, ep2, ep3], "H. Bye.")
        # ep3 targets position 1, which is in sentence 1 ("H. ")
        assert len(groups) == 2
        assert ep3 in groups[0]
