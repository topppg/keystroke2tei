from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx
from jinja2 import Template

from keystroke2tei.models import NodeKind, TEINode
from keystroke2tei.converter import WritingAction

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"

CLASSIFIABLE_TYPES = {"context", "pre-context", "typo", "nt"}

_PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt_template() -> Template:
    path = _PROMPT_DIR / "classify_revisions.j2"
    return Template(path.read_text(encoding="utf-8"))


def _collect_classifiable_nodes(
    segments: list[TEINode], actions: list[WritingAction] | None = None,
) -> list[tuple[int, TEINode]]:
    candidates: list[tuple[TEINode, int]] = []
    nodes: list[tuple[int, TEINode]] = []
    counter = 0
    prev_was_revision = False

    def _walk(node: TEINode, depth: int = 0) -> None:
        if node.kind in (NodeKind.ADD, NodeKind.DEL) and "|" not in node.revision_type:
            candidates.append((node, depth))
        for child in node.children:
            _walk(child, depth + 1)

    for seg in segments:
        _walk(seg, depth=0)

    if actions:
        action_index = {
            action.event.event_id: index for index, action in reversed(list(enumerate(actions)))
            if action.event is not None
        }
        candidates.sort(key=lambda item: action_index.get(
            _first_event_id(item[0].evidence), len(actions)))

    for node, depth in candidates:
        if node.kind == NodeKind.DEL:
            counter += 1
            nodes.append((counter, node))
            prev_was_revision = True
        elif node.kind == NodeKind.ADD and node.revision_type in CLASSIFIABLE_TYPES and node.revision_type != "nt":
            counter += 1
            nodes.append((counter, node))
            prev_was_revision = True
        elif node.kind == NodeKind.ADD and node.revision_type == "nt" and depth == 1 and prev_was_revision:
            # Standalone <add type="nt"> after a revision — candidate for "continue"
            counter += 1
            nodes.append((counter, node))
            prev_was_revision = False
        elif node.kind == NodeKind.ADD and node.revision_type == "nt":
            prev_was_revision = False
    return nodes


def _get_node_text_content(node: TEINode) -> str:
    if node.text and not node.children:
        return node.text
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node.children:
        if child.kind == NodeKind.TEXT:
            parts.append(child.text)
    return "".join(parts)


def _first_event_id(evidence: str) -> int | None:
    match = re.match(r"\d+", evidence)
    return int(match.group()) if match else None


def _order_by_source(
    revision_nodes: list[tuple[int, TEINode]], actions: list[WritingAction],
) -> list[tuple[int, TEINode]]:
    action_index = {
        action.event.event_id: index for index, action in reversed(list(enumerate(actions)))
        if action.event is not None
    }
    ordered = sorted(
        enumerate(revision_nodes),
        key=lambda item: (
            action_index.get(_first_event_id(item[1][1].evidence), len(actions)),
            item[0],
        ),
    )
    return [(index, node) for index, (_, (_, node)) in enumerate(ordered, 1)]


def _action_summary(action: WritingAction) -> dict[str, str | int]:
    summary: dict[str, str | int] = {
        "event": action.event.event_id if action.event else 0,
        "kind": action.kind,
        "position": action.position,
    }
    if action.text:
        summary["text"] = action.text[:20]
    if action.deleted_text:
        summary["deleted"] = action.deleted_text[:20]
    return summary


def _build_revisions_text(
    revision_nodes: list[tuple[int, TEINode]],
    actions: list[WritingAction],
) -> str:
    lines: list[str] = []
    action_index = {
        action.event.event_id: index for index, action in reversed(list(enumerate(actions)))
        if action.event is not None
    }
    for idx, node in revision_nodes:
        source_index = action_index.get(_first_event_id(node.evidence))
        action = actions[source_index] if source_index is not None else None
        candidate = {
            "id": idx,
            "element": node.kind.value,
            "current_type": node.revision_type or "unknown",
            "text": _get_node_text_content(node),
            "source_evidence": node.evidence,
            "source_action": _action_summary(action) if action else None,
            "context_before_edit": action.context_at_edit if action else None,
            "ending_punctuation_to_right": action.context_complete if action else None,
            "previous_actions": [
                _action_summary(previous) for previous in
                actions[max(0, source_index - 2):source_index]
            ] if source_index is not None else [],
            "next_action": (
                _action_summary(actions[source_index + 1])
                if source_index is not None and source_index + 1 < len(actions) else None
            ),
        }
        lines.append(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines)


def _call_openrouter(prompt: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set. Add it to .env or set the environment variable.")
    response = httpx.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _parse_response(response_text: str) -> list[dict[str, str | int]]:
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


VALID_TYPES = {"nt", "typo", "pre-context", "context", "continue"}


def reclassify_with_llm(
    segments: list[TEINode],
    final_text: str,
    actions: list[WritingAction] | None = None,
) -> int:
    source_actions = actions or []
    revision_nodes = _order_by_source(
        _collect_classifiable_nodes(segments, source_actions), source_actions)
    if not revision_nodes:
        return 0

    revisions_text = _build_revisions_text(revision_nodes, source_actions)
    template = _load_prompt_template()
    prompt = template.render(revisions=revisions_text)

    try:
        response_text = _call_openrouter(prompt)
        classifications = _parse_response(response_text)
    except Exception as e:
        print(f"    [classify] LLM call failed, keeping heuristic types: {e}", file=sys.stderr)
        return 0

    node_map = {idx: node for idx, node in revision_nodes}
    changed = 0

    for item in classifications:
        idx = item.get("id")
        new_type = item.get("type", "")
        if idx not in node_map or new_type not in VALID_TYPES:
            continue

        node = node_map[idx]
        old_type = node.revision_type

        if node.kind == NodeKind.DEL and new_type in {"nt", "continue"}:
            continue
        if new_type == "continue" and node.kind == NodeKind.ADD:
            node.kind = NodeKind.MOD
            node.revision_type = "continue"
            changed += 1
        elif new_type != old_type:
            node.revision_type = new_type
            changed += 1

    return changed
