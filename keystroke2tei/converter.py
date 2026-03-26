from __future__ import annotations

import re
from dataclasses import dataclass, field

from keystroke2tei.models import ConversionStats, Diagnostic, Event, EventType, NodeKind, SessionMetadata, TEINode


SPECIAL_KEYS = {"SPACE", "BACK", "DELETE", "RETURN", "TAB"}
NAV_KEYS = {"LEFT", "RIGHT", "UP", "DOWN", "HOME", "END", "PAGEUP", "PAGEDOWN"}
IGNORED_KEYS = {"CAPSLOCK", "NUMLOCK", "SCROLL", "INSERT", "ESCAPE", "PRINT", "PAUSE",
                "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"}
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
            if a.kind == "insert":
                parts.append(a.text)
        return "".join(parts)

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
    normalized = KEY_ALIASES.get(output, output)
    if normalized == "SPACE":
        return " "
    if normalized == "BACK":
        return "BACK"
    if normalized == "DELETE":
        return "DELETE"
    if normalized == "RETURN":
        return "\n"
    if normalized == "TAB":
        return "\t"
    if normalized in NAV_KEYS:
        return "NAV"
    if normalized in IGNORED_KEYS:
        return "UNKNOWN"
    if MODIFIER_PATTERN.match(output):
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

    for ev in events:
        if ev.event_type == EventType.FOCUS:
            continue

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
            else:
                for i, ch in enumerate(key):
                    cmap.insert(cursor + i, ch)
                actions.append(WritingAction(
                    kind="insert", position=cursor, text=key,
                    event=ev, timestamp=ev.start_time,
                ))

            prev_cursor = ev.position

    return actions, cmap.get_text(), diagnostics


def _classify_revision_type(episode: RevisionEpisode) -> str:
    if not episode.is_revision:
        return "nt"

    has_delete = any(a.kind == "delete" for a in episode.actions)
    has_replace = any(a.kind == "replace" for a in episode.actions)

    if has_replace:
        return "context"

    if episode.cursor_moved_back:
        # Cursor was relocated (mouse click) → context revision
        return "context"

    if has_delete:
        # Inline backspace without cursor relocation → typo
        return "typo"

    # Insert at cursor-moved-back position
    if episode.cursor_moved_back:
        return "pre-context"

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

        if action.kind == "replace":
            if current.actions:
                current.end_time = action.timestamp
                episodes.append(current)
            ep = RevisionEpisode(
                start_time=action.timestamp, is_revision=True,
            )
            ep.actions.append(action)
            ep.end_time = action.timestamp
            episodes.append(ep)
            current = RevisionEpisode(start_time=action.timestamp)
            current_kind = ""
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
    prev_ep: RevisionEpisode | None = None
    had_move_since_last_add = False

    for ep in episodes:
        rev_type = _classify_revision_type(ep)
        ep_start, ep_end = _episode_pos_range(ep)

        # Track whether a mouse click occurred between episodes
        if prev_ep and any(a.kind == "move" for a in ep.actions):
            had_move_since_last_add = True

        follows_revision = prev_ep is not None and prev_ep.is_revision

        if not ep.is_revision:
            text = ep.net_text
            if not text:
                prev_ep = ep
                continue

            if current_add is not None and ep_start >= current_add.start_pos and ep_start <= current_add.end_pos + 1:
                # Continuation within current parent — append as plain text
                current_add.append(TEINode(kind=NodeKind.TEXT, text=text))
                current_add.end_pos = max(current_add.end_pos, ep_start + len(text))
            elif follows_revision and current_add is not None:
                if had_move_since_last_add:
                    # Return after editing elsewhere → <add type="context">
                    current_add.append(_make_node(
                        NodeKind.ADD, text, "context", ep,
                        start=ep_start, end=ep_start + len(text),
                    ))
                else:
                    # Resume after inline correction → plain text (nt|continue)
                    current_add.append(TEINode(kind=NodeKind.TEXT, text=text))
                current_add.end_pos = max(current_add.end_pos, ep_start + len(text))
            else:
                # New typing burst — create a new parent <add>
                node = _make_node(
                    NodeKind.ADD, text, rev_type, ep,
                    start=ep_start, end=ep_start + len(text),
                )
                parent = _find_parent_node(root, ep_start, ep_start + len(text))
                parent.append(node)
                current_add = node
                had_move_since_last_add = False
        else:
            deleted = ep.deleted_text
            has_replace = any(a.kind == "replace" for a in ep.actions)

            if current_add is not None and ep_start >= current_add.start_pos and ep_end <= current_add.end_pos + 1:
                target = current_add
            else:
                target = _find_parent_node(root, ep_start, ep_end)

            if has_replace:
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
                target.append(_make_node(
                    NodeKind.DEL, deleted, rev_type, ep,
                    start=ep_start, end=ep_start + len(deleted),
                ))

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


@dataclass
class ConversionResult:
    segments: list[TEINode]
    final_text: str
    actions: list[WritingAction]
    episodes: list[RevisionEpisode]
    metadata: SessionMetadata | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    stats: ConversionStats = field(default_factory=ConversionStats)


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
        typed_chars=sum(len(a.text) for a in actions if a.kind == "insert"),
        deletions=sum(1 for a in actions if a.kind == "delete"),
        replacements=sum(1 for a in actions if a.kind == "replace"),
        moves=sum(1 for a in actions if a.kind == "move"),
        drift_count=sum(1 for d in diagnostics if "drift" in d.message),
        unknown_deletions=sum(1 for d in diagnostics if "unknown deleted" in d.message),
        episodes=len(episodes),
        segments=len(segments),
        parse_warnings=parse_warnings,
    )


def convert(
    events: list[Event],
    metadata: SessionMetadata | None = None,
    parse_warnings: int = 0,
) -> ConversionResult:
    actions, final_text, diagnostics = _process_events(events)
    episodes = _group_into_episodes(actions)
    segment_groups = _segment_episodes(episodes)

    segments: list[TEINode] = []
    for group in segment_groups:
        seg = _build_tei_tree(group)
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
    )
