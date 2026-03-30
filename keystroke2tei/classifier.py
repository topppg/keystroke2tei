from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from jinja2 import Template

from keystroke2tei.models import NodeKind, TEINode

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"

CLASSIFIABLE_TYPES = {"context", "pre-context", "typo", "nt"}

_PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt_template() -> Template:
    path = _PROMPT_DIR / "classify_revisions.j2"
    return Template(path.read_text(encoding="utf-8"))


def _collect_classifiable_nodes(segments: list[TEINode]) -> list[tuple[int, TEINode]]:
    nodes: list[tuple[int, TEINode]] = []
    counter = 0
    prev_was_revision = False

    def _walk(node: TEINode, depth: int = 0) -> None:
        nonlocal counter, prev_was_revision
        if node.kind in (NodeKind.DEL, NodeKind.MOD):
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
        for child in node.children:
            _walk(child, depth + 1)

    for seg in segments:
        _walk(seg, depth=0)
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


def _get_context(final_text: str, pos: int, width: int = 30) -> str:
    start = max(0, pos - width)
    end = min(len(final_text), pos + width)
    before = final_text[start:pos]
    after = final_text[pos:end]
    return f"...{before}|{after}..."


def _build_revisions_text(
    revision_nodes: list[tuple[int, TEINode]],
    final_text: str,
) -> str:
    lines: list[str] = []
    prev_was_del_or_revision = False
    for idx, node in revision_nodes:
        text_content = _get_node_text_content(node)
        kind = node.kind.value
        rev_type = node.revision_type or "unknown"
        context = _get_context(final_text, node.start_pos) if node.start_pos >= 0 else "N/A"

        flags: list[str] = []
        if prev_was_del_or_revision and node.kind == NodeKind.ADD and rev_type == "nt":
            flags.append("follows_revision=true (candidate for 'continue')")

        flag_str = f" [{', '.join(flags)}]" if flags else ""

        if node.kind == NodeKind.DEL:
            lines.append(
                f"{idx}. [{kind}] current_type=\"{rev_type}\" deleted=\"{text_content}\" "
                f"context: {context}{flag_str}"
            )
        else:
            lines.append(
                f"{idx}. [{kind}] current_type=\"{rev_type}\" added=\"{text_content}\" "
                f"context: {context}{flag_str}"
            )

        prev_was_del_or_revision = node.kind == NodeKind.DEL or rev_type not in ("nt",)
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


VALID_TYPES = {"typo", "pre-context", "context", "continue"}


def reclassify_with_llm(
    segments: list[TEINode],
    final_text: str,
) -> int:
    revision_nodes = _collect_classifiable_nodes(segments)
    if not revision_nodes:
        return 0

    revisions_text = _build_revisions_text(revision_nodes, final_text)
    template = _load_prompt_template()
    prompt = template.render(final_text=final_text, revisions=revisions_text)

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

        if new_type == "continue" and node.kind != NodeKind.MOD:
            node.kind = NodeKind.MOD
            node.revision_type = "continue"
            changed += 1
        elif new_type != old_type and new_type != "continue":
            node.revision_type = new_type
            changed += 1

    return changed
