from __future__ import annotations

import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher

from keystroke2tei.models import ConversionStats, Diagnostic, Event, EventType, NodeKind, SessionMetadata, TEINode


SPECIAL_KEYS = {"SPACE", "BACK", "DELETE", "RETURN", "TAB"}
NAV_KEYS = {"LEFT", "RIGHT", "UP", "DOWN", "HOME", "END", "PAGEUP", "PAGEDOWN"}
IGNORED_KEYS = {"CAPSLOCK", "NUMLOCK", "SCROLL", "INSERT", "ESCAPE", "PRINT", "PAUSE",
                "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
                "LCTRL", "RCTRL", "LALT", "RALT", "LSHIFT", "RSHIFT"}
MODIFIER_PATTERN = re.compile(r"^(LCTRL|RCTRL|LALT|RALT|LSHIFT|RSHIFT)\s*\+")
REPLACEMENT_PATTERN = re.compile(r"^\[(\d+):(\d+)\] (.*)")


def _ms_to_seq(ms: int) -> str:
    """Convert elapsed milliseconds or a local wall-clock epoch to @seq."""
    if ms >= 100_000_000_000:
        wall_time = datetime(1970, 1, 1) + timedelta(milliseconds=ms)
        return wall_time.strftime("%Y%m%d%H%M%S")
    total_seconds = ms // 1000
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}{m:02d}{s:02d}"


def _evidence_from_actions(actions: list[WritingAction]) -> str:
    """Compute @evidence from event IDs: single ID or 'first-last' range."""
    ids = [a.event.event_id for a in actions if a.event is not None]
    if not ids:
        return ""
    if len(ids) == 1 or ids[0] == ids[-1]:
        return str(ids[0])
    return f"{ids[0]}-{ids[-1]}"


KEY_ALIASES: dict[str, str] = {
    "ENTER": "RETURN",
    "BACKSPACE": "BACK",
    "DEL": "DELETE",
    "SPACEBAR": "SPACE",
    "ESPACE": "SPACE",
    "RETOUR": "BACK",
    "SUPPR": "DELETE",
    "ENTREE": "RETURN",
    "EINGABE": "RETURN",
    "ENTF": "DELETE",
    "LEERTASTE": "SPACE",
    "LÖSCHEN": "BACK",
}


@dataclass
class WritingAction:
    kind: str  # "insert", "delete", "replace", "move", "noop"
    position: int
    text: str = ""
    deleted_text: str = ""
    event: Event | None = None
    timestamp: int = 0
    context_complete: bool = False
    context_at_edit: str = ""
    final_positions: list[int | None] = field(default_factory=list)
    final_anchor: int | None = None


@dataclass
class CharMap:
    """Position-indexed character map. None = unknown (autocomplete-inserted)."""
    _chars: list[str | None] = field(default_factory=list)
    _origins: list[tuple[WritingAction, int] | None] = field(default_factory=list)
    _markers: list[WritingAction] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self._chars)

    def pad_to(self, target_len: int) -> None:
        if target_len > self.length:
            difference = target_len - self.length
            self._chars.extend([None] * difference)
            self._origins.extend([None] * difference)

    def insert(self, pos: int, char: str, origin: tuple[WritingAction, int] | None = None) -> None:
        pos = max(0, min(pos, self.length))
        for marker in self._markers:
            if marker.final_anchor is not None and marker.final_anchor > pos:
                marker.final_anchor += 1
        self._chars.insert(pos, char)
        self._origins.insert(pos, origin)

    def delete(self, pos: int) -> str:
        if 0 <= pos < self.length:
            for marker in self._markers:
                if marker.final_anchor is not None and marker.final_anchor > pos:
                    marker.final_anchor -= 1
            ch = self._chars.pop(pos)
            self._origins.pop(pos)
            return ch if ch is not None else ""
        return ""

    def mark_deleted(self, action: WritingAction) -> None:
        action.final_anchor = action.position
        self._markers.append(action)

    def replace_range(
        self, start: int, end: int, new_text: str,
        action: WritingAction | None = None,
    ) -> str:
        start = max(0, start)
        end = min(end, self.length)
        old_chars = self._chars[start:end]
        old_text = "".join(c for c in old_chars if c is not None)
        delta = len(new_text) - (end - start)
        for marker in self._markers:
            anchor = marker.final_anchor
            if anchor is None:
                continue
            if anchor >= end:
                marker.final_anchor += delta
            elif start < anchor < end:
                marker.final_anchor = start
        del self._chars[start:end]
        del self._origins[start:end]
        for i, ch in enumerate(new_text):
            self._chars.insert(start + i, ch)
            self._origins.insert(start + i, (action, i) if action is not None else None)
        return old_text

    def get_text(self) -> str:
        return "".join(c for c in self._chars if c is not None)

    def context_at(self, pos: int, width: int = 50) -> str:
        """Text surrounding a cursor immediately before a writing action."""
        pos = max(0, min(pos, self.length))
        left = "".join(ch if ch is not None else "□" for ch in self._chars[max(0, pos - width):pos])
        right = "".join(ch if ch is not None else "□" for ch in self._chars[pos:pos + width])
        return f"{left}|{right}"

    def sentence_complete_at(self, pos: int) -> bool:
        """Whether the sentence at pos already has closing punctuation."""
        for ch in self._chars[max(0, pos):]:
            if ch in (".", "!", "?"):
                return True
            if ch == "\n":
                return False
        return False


@dataclass
class RevisionEpisode:
    actions: list[WritingAction] = field(default_factory=list)
    start_time: int = 0
    end_time: int = 0
    is_revision: bool = False
    cursor_moved_back: bool = False
    revision_type_hint: str = ""
    force_new_add: bool = False

    @property
    def net_text(self) -> str:
        parts: list[str] = []
        for a in self.actions:
            if a.kind in ("insert", "linebreak", "paste"):
                parts.append(a.text)
        return "".join(parts)

    @property
    def has_linebreak(self) -> bool:
        return any(a.kind == "linebreak" for a in self.actions)

    @property
    def deleted_text(self) -> str:
        del_parts: list[str] = []
        replace_parts: list[str] = []
        for a in self.actions:
            if a.kind == "delete":
                del_parts.append(a.deleted_text)
            elif a.kind == "replace":
                replace_parts.append(a.deleted_text)
        # BACK deletes are right-to-left, reverse to get reading order
        reversed_dels = "".join(reversed(del_parts))
        return reversed_dels + "".join(replace_parts)


def _classify_key(output: str) -> str:
    stripped = output.replace(" ", "")
    normalized = KEY_ALIASES.get(stripped, KEY_ALIASES.get(output, stripped))
    if normalized == "SPACE":
        return " "
    if normalized == "BACK":
        return "BACK"
    if normalized == "DELETE":
        return "DELETE"
    if normalized == "RETURN":
        return "RETURN"
    if normalized == "TAB":
        return "\t"
    if normalized in NAV_KEYS:
        return "NAV"
    if normalized in IGNORED_KEYS:
        return "UNKNOWN"
    m = MODIFIER_PATTERN.match(output)
    if m:
        rest = output[m.end():].strip()
        if rest.upper() in ("X", "C", "V"):
            return f"CTRL+{rest.upper()}"
        return "MODIFIER"
    if len(output) == 1:
        return output
    # Multi-char output (IME, emoji, ligatures) — treat as typed text
    if len(output) > 1 and output.isprintable():
        return output
    return "UNKNOWN"


def _process_events(
    events: list[Event], initial_text: str = "",
    document_out: list[str] | None = None,
) -> tuple[list[WritingAction], str, list[Diagnostic]]:
    cmap = CharMap(_chars=list(initial_text), _origins=[None] * len(initial_text))
    actions: list[WritingAction] = []
    diagnostics: list[Diagnostic] = []
    prev_cursor = 0
    pending_modifier: str | None = None
    clipboard: str = ""
    pending_clipboard_op: str | None = None
    pending_clipboard_ev: Event | None = None
    pending_clipboard_cursor: int = 0
    focus_source: str = ""

    for ev in events:
        if ev.event_type == EventType.FOCUS:
            actions.append(WritingAction(
                kind="focus", position=ev.position, text=ev.output,
                event=ev, timestamp=ev.start_time,
            ))
            focus_source = ev.output
            continue

        # Resolve pending cut/copy/paste using this event's doclength (before drift padding)
        if pending_clipboard_op is not None:
            if pending_clipboard_op == "CTRL+X":
                cut_len = max(0, cmap.length - ev.doclength)
                cut_text = ""
                cut_context = cmap.context_at(pending_clipboard_cursor)
                for _ in range(cut_len):
                    if pending_clipboard_cursor < cmap.length:
                        ch = cmap.delete(pending_clipboard_cursor)
                        cut_text += ch if ch else ""
                clipboard = cut_text
                if cut_text and pending_clipboard_ev:
                    cut_action = WritingAction(
                        kind="cut", position=pending_clipboard_cursor,
                        deleted_text=cut_text, event=pending_clipboard_ev,
                        timestamp=pending_clipboard_ev.start_time,
                        context_at_edit=cut_context,
                    )
                    cmap.mark_deleted(cut_action)
                    actions.append(cut_action)
            elif pending_clipboard_op == "CTRL+C":
                # Infer copied text from selection (same length logic as cut but no delete)
                # We can't determine copy content without selection info; best effort
                pass
            elif pending_clipboard_op == "CTRL+V":
                paste_len = max(0, ev.doclength - cmap.length)
                if paste_len > 0 and clipboard:
                    paste_text = clipboard[:paste_len] if len(clipboard) >= paste_len else clipboard
                elif paste_len > 0:
                    paste_text = "?" * paste_len
                elif clipboard:
                    paste_text = clipboard
                else:
                    paste_text = ""
                if paste_text and pending_clipboard_ev:
                    paste_action = WritingAction(
                        kind="paste", position=pending_clipboard_cursor,
                        text=paste_text, event=pending_clipboard_ev,
                        timestamp=pending_clipboard_ev.start_time,
                        context_at_edit=cmap.context_at(pending_clipboard_cursor),
                        final_positions=[None] * len(paste_text),
                    )
                    for i, ch in enumerate(paste_text):
                        cmap.insert(pending_clipboard_cursor + i, ch, (paste_action, i))
                    actions.append(paste_action)
            pending_clipboard_op = None
            pending_clipboard_ev = None

        # Pad map if CSV reports a larger document (autocomplete/spellcheck added chars)
        if ev.doclength > cmap.length:
            drift = ev.doclength - cmap.length
            diagnostics.append(Diagnostic(
                event_id=ev.event_id, timestamp=ev.start_time,
                message=f"doclength drift +{drift} (autocomplete/spellcheck?)",
                level="warning",
            ))
            cmap.pad_to(ev.doclength)

        if ev.event_type == EventType.MOUSE:
            if "Click" not in ev.output:
                continue
            actions.append(WritingAction(
                kind="move", position=ev.position, event=ev,
                timestamp=ev.start_time,
            ))
            prev_cursor = ev.position
            continue

        if ev.event_type == EventType.REPLACEMENT:
            m = REPLACEMENT_PATTERN.match(ev.output)
            if m:
                start, end, new_text = int(m.group(1)), int(m.group(2)), m.group(3)
                start = max(0, min(start, cmap.length))
                end = max(start, min(end, cmap.length))
                context_complete = cmap.sentence_complete_at(start)
                old_text = "".join(ch for ch in cmap._chars[start:end] if ch is not None)
                if old_text != new_text:
                    replace_action = WritingAction(
                        kind="replace", position=start, text=new_text,
                        deleted_text=old_text, event=ev, timestamp=ev.start_time,
                        context_complete=context_complete,
                        context_at_edit=cmap.context_at(start),
                        final_positions=[None] * len(new_text),
                    )
                    cmap.replace_range(start, end, new_text, replace_action)
                    cmap.mark_deleted(replace_action)
                    actions.append(replace_action)
                else:
                    diagnostics.append(Diagnostic(
                        event_id=ev.event_id, timestamp=ev.start_time,
                        message=f"identity replacement skipped at [{start}:{end}]",
                    ))
            continue

        if ev.event_type == EventType.KEYBOARD:
            if not ev.replay:
                continue
            key = _classify_key(ev.output)

            # GA format: bare modifier followed by X/C/V
            if key == "UNKNOWN" and ev.output.replace(" ", "") in ("LCTRL", "RCTRL"):
                pending_modifier = "CTRL"
                continue
            if pending_modifier == "CTRL" and len(key) == 1 and key.upper() in ("X", "C", "V"):
                key = f"CTRL+{key.upper()}"
                pending_modifier = None
            else:
                pending_modifier = None

            if key in ("MODIFIER", "UNKNOWN", "NAV"):
                continue

            cursor = ev.position  # pre-event cursor from CSV
            context_complete = cmap.sentence_complete_at(cursor)

            if key == "BACK":
                del_pos = cursor - 1
                if del_pos >= 0:
                    deleted_sentence_complete = cmap.sentence_complete_at(del_pos)
                    context_at_edit = cmap.context_at(del_pos)
                    deleted = cmap.delete(del_pos)
                    if not deleted:
                        diagnostics.append(Diagnostic(
                            event_id=ev.event_id, timestamp=ev.start_time,
                            message=f"unknown deleted char at position {del_pos}",
                            level="warning",
                        ))
                    delete_action = WritingAction(
                        kind="delete", position=del_pos,
                        deleted_text=deleted, event=ev, timestamp=ev.start_time,
                        context_complete=deleted_sentence_complete,
                        context_at_edit=context_at_edit,
                    )
                    cmap.mark_deleted(delete_action)
                    actions.append(delete_action)
            elif key == "DELETE":
                if cursor < cmap.length:
                    context_at_edit = cmap.context_at(cursor)
                    deleted = cmap.delete(cursor)
                    if not deleted:
                        diagnostics.append(Diagnostic(
                            event_id=ev.event_id, timestamp=ev.start_time,
                            message=f"unknown deleted char at position {cursor}",
                            level="warning",
                        ))
                    delete_action = WritingAction(
                        kind="delete", position=cursor,
                        deleted_text=deleted, event=ev, timestamp=ev.start_time,
                        context_complete=context_complete,
                        context_at_edit=context_at_edit,
                    )
                    cmap.mark_deleted(delete_action)
                    actions.append(delete_action)
            elif key == "RETURN":
                action = WritingAction(
                    kind="linebreak", position=cursor, text="\n",
                    event=ev, timestamp=ev.start_time,
                    context_complete=context_complete,
                    context_at_edit=cmap.context_at(cursor),
                    final_positions=[None],
                )
                cmap.insert(cursor, "\n", (action, 0))
                actions.append(action)
            elif key in ("CTRL+X", "CTRL+C", "CTRL+V"):
                pending_clipboard_op = key
                pending_clipboard_ev = ev
                pending_clipboard_cursor = cursor
            else:
                action = WritingAction(
                    kind="insert", position=cursor, text=key,
                    event=ev, timestamp=ev.start_time,
                    context_complete=context_complete,
                    context_at_edit=cmap.context_at(cursor),
                    final_positions=[None] * len(key),
                )
                for i, ch in enumerate(key):
                    cmap.insert(cursor + i, ch, (action, i))
                actions.append(action)

            prev_cursor = ev.position

    # Resolve any trailing clipboard op (last event was cut/copy/paste)
    if pending_clipboard_op == "CTRL+V" and clipboard and pending_clipboard_ev:
        paste_action = WritingAction(
            kind="paste", position=pending_clipboard_cursor,
            text=clipboard, event=pending_clipboard_ev,
            timestamp=pending_clipboard_ev.start_time,
            context_at_edit=cmap.context_at(pending_clipboard_cursor),
            final_positions=[None] * len(clipboard),
        )
        for i, ch in enumerate(clipboard):
            cmap.insert(pending_clipboard_cursor + i, ch, (paste_action, i))
        actions.append(paste_action)

    visible_prefix = [0]
    for char, origin in zip(cmap._chars, cmap._origins):
        if char is not None and origin is not None:
            action, offset = origin
            action.final_positions[offset] = visible_prefix[-1]
        visible_prefix.append(visible_prefix[-1] + (char is not None and origin is not None))
    for marker in cmap._markers:
        if marker.final_anchor is not None:
            index = max(0, min(marker.final_anchor, len(cmap._chars)))
            marker.final_anchor = visible_prefix[index]

    final_typed_text = "".join(
        char for char, origin in zip(cmap._chars, cmap._origins)
        if char is not None and origin is not None
    )
    if document_out is not None:
        document_out.append(cmap.get_text())
    return actions, final_typed_text, diagnostics


def _classify_revision_type(episode: RevisionEpisode) -> str:
    if episode.revision_type_hint:
        return episode.revision_type_hint
    if not episode.is_revision:
        return "nt"

    has_delete = any(a.kind == "delete" for a in episode.actions)
    has_replace = any(a.kind == "replace" for a in episode.actions)

    context_complete = episode.actions[0].context_complete if episode.actions else False

    if has_replace:
        return "context" if context_complete else "pre-context"

    if episode.cursor_moved_back:
        return "context" if context_complete else "pre-context"

    if has_delete:
        # Inline backspace without cursor relocation → typo
        return "typo"

    return "nt"


def _group_into_episodes(
    actions: list[WritingAction],
    pause_threshold: int = 2000,
) -> list[RevisionEpisode]:
    if not actions:
        return []

    episodes: list[RevisionEpisode] = []
    current = RevisionEpisode(start_time=actions[0].timestamp)
    last_insert_end = 0
    current_kind = ""

    for action in actions:
        if action.kind == "focus":
            continue

        if action.kind == "move":
            if current.actions:
                current.end_time = action.timestamp
                episodes.append(current)
            current = RevisionEpisode(start_time=action.timestamp)
            if action.position < last_insert_end:
                current.is_revision = True
                current.cursor_moved_back = True
            current_kind = ""
            continue

        if action.kind in ("replace", "cut", "paste"):
            if current.actions:
                current.end_time = action.timestamp
                episodes.append(current)
            ep = RevisionEpisode(
                start_time=action.timestamp, is_revision=(action.kind != "paste"),
            )
            ep.actions.append(action)
            ep.end_time = action.timestamp
            episodes.append(ep)
            current = RevisionEpisode(start_time=action.timestamp)
            current_kind = ""
            continue

        # Linebreak after deletes is an insert — triggers split
        if action.kind == "linebreak":
            if current_kind == "delete" and current.actions:
                current.end_time = action.timestamp
                episodes.append(current)
                current = RevisionEpisode(start_time=action.timestamp)
                current_kind = ""
            current.actions.append(action)
            current.end_time = action.timestamp
            last_insert_end = action.position + 1
            current_kind = "insert"
            continue

        # A position change between inserts is an implicit cursor relocation.
        if (
            action.kind == "insert" and current_kind == "insert"
            and current.actions and action.position != last_insert_end
        ):
            current.end_time = action.timestamp
            episodes.append(current)
            moved_back = action.position < last_insert_end
            current = RevisionEpisode(
                start_time=action.timestamp, is_revision=moved_back,
                cursor_moved_back=moved_back,
            )
            current_kind = ""

        # Split at insert↔delete transitions
        if action.kind == "delete" and current_kind == "insert" and current.actions:
            current.end_time = action.timestamp
            episodes.append(current)
            current = RevisionEpisode(
                start_time=action.timestamp, is_revision=True,
            )
            current_kind = ""
        elif action.kind == "insert" and current_kind == "delete" and current.actions:
            current.end_time = action.timestamp
            episodes.append(current)
            current = RevisionEpisode(start_time=action.timestamp)
            current_kind = ""

        if action.kind == "delete":
            current.is_revision = True
        current.actions.append(action)
        current.end_time = action.timestamp
        current_kind = action.kind

        if action.kind == "insert":
            last_insert_end = action.position + len(action.text)

    if current.actions:
        episodes.append(current)

    return episodes


def _refine_deletion_types(
    episodes: list[RevisionEpisode], diagnostics: list[Diagnostic],
) -> None:
    """Distinguish likely spelling corrections from changes to unfinished text."""
    uncertain_count = 0
    first_uncertain: WritingAction | None = None
    for index, episode in enumerate(episodes):
        if not episode.is_revision or not any(a.kind == "delete" for a in episode.actions):
            continue
        deleted = episode.deleted_text.strip()
        following = episodes[index + 1].net_text.lstrip() if index + 1 < len(episodes) else ""
        replacement = re.match(r"\w+", following)
        replacement_word = replacement.group(0) if replacement else ""
        if not deleted or not replacement_word:
            continue

        same_letter_case_change = deleted.casefold() == replacement_word.casefold()
        similarity = SequenceMatcher(
            None, deleted.casefold(), replacement_word.casefold(),
        ).ratio()
        if same_letter_case_change or (len(deleted) > 1 and similarity >= 0.7):
            episode.revision_type_hint = "typo"
        elif not episode.cursor_moved_back and len(deleted) > 1 and similarity < 0.6:
            episode.revision_type_hint = "pre-context"
            uncertain_count += 1
            if first_uncertain is None:
                first_uncertain = episode.actions[0]
    if first_uncertain is not None:
        diagnostics.append(Diagnostic(
            event_id=first_uncertain.event.event_id if first_uncertain.event else 0,
            timestamp=first_uncertain.timestamp,
            message=f"{uncertain_count} word replacement(s) classified pre-context "
                    "by heuristic; review intended meaning",
        ))


def _find_parent_node(root: TEINode, start: int, end: int) -> TEINode:
    """Find the deepest node whose position range contains [start, end]."""
    for child in root.children:
        if child.start_pos <= start and child.end_pos >= end and child.kind == NodeKind.ADD:
            deeper = _find_parent_node(child, start, end)
            return deeper
    return root


def _episode_pos_range(ep: RevisionEpisode) -> tuple[int, int]:
    positions = [a.position for a in ep.actions if a.position >= 0]
    if not positions:
        return (0, 0)
    start = min(positions)
    end = max(positions)
    for a in ep.actions:
        if a.kind == "insert":
            end = max(end, a.position + len(a.text))
    return (start, end)


def _append_episode_content(ep: RevisionEpisode, target: TEINode) -> None:
    if not ep.has_linebreak:
        content = [a for a in ep.actions if a.kind in ("insert", "paste")]
        positions = (
            [pos for a in content for pos in a.final_positions]
            if all(len(a.final_positions) == len(a.text) for a in content) else []
        )
        target.append(TEINode(kind=NodeKind.TEXT, text=ep.net_text, positions=positions))
        return
    buf: list[str] = []
    buf_positions: list[int | None] = []
    for a in ep.actions:
        if a.kind == "linebreak":
            if buf:
                target.append(TEINode(
                    kind=NodeKind.TEXT, text="".join(buf), positions=buf_positions.copy(),
                ))
                buf.clear()
                buf_positions.clear()
            target.append(TEINode(
                kind=NodeKind.LB,
                final_pos=(a.final_positions[0] if a.final_positions and a.final_positions[0] is not None else -1),
                positions=a.final_positions.copy(),
            ))
        elif a.kind == "insert":
            buf.append(a.text)
            buf_positions.extend(a.final_positions)
    if buf:
        target.append(TEINode(
            kind=NodeKind.TEXT, text="".join(buf), positions=buf_positions,
        ))


def _build_tei_tree(episodes: list[RevisionEpisode]) -> TEINode:
    root = TEINode(kind=NodeKind.SEG, start_pos=0, end_pos=999999)

    def _final_positions_touch(node: TEINode, ep: RevisionEpisode) -> bool:
        """Do not rejoin typing runs separated by later surviving insertions."""
        existing = [
            pos for child in node.children if child.kind in (NodeKind.TEXT, NodeKind.LB)
            for pos in child.positions if pos is not None
        ]
        incoming = [
            pos for action in ep.actions for pos in action.final_positions
            if pos is not None
        ]
        return not existing or not incoming or min(incoming) == max(existing) + 1

    def _make_node(
        kind: NodeKind, text: str, rev_type: str, ep: RevisionEpisode,
        start: int = -1, end: int = -1,
    ) -> TEINode:
        seq = _ms_to_seq(ep.start_time) if ep.start_time or any(
            a.event is not None and a.event.event_type != EventType.REPLACEMENT
            for a in ep.actions
        ) else ""
        evidence = _evidence_from_actions(ep.actions)
        final_positions = [
            pos for action in ep.actions for pos in action.final_positions if pos is not None
        ]
        anchors = [
            action.final_anchor for action in ep.actions if action.final_anchor is not None
        ]
        final_pos = (
            min(anchors) if kind == NodeKind.DEL and anchors
            else min(final_positions) if final_positions else start
        )
        return TEINode(
            kind=kind, text=text, seq=seq, revision_type=rev_type,
            evidence=evidence, start_pos=start, end_pos=end, final_pos=final_pos,
        )

    def _make_action_node(
        kind: NodeKind, text: str, rev_type: str, action: WritingAction,
        start: int = -1, end: int = -1,
    ) -> TEINode:
        seq = _ms_to_seq(action.timestamp) if (
            action.timestamp or (
                action.event is not None
                and action.event.event_type != EventType.REPLACEMENT
            )
        ) else ""
        ev_id = str(action.event.event_id) if action.event else ""
        node = TEINode(
            kind=kind, text=text, seq=seq, revision_type=rev_type,
            evidence=ev_id, start_pos=start, end_pos=end,
            final_pos=(
                action.final_anchor if kind == NodeKind.DEL and action.final_anchor is not None
                else next((pos for pos in action.final_positions if pos is not None), start)
            ),
        )
        if kind == NodeKind.ADD and action.final_positions:
            node.text = ""
            node.append(TEINode(
                kind=NodeKind.TEXT, text=text,
                positions=action.final_positions.copy(),
            ))
        return node

    current_add: TEINode | None = None
    current_add_parent: TEINode = root
    current_add_type: str = "nt"
    prev_ep: RevisionEpisode | None = None
    had_move_since_last_add = False
    interrupted_by_inline_typo = False
    leading_edge_pos: int = 0
    edited_away_from_edge = False

    for ep in episodes:
        rev_type = _classify_revision_type(ep)
        ep_start, ep_end = _episode_pos_range(ep)

        # Track whether a mouse click occurred between episodes
        if ep.cursor_moved_back:
            had_move_since_last_add = True

        follows_revision = prev_ep is not None and prev_ep.is_revision

        # Check for cut/paste episodes
        has_cut = any(a.kind == "cut" for a in ep.actions)
        has_paste = any(a.kind == "paste" for a in ep.actions)
        is_source_paste = has_paste and any(a.kind == "paste" and a.deleted_text == "source" for a in ep.actions)

        # Reclassify: a "revision" episode with only inserts near the leading edge
        # is actually a return to leading edge, not a real revision
        has_only_inserts = all(a.kind in ("insert", "linebreak") for a in ep.actions)
        is_at_leading_edge = has_only_inserts and ep_start == leading_edge_pos
        treat_as_forward = (not ep.is_revision or has_paste or
                           (ep.is_revision and is_at_leading_edge and edited_away_from_edge))

        if treat_as_forward:
            text = ep.net_text
            if not text:
                prev_ep = ep
                continue

            if has_paste:
                # Paste always gets its own node (translocation or source)
                effective_type = "source" if is_source_paste else "translocation"
                node = _make_node(
                    NodeKind.ADD, "", effective_type, ep,
                    start=ep_start, end=ep_start + len(text),
                )
                _append_episode_content(ep, node)
                parent = _find_parent_node(root, ep_start, ep_start + len(text))
                parent.append(node)
                current_add = node
                current_add_parent = parent
                current_add_type = effective_type
                had_move_since_last_add = False
                interrupted_by_inline_typo = False
                leading_edge_pos = max(leading_edge_pos, ep_start + len(text))
            elif follows_revision and current_add is not None and not had_move_since_last_add and interrupted_by_inline_typo:
                # Resume after inline correction → sibling <add type="...|continue">
                base_type = current_add_type.split("|", 1)[0]
                if base_type == "continue":
                    base_type = "nt"
                continue_type = f"{base_type}|continue"
                node = _make_node(
                    NodeKind.ADD, "", continue_type, ep,
                    start=ep_start, end=ep_start + len(text),
                )
                _append_episode_content(ep, node)
                current_add_parent.append(node)
                current_add = node
                # Keep base type so next continue is also "nt|continue", not "nt|continue|continue"
                interrupted_by_inline_typo = False
                leading_edge_pos = max(leading_edge_pos, ep_start + len(text))
            elif edited_away_from_edge and had_move_since_last_add and ep_start == leading_edge_pos:
                # Return to leading edge after editing elsewhere → <mod type="continue">
                node = _make_node(
                    NodeKind.MOD, "", "continue", ep,
                    start=ep_start, end=ep_start + len(text),
                )
                _append_episode_content(ep, node)
                root.append(node)
                current_add = node
                current_add_parent = root
                current_add_type = "continue"
                had_move_since_last_add = False
                edited_away_from_edge = False
                leading_edge_pos = max(leading_edge_pos, ep_start + len(text))
            elif (current_add is not None and ep_start >= current_add.start_pos
                  and ep_start <= current_add.end_pos + 1 and not follows_revision
                  and not ep.force_new_add
                  and _final_positions_touch(current_add, ep)):
                # Continuation within current parent — append content
                _append_episode_content(ep, current_add)
                current_add.end_pos = max(current_add.end_pos, ep_start + len(text))
                leading_edge_pos = max(leading_edge_pos, ep_start + len(text))
            elif follows_revision and current_add is not None and had_move_since_last_add:
                # Continue an insertion after a relocated deletion.
                previous_type = _classify_revision_type(prev_ep)
                if previous_type == "continue":
                    previous_type = "nt"
                node = _make_node(
                    NodeKind.ADD, "", previous_type, ep,
                    start=ep_start, end=ep_start + len(text),
                )
                _append_episode_content(ep, node)
                current_add.append(node)
                current_add.end_pos = max(current_add.end_pos, ep_start + len(text))
            else:
                # New typing burst — create a new parent <add>
                effective_type = rev_type
                node = _make_node(
                    NodeKind.ADD, "", effective_type, ep,
                    start=ep_start, end=ep_start + len(text),
                )
                _append_episode_content(ep, node)
                parent = _find_parent_node(root, ep_start, ep_start + len(text))
                parent.append(node)
                current_add = node
                current_add_parent = parent
                current_add_type = effective_type
                had_move_since_last_add = False
                interrupted_by_inline_typo = False
                leading_edge_pos = max(leading_edge_pos, ep_start + len(text))
        else:
            deleted = ep.deleted_text
            has_replace = any(a.kind == "replace" for a in ep.actions)

            if had_move_since_last_add and ep_end < leading_edge_pos:
                edited_away_from_edge = True

            if current_add is not None and ep_start >= current_add.start_pos and ep_end <= current_add.end_pos + 1:
                target = current_add
                if rev_type in ("typo", "pre-context") and not had_move_since_last_add:
                    interrupted_by_inline_typo = True
            else:
                target = _find_parent_node(root, ep_start, ep_end)

            if has_cut:
                for a in ep.actions:
                    if a.kind == "cut" and a.deleted_text:
                        target.append(_make_action_node(
                            NodeKind.DEL, a.deleted_text, "translocation", a,
                            start=a.position, end=a.position + len(a.deleted_text),
                        ))
            elif has_replace:
                for a in ep.actions:
                    if a.kind == "replace":
                        if a.deleted_text:
                            target.append(_make_action_node(
                                NodeKind.DEL, a.deleted_text, rev_type, a,
                                start=a.position, end=a.position + len(a.deleted_text),
                            ))
                        if a.text:
                            target.append(_make_action_node(
                                NodeKind.ADD, a.text, rev_type, a,
                                start=a.position, end=a.position + len(a.text),
                            ))
            elif deleted:
                if "\n" in deleted:
                    del_node = _make_node(
                        NodeKind.DEL, "", rev_type, ep,
                        start=ep_start, end=ep_start + len(deleted),
                    )
                    parts = deleted.split("\n")
                    for i, part in enumerate(parts):
                        if part:
                            del_node.append(TEINode(kind=NodeKind.TEXT, text=part))
                        if i < len(parts) - 1:
                            del_node.append(TEINode(kind=NodeKind.LB))
                    target.append(del_node)
                else:
                    target.append(_make_node(
                        NodeKind.DEL, deleted, rev_type, ep,
                        start=ep_start, end=ep_start + len(deleted),
                    ))
            elif rev_type in ("pre-context", "context") and ep.net_text:
                # Insertion within existing text after cursor relocation.
                text = ep.net_text
                node = _make_node(
                    NodeKind.ADD, "", rev_type, ep,
                    start=ep_start, end=ep_start + len(text),
                )
                _append_episode_content(ep, node)
                target.append(node)

            if ep_start < leading_edge_pos:
                removed = sum(len(a.deleted_text) for a in ep.actions if a.kind in ("delete", "cut", "replace"))
                inserted = sum(len(a.text) for a in ep.actions if a.kind in ("insert", "linebreak", "replace"))
                leading_edge_pos = max(0, leading_edge_pos + inserted - removed)

        prev_ep = ep

    return root


def _segment_episodes(
    episodes: list[RevisionEpisode],
    pause_threshold: int = 5000,
) -> list[list[RevisionEpisode]]:
    if not episodes:
        return []

    segments: list[list[RevisionEpisode]] = []
    current: list[RevisionEpisode] = []

    for ep in episodes:
        should_split = False

        if current:
            gap = ep.start_time - current[-1].end_time
            if gap > pause_threshold:
                should_split = True

            # Split on sentence boundaries: prev episode's text ends with ". "
            prev_text = current[-1].net_text
            if prev_text and prev_text.rstrip().endswith(".") and not ep.is_revision:
                should_split = True

            # Split when cursor jumps to a very different region
            if ep.is_revision and current[-1].actions and ep.actions:
                prev_pos = current[-1].actions[-1].position
                cur_pos = ep.actions[0].position
                if abs(cur_pos - prev_pos) > 20:
                    should_split = True

        if should_split and current:
            segments.append(current)
            current = []

        current.append(ep)

    if current:
        segments.append(current)

    return segments


_SENTENCE_END = re.compile(r'[.!?]["\'»)\]]?\s|[.!?]["\'»)\]]?$')


def _find_sentence_ranges(text: str) -> list[tuple[int, int]]:
    if not text:
        return [(0, 0)]
    ranges: list[tuple[int, int]] = []
    start = 0
    for m in _SENTENCE_END.finditer(text):
        # An acronym followed by a lowercase word is still inside the same
        # sentence (for example, "U.S. citizens"). Its final dot looks like
        # sentence punctuation to the general boundary expression.
        if m.group().startswith(".") and re.search(r"(?:\b[A-Z]\.)+[A-Z]$", text[:m.start()]):
            following = text[m.end():].lstrip()
            if following and following[0].islower():
                continue
        end = m.end()
        ranges.append((start, end))
        start = end
    if start < len(text):
        ranges.append((start, len(text)))
    if not ranges:
        ranges.append((0, len(text)))
    return ranges


def _segment_by_sentences(
    episodes: list[RevisionEpisode],
    final_text: str,
) -> list[list[RevisionEpisode]]:
    if not episodes:
        return []

    ranges = _find_sentence_ranges(final_text)

    buckets: list[list[RevisionEpisode]] = [[] for _ in ranges]

    def bucket_index(pos: int) -> int:
        for i, (s, e) in enumerate(ranges):
            if s <= pos < e:
                return i
        return len(ranges) - 1

    for ep in episodes:
        # A replacement or paste can insert a whole passage. Divide its
        # surviving characters between the sentences they occupy in the final
        # document. The removed text of a replacement stays in its first
        # sentence; paste source metadata applies to every resulting piece.
        if len(ep.actions) == 1 and ep.actions[0].kind in ("replace", "paste"):
            action = ep.actions[0]
            if action.text and len(action.final_positions) == len(action.text):
                runs: list[tuple[int, int, int]] = []
                for offset, final_pos in enumerate(action.final_positions):
                    index = bucket_index(final_pos if final_pos is not None else action.position + offset)
                    if not runs or runs[-1][0] != index:
                        runs.append((index, offset, offset + 1))
                    else:
                        previous_index, start, _ = runs[-1]
                        runs[-1] = (previous_index, start, offset + 1)
                if len(runs) > 1:
                    for run_number, (index, start, end) in enumerate(runs):
                        piece = replace(
                            action,
                            position=action.position + start,
                            text=action.text[start:end],
                            deleted_text=(action.deleted_text if action.kind == "paste"
                                          or run_number == 0 else ""),
                            final_positions=action.final_positions[start:end],
                        )
                        buckets[index].append(replace(ep, actions=[piece]))
                    continue

        if not all(a.kind in ("insert", "linebreak") for a in ep.actions):
            final_positions = [
                pos for action in ep.actions for pos in action.final_positions if pos is not None
            ]
            anchors = [
                action.final_anchor for action in ep.actions if action.final_anchor is not None
            ]
            ep_start, _ = _episode_pos_range(ep)
            anchor = min(final_positions or anchors or [ep_start])
            buckets[bucket_index(anchor)].append(ep)
            continue

        runs: list[tuple[int, list[WritingAction]]] = []
        previous_final_pos: int | None = None
        for action in ep.actions:
            for offset, char in enumerate(action.text):
                current_final_pos = (
                    action.final_positions[offset]
                    if offset < len(action.final_positions) else None
                )
                pos = current_final_pos if current_final_pos is not None else action.position + offset
                index = bucket_index(pos)
                gap = (
                    current_final_pos is not None and previous_final_pos is not None
                    and (current_final_pos < previous_final_pos or current_final_pos - previous_final_pos > 1)
                )
                if not runs or runs[-1][0] != index or gap:
                    runs.append((index, []))
                runs[-1][1].append(replace(
                    action, position=action.position + offset,
                    text=char,
                    final_positions=[current_final_pos] if action.final_positions else [],
                ))
                if current_final_pos is not None:
                    previous_final_pos = current_final_pos

        if len(runs) <= 1:
            index = runs[0][0] if runs else bucket_index(_episode_pos_range(ep)[0])
            buckets[index].append(ep)
        else:
            for run_index, (index, actions) in enumerate(runs):
                buckets[index].append(replace(
                    ep, actions=actions, start_time=actions[0].timestamp,
                    end_time=actions[-1].timestamp,
                    force_new_add=run_index > 0 and runs[run_index - 1][0] == index,
                ))

    return [b for b in buckets if b]


@dataclass
class FocusEvent:
    app_name: str
    timestamp: int
    event_id: int

@dataclass
class ConversionResult:
    segments: list[TEINode]
    final_text: str
    actions: list[WritingAction]
    episodes: list[RevisionEpisode]
    final_document_text: str = ""
    metadata: SessionMetadata | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    stats: ConversionStats = field(default_factory=ConversionStats)
    focus_sources: list[FocusEvent] = field(default_factory=list)
    source_paste_indices: set[int] = field(default_factory=set)


def _compute_stats(
    events: list[Event],
    actions: list[WritingAction],
    episodes: list[RevisionEpisode],
    segments: list[TEINode],
    diagnostics: list[Diagnostic],
    parse_warnings: int = 0,
) -> ConversionStats:
    return ConversionStats(
        total_events=len(events),
        typed_chars=sum(len(a.text) for a in actions if a.kind in ("insert", "linebreak")),
        deletions=sum(1 for a in actions if a.kind == "delete"),
        replacements=sum(1 for a in actions if a.kind == "replace"),
        moves=sum(1 for a in actions if a.kind == "move"),
        drift_count=sum(1 for d in diagnostics if "drift" in d.message),
        unknown_deletions=sum(1 for d in diagnostics if "unknown deleted" in d.message),
        episodes=len(episodes),
        segments=len(segments),
        parse_warnings=parse_warnings,
    )


def _detect_focus_sources(actions: list[WritingAction]) -> tuple[list[FocusEvent], set[int]]:
    focus_sources: list[FocusEvent] = []
    source_paste_indices: set[int] = set()

    last_focus_out: FocusEvent | None = None
    for i, a in enumerate(actions):
        if a.kind == "focus":
            ev_id = a.event.event_id if a.event else 0
            fe = FocusEvent(app_name=a.text, timestamp=a.timestamp, event_id=ev_id)
            focus_sources.append(fe)
            last_focus_out = fe
        elif a.kind == "paste" and last_focus_out is not None:
            source_paste_indices.add(i)
            last_focus_out = None
        elif a.kind not in ("move",):
            last_focus_out = None

    return focus_sources, source_paste_indices


def _get_node_text(node: TEINode) -> str:
    if node.text and not node.children:
        return node.text
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node.children:
        if child.kind == NodeKind.TEXT:
            parts.append(child.text)
    return "".join(parts)


def _hoist_misplaced_additions(node: TEINode) -> None:
    for child in list(node.children):
        _hoist_misplaced_additions(child)

    for child in list(node.children):
        if child.kind not in (NodeKind.ADD, NodeKind.MOD):
            continue
        own_positions = [
            pos for item in child.children
            if item.kind in (NodeKind.TEXT, NodeKind.LB)
            for pos in item.positions if pos is not None
        ]
        for nested in list(child.children):
            if nested.kind not in (NodeKind.ADD, NodeKind.MOD):
                continue
            nested_positions = [
                pos for item in nested.children
                if item.kind in (NodeKind.TEXT, NodeKind.LB)
                for pos in item.positions if pos is not None
            ]
            anchor = min(nested_positions) if nested_positions else nested.final_pos
            if not own_positions or anchor < min(own_positions) or anchor > max(own_positions):
                child.children.remove(nested)
                node.children.append(nested)


def _interleave_text_with_revisions(node: TEINode) -> None:
    def surviving_positions(parent: TEINode) -> list[int]:
        positions = [pos for pos in parent.positions if pos is not None]
        if parent.kind == NodeKind.LB and parent.final_pos >= 0:
            positions.append(parent.final_pos)
        for descendant in parent.children:
            if descendant.kind != NodeKind.DEL:
                positions.extend(surviving_positions(descendant))
        return positions

    def effective_pos(child: TEINode) -> int:
        positions = surviving_positions(child) if child.kind in (NodeKind.ADD, NodeKind.MOD) else []
        return min(positions) if positions else child.final_pos

    if node.kind in (NodeKind.SEG, NodeKind.ADD, NodeKind.MOD):

        additions = [
            child for child in node.children if child.kind in (NodeKind.ADD, NodeKind.MOD)
        ]
        spans: dict[int, tuple[int, int]] = {}
        for child in additions:
            positions = surviving_positions(child)
            if positions:
                spans[id(child)] = (min(positions), max(positions))
        nested_ids: set[int] = set()
        for child in additions:
            child_position = effective_pos(child)
            if child_position < 0:
                continue
            child_span = spans.get(id(child), (child_position, child_position))
            candidates = [
                parent for parent in additions if parent is not child
                and id(parent) in spans
                and spans[id(parent)][0] < child_span[0] <= spans[id(parent)][1]
            ]
            if candidates:
                parent = min(
                    candidates,
                    key=lambda candidate: child_span[0] - spans[id(candidate)][0],
                )
                parent.append(child)
                nested_ids.add(id(child))
        node.children = [child for child in node.children if id(child) not in nested_ids]

        if node.kind == NodeKind.SEG:
            node.children.sort(key=lambda child: (
                min(surviving_positions(child))
                if surviving_positions(child) else effective_pos(child),
                0 if child.kind == NodeKind.DEL else 1,
            ))

    for child in node.children:
        if child.kind in (NodeKind.ADD, NodeKind.MOD, NodeKind.SEG):
            _interleave_text_with_revisions(child)

    if node.kind not in (NodeKind.ADD, NodeKind.MOD, NodeKind.SEG):
        return

    text_items: list[TEINode] = []
    revision_items: list[TEINode] = []
    unpositioned: list[TEINode] = []

    for child in node.children:
        if child.kind in (NodeKind.TEXT, NodeKind.LB):
            text_items.append(child)
        elif child.start_pos >= 0:
            revision_items.append(child)
        else:
            unpositioned.append(child)

    positioned = any(item.positions for item in text_items)
    if not text_items or (not revision_items and not positioned):
        return

    # Build position-indexed buffer from surviving character provenance.
    buf: list[tuple[int, str | TEINode]] = []
    pos = node.start_pos if node.start_pos >= 0 else 0
    for item in text_items:
        if item.kind == NodeKind.TEXT:
            for offset, ch in enumerate(item.text):
                final_pos = (
                    item.positions[offset]
                    if positioned and offset < len(item.positions) else pos
                )
                if final_pos is not None:
                    buf.append((final_pos, ch))
                pos += 1
        elif item.kind == NodeKind.LB:
            if positioned and item.positions and item.positions[0] is None:
                pos += 1
                continue
            final_pos = item.final_pos if positioned and item.final_pos >= 0 else pos
            buf.append((final_pos, item))
            pos += 1
    if positioned:
        buf.sort(key=lambda entry: entry[0])

    # Sort revisions by position (DEL before ADD at same position)
    revision_items.sort(key=lambda r: (
        effective_pos(r) if positioned and effective_pos(r) >= 0 else r.start_pos,
        0 if r.kind == NodeKind.DEL else 1,
    ))

    # Walk buffer and revisions together
    new_children: list[TEINode] = []
    text_acc: list[str] = []
    text_positions: list[int] = []
    buf_idx = 0
    rev_idx = 0

    while buf_idx < len(buf) or rev_idx < len(revision_items):
        # Check if next revision should be inserted before current buffer position
        if rev_idx < len(revision_items):
            rev = revision_items[rev_idx]
            cur_buf_pos = buf[buf_idx][0] if buf_idx < len(buf) else float("inf")

            rev_position = effective_pos(rev) if positioned and effective_pos(rev) >= 0 else rev.start_pos
            if rev_position <= cur_buf_pos:
                if text_acc:
                    new_children.append(TEINode(
                        kind=NodeKind.TEXT, text="".join(text_acc), positions=text_positions.copy(),
                    ))
                    text_acc.clear()
                    text_positions.clear()

                # Collect all revisions at this position
                rev_pos = rev_position
                while rev_idx < len(revision_items) and (
                    effective_pos(revision_items[rev_idx])
                    if positioned and effective_pos(revision_items[rev_idx]) >= 0
                    else revision_items[rev_idx].start_pos
                ) == rev_pos:
                    r = revision_items[rev_idx]
                    new_children.append(r)
                    # Skip deleted chars in buffer
                    if r.kind == NodeKind.DEL and not positioned:
                        del_len = len(_get_node_text(r))
                        skipped = 0
                        while skipped < del_len and buf_idx < len(buf):
                            _, val = buf[buf_idx]
                            if isinstance(val, str):
                                buf_idx += 1
                                skipped += 1
                            else:
                                break
                    rev_idx += 1
                continue

        if buf_idx < len(buf):
            buf_pos, val = buf[buf_idx]
            if isinstance(val, str):
                text_acc.append(val)
                text_positions.append(buf_pos)
            else:
                if text_acc:
                    new_children.append(TEINode(
                        kind=NodeKind.TEXT, text="".join(text_acc), positions=text_positions.copy(),
                    ))
                    text_acc.clear()
                    text_positions.clear()
                new_children.append(val)
            buf_idx += 1

    if text_acc:
        new_children.append(TEINode(
            kind=NodeKind.TEXT, text="".join(text_acc), positions=text_positions,
        ))

    new_children.extend(unpositioned)
    node.children = new_children


def _is_empty_content_node(node: TEINode) -> bool:
    if node.kind not in (NodeKind.ADD, NodeKind.DEL):
        return False
    if any(c.kind not in (NodeKind.TEXT,) for c in node.children):
        return False
    all_text = (node.text or "") + "".join(c.text for c in node.children if c.kind == NodeKind.TEXT)
    return not all_text


def _strip_empty_content_nodes(node: TEINode) -> None:
    for child in node.children:
        _strip_empty_content_nodes(child)
    node.children = [c for c in node.children if not _is_empty_content_node(c)]


def _audit_notation(segments: list[TEINode]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    evidence_seen: set[str] = set()

    def visit(node: TEINode) -> None:
        if node.kind in (NodeKind.ADD, NodeKind.DEL, NodeKind.MOD):
            event_id = int(node.evidence.split("-", 1)[0]) if node.evidence else 0
            if not node.seq:
                diagnostics.append(Diagnostic(
                    event_id, 0, "missing @seq; source event has no usable timestamp", "warning",
                ))
            if not node.evidence:
                diagnostics.append(Diagnostic(
                    event_id, 0, "missing @evidence for writing action", "warning",
                ))
            elif node.evidence in evidence_seen:
                diagnostics.append(Diagnostic(
                    event_id, 0, f"repeated @evidence={node.evidence}; source event maps to multiple operations",
                    "warning",
                ))
            evidence_seen.add(node.evidence)
        for child in node.children:
            visit(child)

    for segment in segments:
        visit(segment)
    return diagnostics


def _visible_text(node: TEINode) -> str:
    if node.kind == NodeKind.DEL:
        return ""
    if node.kind == NodeKind.LB:
        return "\n"
    return node.text + "".join(_visible_text(child) for child in node.children)


def convert(
    events: list[Event],
    metadata: SessionMetadata | None = None,
    parse_warnings: int = 0,
    initial_text: str = "",
) -> ConversionResult:
    final_document: list[str] = []
    actions, final_text, diagnostics = _process_events(events, initial_text, final_document)

    focus_sources, source_paste_indices = _detect_focus_sources(actions)

    # Mark source pastes in actions for _build_tei_tree
    for i in source_paste_indices:
        actions[i] = WritingAction(
            kind="paste", position=actions[i].position, text=actions[i].text,
            deleted_text="source", event=actions[i].event, timestamp=actions[i].timestamp,
            context_complete=actions[i].context_complete,
            final_positions=actions[i].final_positions,
        )

    episodes = _group_into_episodes(actions)
    _refine_deletion_types(episodes, diagnostics)
    segment_groups = _segment_by_sentences(episodes, final_text)

    segments: list[TEINode] = []
    for group in segment_groups:
        seg = _build_tei_tree(group)
        if seg.children:
            _hoist_misplaced_additions(seg)
            _interleave_text_with_revisions(seg)
            _strip_empty_content_nodes(seg)
            if seg.children:
                segments.append(seg)

    diagnostics.extend(_audit_notation(segments))
    projected_text = "".join(_visible_text(seg) for seg in segments)
    if projected_text != final_text:
        mismatch = next(
            (i for i, (actual, expected) in enumerate(zip(projected_text, final_text))
             if actual != expected),
            min(len(projected_text), len(final_text)),
        )
        diagnostics.append(Diagnostic(
            0, 0,
            f"TEI reading text differs from replayed text at character {mismatch}; "
            "review overlapping revisions or lost line breaks",
            "warning",
        ))

    stats = _compute_stats(events, actions, episodes, segments, diagnostics, parse_warnings)

    return ConversionResult(
        segments=segments,
        final_text=final_text,
        actions=actions,
        episodes=episodes,
        final_document_text=final_document[0],
        metadata=metadata,
        diagnostics=diagnostics,
        stats=stats,
        focus_sources=focus_sources,
        source_paste_indices=source_paste_indices,
    )
