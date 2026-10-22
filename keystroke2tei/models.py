from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class SessionMetadata:
    participant: str = ""
    language: str = ""
    date: str = ""
    session: str = ""
    filepath: str = ""


class EventType(Enum):
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    FOCUS = "focus"
    REPLACEMENT = "replacement"


@dataclass
class Event:
    event_type: EventType
    event_id: int
    output: str
    char_production: int
    action_time: int
    start_time: int
    end_time: int
    pause_location: int
    pause_location_full: str
    pause_time: int
    position: int
    doclength: int
    x: int | None = None
    y: int | None = None
    replay: bool = True


class RevisionType(Enum):
    NEW_TEXT = "nt"
    TYPO = "typo"
    CONTEXT = "context"
    PRE_CONTEXT = "pre-context"
    CONTINUATION = "continue"


class NodeKind(Enum):
    ADD = "add"
    DEL = "del"
    MOD = "mod"
    SEG = "seg"
    TEXT = "text"
    LB = "lb"
    MEDIA = "media"
    DESC = "desc"


@dataclass
class TEINode:
    kind: NodeKind
    text: str = ""
    seq: str = ""
    revision_type: str = ""
    evidence: str = ""
    children: list[TEINode] = field(default_factory=list)
    start_pos: int = -1
    end_pos: int = -1
    final_pos: int = -1
    positions: list[int | None] = field(default_factory=list)

    def append(self, child: TEINode) -> None:
        self.children.append(child)


@dataclass
class Diagnostic:
    event_id: int
    timestamp: int
    message: str
    level: str = "info"  # "info" or "warning"


@dataclass
class ConversionStats:
    total_events: int = 0
    typed_chars: int = 0
    deletions: int = 0
    replacements: int = 0
    moves: int = 0
    drift_count: int = 0
    unknown_deletions: int = 0
    episodes: int = 0
    segments: int = 0
    parse_warnings: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total_events": self.total_events,
            "typed_chars": self.typed_chars,
            "deletions": self.deletions,
            "replacements": self.replacements,
            "moves": self.moves,
            "drift_count": self.drift_count,
            "unknown_deletions": self.unknown_deletions,
            "episodes": self.episodes,
            "segments": self.segments,
            "parse_warnings": self.parse_warnings,
        }
