"""Explicit editorial review of a converted keystroke session.

The report records source-derived uncertainties and audits the *current* TEI tree.
Attribute overrides are deliberately small: structural sentence and crossing-edit
decisions require an editor to inspect the XML, rather than a silent tree rewrite.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from keystroke2tei.converter import ConversionResult
from keystroke2tei.models import NodeKind, TEINode


_OPERATIONS = {NodeKind.ADD, NodeKind.DEL, NodeKind.MOD}
_EDITABLE = {"revision_type", "seq", "evidence"}
_ADD_TYPES = {"nt", "typo", "pre-context", "context", "translocation", "source"}
_DEL_TYPES = {"typo", "pre-context", "context", "translocation"}


def _validate_change(kind: str, name: str, value: str) -> None:
    if name == "seq":
        if not re.fullmatch(r"(?:[0-9]{6}|[0-9]{14})", value):
            raise ValueError("@seq must be hhmmss or yyyymmddhhmmss")
        clock = value[-6:]
        if int(clock[:2]) > 23 or int(clock[2:4]) > 59 or int(clock[4:]) > 59:
            raise ValueError("@seq contains an invalid clock time")
        if len(value) == 14:
            try:
                datetime.strptime(value[:8], "%Y%m%d")
            except ValueError as error:
                raise ValueError("@seq contains an invalid calendar date") from error
    elif name == "evidence":
        if not re.fullmatch(r"[0-9]+(?:-[0-9]+)?", value):
            raise ValueError("@evidence must be an event ID or numeric ID range")
        first, *last = value.split("-")
        if last and int(last[0]) < int(first):
            raise ValueError("@evidence range must be ascending")
    elif name == "revision_type":
        base, *continuations = value.split("|")
        valid_base = (_ADD_TYPES if kind == "add" else _DEL_TYPES if kind == "del" else {"continue"})
        if base not in valid_base or len(continuations) > 1 or (
            continuations and continuations[0] != "continue"
        ):
            raise ValueError(f"Unsupported @type={value!r} for <{kind}>")


def _walk(result: ConversionResult):
    """Yield nodes with a path from the segments list, in document order."""
    def descendants(node: TEINode, path: list[int]):
        yield node, path
        for index, child in enumerate(node.children):
            yield from descendants(child, [*path, index])

    for index, segment in enumerate(result.segments):
        yield from descendants(segment, [index])


def _anchored_nodes(result: ConversionResult):
    counts: dict[tuple[str, str], int] = {}
    for node, path in _walk(result):
        if node.kind not in _OPERATIONS:
            continue
        key = (node.kind.value, node.evidence)
        occurrence = counts.get(key, 0)
        counts[key] = occurrence + 1
        target = {
            "kind": node.kind.value,
            "evidence": node.evidence,
            "occurrence": occurrence,
            "path": path,
        }
        yield node, target


def _reading_text(node: TEINode) -> str:
    if node.kind == NodeKind.DEL:
        return ""
    if node.kind == NodeKind.LB:
        return "\n"
    return node.text + "".join(_reading_text(child) for child in node.children)


def build_review_report(result: ConversionResult) -> dict[str, Any]:
    """Return a JSON-serializable report of decisions requiring editorial attention.

    `source_diagnostics` are retained verbatim from conversion and can describe
    conditions that an override has since resolved. `issues` are computed from
    the current tree and are suitable for checking the result after overrides.
    """
    issues: list[dict[str, Any]] = []
    seen_evidence: dict[str, dict[str, Any]] = {}

    for node, target in _anchored_nodes(result):
        if node.revision_type in {"typo", "context", "pre-context", "translocation", "source"}:
            issues.append({
                "category": "inferred_type", "severity": "review", "target": target,
                "message": "Confirm that the inferred revision type matches the writer's action.",
                "current": node.revision_type,
            })
        for attr in ("seq", "revision_type", "evidence"):
            if not getattr(node, attr):
                issues.append({
                    "category": f"missing_{attr}", "severity": "warning", "target": target,
                    "message": f"Writing operation is missing @{ 'type' if attr == 'revision_type' else attr }.",
                })
        if node.evidence:
            if node.evidence in seen_evidence:
                issues.append({
                    "category": "repeated_evidence", "severity": "warning", "target": target,
                    "message": f"@evidence={node.evidence} is used by multiple operations.",
                    "first_target": seen_evidence[node.evidence],
                })
            else:
                seen_evidence[node.evidence] = target

    for index, segment in enumerate(result.segments[:-1]):
        issues.append({
            "category": "sentence_boundary", "severity": "review",
            "target": {"kind": "seg", "path": [index]},
            "message": "Confirm that this segment ends at a sentence boundary.",
            "left_excerpt": _reading_text(segment)[-60:],
            "right_excerpt": _reading_text(result.segments[index + 1])[:60],
        })

    projected = "".join(_reading_text(segment) for segment in result.segments)
    if projected != result.final_text:
        mismatch = next(
            (i for i, (actual, expected) in enumerate(zip(projected, result.final_text))
             if actual != expected),
            min(len(projected), len(result.final_text)),
        )
        issues.append({
            "category": "text_mismatch", "severity": "warning",
            "message": "TEI reading text differs from replayed text.",
            "offset": mismatch,
            "expected_excerpt": result.final_text[max(0, mismatch - 30):mismatch + 30],
            "actual_excerpt": projected[max(0, mismatch - 30):mismatch + 30],
        })

    source_diagnostics = [
        {"event_id": d.event_id, "timestamp": d.timestamp,
         "level": d.level, "message": d.message}
        for d in result.diagnostics
    ]
    return {
        "format_version": 1,
        "source": result.metadata.filepath if result.metadata else "",
        "final_text_length": len(result.final_text),
        "issues": issues,
        "source_diagnostics": source_diagnostics,
    }


def load_overrides(path: str | Path) -> dict[str, Any]:
    """Load editor-authored overrides from JSON; validation is in apply_overrides."""
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Overrides must be a JSON object")
    return data


def apply_overrides(result: ConversionResult, overrides: dict[str, Any]) -> None:
    """Apply validated node attribute edits in place, with no partial updates.

    Targets normally use kind + source evidence + occurrence, which survive
    unrelated tree movement. Nodes without evidence use their segment/child path.
    A stale or ambiguous target raises ValueError rather than editing another node.
    """
    if not isinstance(overrides, dict) or set(overrides) != {"format_version", "overrides"}:
        raise ValueError("Overrides need format_version and overrides keys")
    if overrides["format_version"] != 1:
        raise ValueError("Unsupported override format_version")
    entries = overrides["overrides"]
    if not isinstance(entries, list):
        raise ValueError("overrides must be a list")

    indexed = list(_anchored_nodes(result))
    planned: list[tuple[TEINode, dict[str, str]]] = []
    edited: set[int] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"target", "set"}:
            raise ValueError("Each override needs target and set keys")
        target, changes = entry["target"], entry["set"]
        if not isinstance(target, dict) or not isinstance(changes, dict) or not changes:
            raise ValueError("Override target and set must be nonempty objects")
        if not set(changes) <= _EDITABLE:
            raise ValueError(f"Unsupported override attributes: {sorted(set(changes) - _EDITABLE)}")
        if any(not isinstance(value, str) or not value or value.strip() != value
               for value in changes.values()):
            raise ValueError("Override values must be nonempty trimmed strings")

        kind = target.get("kind")
        evidence = target.get("evidence")
        occurrence = target.get("occurrence")
        path = target.get("path")
        if kind not in {"add", "del", "mod"} or not isinstance(evidence, str):
            raise ValueError("Target needs an add/del/mod kind and source evidence")
        for name, value in changes.items():
            _validate_change(kind, name, value)
        if not isinstance(occurrence, int) or isinstance(occurrence, bool) or occurrence < 0:
            raise ValueError("Target occurrence must be a nonnegative integer")
        if not isinstance(path, list) or not path or any(
            not isinstance(i, int) or isinstance(i, bool) or i < 0 for i in path
        ):
            raise ValueError("Target path must be a list of nonnegative integers")

        matching = [(node, anchor) for node, anchor in indexed
                    if anchor["kind"] == kind and anchor["evidence"] == evidence
                    and anchor["occurrence"] == occurrence]
        if len(matching) != 1:
            raise ValueError(f"Stale or ambiguous override target: {target}")
        node, anchor = matching[0]
        if not evidence and anchor["path"] != path:
            raise ValueError(f"Stale path for operation without evidence: {target}")
        if id(node) in edited:
            raise ValueError(f"Operation is overridden more than once: {target}")
        edited.add(id(node))
        planned.append((node, changes))

    for node, changes in planned:
        for name, value in changes.items():
            setattr(node, name, value)
