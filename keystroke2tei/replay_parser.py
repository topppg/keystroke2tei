"""Read the embedded state data in an Inputlog replay HTML file."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


@dataclass(frozen=True)
class ReplayText:
    initial_text: str
    final_added_text: str
    final_document_text: str
    inserted_chars: int
    deleted_added_chars: int
    deleted_initial_chars: int


class _DataScript(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_data = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "data":
            self.in_data = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_data = False

    def handle_data(self, data: str) -> None:
        if self.in_data:
            self.parts.append(data)


def parse_replay_html(path: Path) -> ReplayText:
    parser = _DataScript()
    parser.feed(path.read_text(encoding="utf-8-sig"))
    if not parser.parts:
        raise ValueError("Replay HTML has no embedded data script")
    data = json.loads("".join(parser.parts))
    text = data["T"]
    changes = {int(i): (int(start), int(end), int(kind))
               for i, start, end, kind in data["X"]}
    final_state = len(data["S"]["t"]) - 1
    if final_state < 0:
        raise ValueError("Replay HTML contains no states")

    initial: list[str] = []
    final_added: list[str] = []
    final_document: list[str] = []
    for index, char in enumerate(text):
        start, end, kind = changes.get(index, (0, -1, 0))
        if kind == 2:
            continue  # Pause marker, not document text.
        if start <= 0 and (end < 0 or end > 0):
            initial.append(char)
        if start <= final_state and (end < 0 or end > final_state):
            final_document.append(char)
            if kind == 1:
                final_added.append(char)

    return ReplayText(
        initial_text="".join(initial),
        final_added_text="".join(final_added),
        final_document_text="".join(final_document),
        inserted_chars=sum(1 for start, _, kind in changes.values() if kind == 1),
        deleted_added_chars=sum(1 for _, end, kind in changes.values()
                                if kind == 1 and 0 <= end <= final_state),
        deleted_initial_chars=sum(1 for _, end, kind in changes.values()
                                  if kind == 0 and 0 <= end <= final_state),
    )
