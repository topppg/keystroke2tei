from __future__ import annotations

import re
from dataclasses import dataclass, field

from keystroke2tei.models import ConversionStats, Diagnostic, Event, EventType, NodeKind, SessionMetadata, TEINode


SPECIAL_KEYS = {"SPACE", "BACK", "DELETE", "RETURN", "TAB"}
NAV_KEYS = {"LEFT", "RIGHT", "UP", "DOWN", "HOME", "END", "PAGEUP", "PAGEDOWN"}
IGNORED_KEYS = {"CAPSLOCK", "NUMLOCK", "SCROLL", "INSERT", "ESCAPE", "PRINT", "PAUSE",
                "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
                "LCTRL", "RCTRL", "LALT", "RALT", "LSHIFT", "RSHIFT"}
MODIFIER_PATTERN = re.compile(r"^(LCTRL|RCTRL|LALT|RALT|LSHIFT|RSHIFT)\s*\+")
REPLACEMENT_PATTERN = re.compile(r"^\[(\d+):(\d+)\]\s*(.*)")


def _ms_to_seq(ms: int) -> str:
    """Convert milliseconds to hhmmss timestamp for @seq attribute."""
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


@dataclass
class CharMap:
    """Position-indexed character map. None = unknown (autocomplete-inserted)."""
    _chars: list[str | None] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self._chars)

    def pad_to(self, target_len: int) -> None:
        if target_len > self.length:
            self._chars.extend([None] * (target_len - self.length))

    def insert(self, pos: int, char: str) -> None:
        pos = max(0, min(pos, self.length))
        self._chars.insert(pos, char)

    def delete(self, pos: int) -> str:
        if 0 <= pos < self.length:
            ch = self._chars.pop(pos)
            return ch if ch is not None else ""
        return ""

    def replace_range(self, start: int, end: int, new_text: str) -> str:
        start = max(0, start)
        end = min(end, self.length)
        old_chars = self._chars[start:end]
        old_text = "".join(c for c in old_chars if c is not None)
        del self._chars[start:end]
        for i, ch in enumerate(new_text):
            self._chars.insert(start + i, ch)
        return old_text

    def get_text(self) -> str:
        return "".join(c for c in self._chars if c is not None)


@dataclass
class RevisionEpisode:
    actions: list[WritingAction] = field(default_factory=list)
    start_time: int = 0
    end_time: int = 0
    is_revision: bool = False
    cursor_moved_back: bool = False

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


def _process_events(events: list[Event]) -> tuple[list[WritingAction], str, list[Diagnostic]]:
    cmap = CharMap()
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
                for _ in range(cut_len):
                    if pending_clipboard_cursor < cmap.length:
                        ch = cmap.delete(pending_clipboard_cursor)
                        cut_text += ch if ch else ""
                clipboard = cut_text
                if cut_text and pending_clipboard_ev:
                    actions.append(WritingAction(
                        kind="cut", position=pending_clipboard_cursor,
                        deleted_text=cut_text, event=pending_clipboard_ev,
                        timestamp=pending_clipboard_ev.start_time,
                    ))
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
                    for i, ch in enumerate(paste_text):
                        cmap.insert(pending_clipboard_cursor + i, ch)
                    actions.append(WritingAction(
                        kind="paste", position=pending_clipboard_cursor,
                        text=paste_text, event=pending_clipboard_ev,
                        timestamp=pending_clipboard_ev.start_time,
                    ))
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
                old_text = cmap.replace_range(start, end, new_text)
                if old_text != new_text:
                    actions.append(WritingAction(
                        kind="replace", position=start, text=new_text,
                        deleted_text=old_text, event=ev, timestamp=ev.start_time,
                    ))
                else:
                    diagnostics.append(Diagnostic(
                        event_id=ev.event_id, timestamp=ev.start_time,
                        message=f"identity replacement skipped at [{start}:{end}]",
                    ))
            continue

        if ev.event_type == EventType.KEYBOARD:
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

            if key == "BACK":
                del_pos = cursor - 1
                if del_pos >= 0:
                    deleted = cmap.delete(del_pos)
                    if not deleted:
                        diagnostics.append(Diagnostic(
                            event_id=ev.event_id, timestamp=ev.start_time,
                            message=f"unknown deleted char at position {del_pos}",
                            level="warning",
                        ))
                    actions.append(WritingAction(
                        kind="delete", position=del_pos,
                        deleted_text=deleted, event=ev, timestamp=ev.start_time,
                    ))
            elif key == "DELETE":
                if cursor < cmap.length:
                    deleted = cmap.delete(cursor)
                    if not deleted:
                        diagnostics.append(Diagnostic(
                            event_id=ev.event_id, timestamp=ev.start_time,
                            message=f"unknown deleted char at position {cursor}",
                            level="warning",
                        ))
                    actions.append(WritingAction(
                        kind="delete", position=cursor,
                        deleted_text=deleted, event=ev, timestamp=ev.start_time,
                    ))
            elif key == "RETURN":
                cmap.insert(cursor, "\n")
                actions.append(WritingAction(
                    kind="linebreak", position=cursor, text="\n",
                    event=ev, timestamp=ev.start_time,
                ))
            elif key in ("CTRL+X", "CTRL+C", "CTRL+V"):
                pending_clipboard_op = key
                pending_clipboard_ev = ev
                pending_clipboard_cursor = cursor
            else:
                for i, ch in enumerate(key):
                    cmap.insert(cursor + i, ch)
                actions.append(WritingAction(
                    kind="insert", position=cursor, text=key,
                    event=ev, timestamp=ev.start_time,
                ))

            prev_cursor = ev.position

    # Resolve any trailing clipboard op (last event was cut/copy/paste)
    if pending_clipboard_op == "CTRL+V" and clipboard and pending_clipboard_ev:
        for i, ch in enumerate(clipboard):
            cmap.insert(pending_clipboard_cursor + i, ch)
        actions.append(WritingAction(
            kind="paste", position=pending_clipboard_cursor,
            text=clipboard, event=pending_clipboard_ev,
            timestamp=pending_clipboard_ev.start_time,
        ))

    return actions, cmap.get_text(), diagnostics


def _classify_revision_type(episode: RevisionEpisode) -> str:
    if not episode.is_revision:
        return "nt"

    has_delete = any(a.kind == "delete" for a in episode.actions)
    has_replace = any(a.kind == "replace" for a in episode.actions)

    if has_replace:
        return "context"

    if episode.cursor_moved_back:
        if has_delete:
            return "context"
        # Cursor relocated backward, insertion only → pre-context
        return "pre-context"

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
            continue

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

        current.actions.append(action)
        current.end_time = action.timestamp
        current_kind = action.kind

        if action.kind == "insert":
            last_insert_end = action.position + len(action.text)

    if current.actions:
        episodes.append(current)

    return episodes


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
        target.append(TEINode(kind=NodeKind.TEXT, text=ep.net_text))
        return
    buf: list[str] = []
    for a in ep.actions:
        if a.kind == "linebreak":
            if buf:
                target.append(TEINode(kind=NodeKind.TEXT, text="".join(buf)))
                buf.clear()
            target.append(TEINode(kind=NodeKind.LB))
        elif a.kind == "insert":
            buf.append(a.text)
    if buf:
        target.append(TEINode(kind=NodeKind.TEXT, text="".join(buf)))


def _build_tei_tree(episodes: list[RevisionEpisode]) -> TEINode:
    root = TEINode(kind=NodeKind.SEG, start_pos=0, end_pos=999999)

    def _make_node(
        kind: NodeKind, text: str, rev_type: str, ep: RevisionEpisode,
        start: int = -1, end: int = -1,
    ) -> TEINode:
        seq = _ms_to_seq(ep.start_time) if ep.start_time else ""
        evidence = _evidence_from_actions(ep.actions)
        return TEINode(
            kind=kind, text=text, seq=seq, revision_type=rev_type,
            evidence=evidence, start_pos=start, end_pos=end,
        )

    def _make_action_node(
        kind: NodeKind, text: str, rev_type: str, action: WritingAction,
        start: int = -1, end: int = -1,
    ) -> TEINode:
        seq = _ms_to_seq(action.timestamp) if action.timestamp else ""
        ev_id = str(action.event.event_id) if action.event else ""
        return TEINode(
            kind=kind, text=text, seq=seq, revision_type=rev_type,
            evidence=ev_id, start_pos=start, end_pos=end,
        )

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
        is_at_leading_edge = has_only_inserts and abs(ep_start - leading_edge_pos) <= 2
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
                continue_type = f"{current_add_type}|continue"
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
            elif edited_away_from_edge and had_move_since_last_add and abs(ep_start - leading_edge_pos) <= 2:
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
            elif current_add is not None and ep_start >= current_add.start_pos and ep_start <= current_add.end_pos + 1 and not follows_revision:
                # Continuation within current parent — append content
                _append_episode_content(ep, current_add)
                current_add.end_pos = max(current_add.end_pos, ep_start + len(text))
                leading_edge_pos = max(leading_edge_pos, ep_start + len(text))
            elif follows_revision and current_add is not None and had_move_since_last_add:
                # Return after editing elsewhere → <add type="context">
                node = _make_node(
                    NodeKind.ADD, "", "context", ep,
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
                if rev_type == "typo" and not had_move_since_last_add:
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
                                NodeKind.DEL, a.deleted_text, "context", a,
                                start=a.position, end=a.position + len(a.deleted_text),
                            ))
                        if a.text:
                            target.append(_make_action_node(
                                NodeKind.ADD, a.text, "context", a,
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
            elif rev_type == "pre-context" and ep.net_text:
                # Pre-context: insertion within existing text after cursor relocation
                text = ep.net_text
                node = _make_node(
                    NodeKind.ADD, "", "pre-context", ep,
                    start=ep_start, end=ep_start + len(text),
                )
                _append_episode_content(ep, node)
                target.append(node)

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

    for ep in episodes:
        ep_start, _ = _episode_pos_range(ep)
        assigned = False
        for i, (s, e) in enumerate(ranges):
            if s <= ep_start < e:
                buckets[i].append(ep)
                assigned = True
                break
        if not assigned:
            buckets[-1].append(ep)

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


def _interleave_text_with_revisions(node: TEINode) -> None:
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

    if not text_items or not revision_items:
        return

    # Build position-indexed buffer: list of (abs_pos, char_or_lb_node)
    buf: list[tuple[int, str | TEINode]] = []
    pos = node.start_pos if node.start_pos >= 0 else 0
    for item in text_items:
        if item.kind == NodeKind.TEXT:
            for ch in item.text:
                buf.append((pos, ch))
                pos += 1
        elif item.kind == NodeKind.LB:
            buf.append((pos, item))
            pos += 1

    # Sort revisions by position (DEL before ADD at same position)
    revision_items.sort(key=lambda r: (r.start_pos, 0 if r.kind == NodeKind.DEL else 1))

    # Walk buffer and revisions together
    new_children: list[TEINode] = []
    text_acc: list[str] = []
    buf_idx = 0
    rev_idx = 0

    while buf_idx < len(buf) or rev_idx < len(revision_items):
        # Check if next revision should be inserted before current buffer position
        if rev_idx < len(revision_items):
            rev = revision_items[rev_idx]
            cur_buf_pos = buf[buf_idx][0] if buf_idx < len(buf) else float("inf")

            if rev.start_pos <= cur_buf_pos:
                if text_acc:
                    new_children.append(TEINode(kind=NodeKind.TEXT, text="".join(text_acc)))
                    text_acc.clear()

                # Collect all revisions at this position
                rev_pos = rev.start_pos
                while rev_idx < len(revision_items) and revision_items[rev_idx].start_pos == rev_pos:
                    r = revision_items[rev_idx]
                    new_children.append(r)
                    # Skip deleted chars in buffer
                    if r.kind == NodeKind.DEL:
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
            _, val = buf[buf_idx]
            if isinstance(val, str):
                text_acc.append(val)
            else:
                if text_acc:
                    new_children.append(TEINode(kind=NodeKind.TEXT, text="".join(text_acc)))
                    text_acc.clear()
                new_children.append(val)
            buf_idx += 1

    if text_acc:
        new_children.append(TEINode(kind=NodeKind.TEXT, text="".join(text_acc)))

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


def convert(
    events: list[Event],
    metadata: SessionMetadata | None = None,
    parse_warnings: int = 0,
) -> ConversionResult:
    actions, final_text, diagnostics = _process_events(events)

    focus_sources, source_paste_indices = _detect_focus_sources(actions)

    # Mark source pastes in actions for _build_tei_tree
    for i in source_paste_indices:
        actions[i] = WritingAction(
            kind="paste", position=actions[i].position, text=actions[i].text,
            deleted_text="source", event=actions[i].event, timestamp=actions[i].timestamp,
        )

    episodes = _group_into_episodes(actions)
    segment_groups = _segment_by_sentences(episodes, final_text)

    segments: list[TEINode] = []
    for group in segment_groups:
        seg = _build_tei_tree(group)
        if seg.children:
            _interleave_text_with_revisions(seg)
            _strip_empty_content_nodes(seg)
            if seg.children:
                segments.append(seg)

    stats = _compute_stats(events, actions, episodes, segments, diagnostics, parse_warnings)

    return ConversionResult(
        segments=segments,
        final_text=final_text,
        actions=actions,
        episodes=episodes,
        metadata=metadata,
        diagnostics=diagnostics,
        stats=stats,
        focus_sources=focus_sources,
        source_paste_indices=source_paste_indices,
    )
