from __future__ import annotations

import json

import pytest

from keystroke2tei.converter import ConversionResult
from keystroke2tei.models import Diagnostic, NodeKind, TEINode
from keystroke2tei.review import apply_overrides, build_review_report, load_overrides
from keystroke2tei.writer import write_tei


def _result() -> ConversionResult:
    first = TEINode(NodeKind.ADD, seq="000001", revision_type="nt", evidence="1")
    first.children = [
        TEINode(NodeKind.TEXT, text="Hi"),
        TEINode(NodeKind.ADD, text="!", revision_type="context", evidence="2"),
    ]
    second = TEINode(NodeKind.ADD, text="Bye.", seq="000003", revision_type="nt", evidence="2")
    return ConversionResult(
        segments=[TEINode(NodeKind.SEG, children=[first]), TEINode(NodeKind.SEG, children=[second])],
        final_text="Hi!Bye.", actions=[], episodes=[],
        diagnostics=[Diagnostic(2, 0, "missing @seq; source event has no usable timestamp", "warning")],
    )


def test_report_identifies_review_decisions_and_current_notation_issues():
    report = build_review_report(_result())
    assert report["format_version"] == 1
    categories = [issue["category"] for issue in report["issues"]]
    assert "inferred_type" in categories
    assert "missing_seq" in categories
    assert "repeated_evidence" in categories
    assert "sentence_boundary" in categories
    assert "text_mismatch" not in categories
    assert report["source_diagnostics"][0]["message"].startswith("missing @seq")


def test_override_uses_source_anchor_and_report_reflects_current_tree(tmp_path):
    result = _result()
    issue = next(i for i in build_review_report(result)["issues"] if i["category"] == "missing_seq")
    target = issue["target"]
    assert target == {"kind": "add", "evidence": "2", "occurrence": 0, "path": [0, 0, 1]}
    override_file = tmp_path / "overrides.json"
    override_file.write_text(json.dumps({
        "format_version": 1,
        "overrides": [{"target": target, "set": {"seq": "000002", "revision_type": "typo"}}],
    }), encoding="utf-8")
    apply_overrides(result, load_overrides(override_file))
    assert 'seq="000002" type="typo" evidence="2"' in write_tei(result.segments)
    updated = build_review_report(result)
    assert not any(i["category"] == "missing_seq" for i in updated["issues"])
    assert any(i["category"] == "inferred_type" and i["current"] == "typo"
               for i in updated["issues"])
    assert updated["source_diagnostics"][0]["message"].startswith("missing @seq")


def test_override_can_resolve_duplicate_evidence():
    result = _result()
    duplicate = next(i for i in build_review_report(result)["issues"]
                     if i["category"] == "repeated_evidence")
    apply_overrides(result, {
        "format_version": 1,
        "overrides": [{"target": duplicate["target"], "set": {"evidence": "3"}}],
    })
    assert not any(i["category"] == "repeated_evidence" for i in build_review_report(result)["issues"])


def test_invalid_override_is_atomic():
    result = _result()
    target = next(i["target"] for i in build_review_report(result)["issues"]
                  if i["category"] == "missing_seq")
    stale = {**target, "evidence": "999"}
    with pytest.raises(ValueError, match="Stale"):
        apply_overrides(result, {
            "format_version": 1,
            "overrides": [
                {"target": target, "set": {"seq": "000002"}},
                {"target": stale, "set": {"seq": "000004"}},
            ],
        })
    assert any(i["category"] == "missing_seq" for i in build_review_report(result)["issues"])


def test_report_detects_reading_text_mismatch():
    result = _result()
    result.final_text = "Hi?Bye."
    mismatch = next(i for i in build_review_report(result)["issues"]
                    if i["category"] == "text_mismatch")
    assert mismatch["offset"] == 2
    assert mismatch["expected_excerpt"] == "Hi?Bye."
    assert mismatch["actual_excerpt"] == "Hi!Bye."


@pytest.mark.parametrize("field,value", [
    ("seq", "12345"),
    ("seq", "246001"),
    ("seq", "20250229010203"),
    ("revision_type", "continue"),
    ("revision_type", "nt|continue|continue"),
    ("revision_type", "focus"),
    ("revision_type", "unknown"),
    ("evidence", "event 5"),
    ("evidence", "5-3"),
])
def test_malformed_override_is_rejected_atomically(field, value):
    result = _result()
    target = next(i["target"] for i in build_review_report(result)["issues"]
                  if i["category"] == "missing_seq")
    before = write_tei(result.segments)
    with pytest.raises(ValueError):
        apply_overrides(result, {
            "format_version": 1,
            "overrides": [{"target": target, "set": {"seq": "000002", field: value}}],
        })
    assert write_tei(result.segments) == before


def test_accepted_date_sequence_and_addition_continuation():
    result = _result()
    target = next(i["target"] for i in build_review_report(result)["issues"]
                  if i["category"] == "missing_seq")
    apply_overrides(result, {
        "format_version": 1,
        "overrides": [{"target": target, "set": {
            "seq": "20240229010203", "revision_type": "pre-context|continue",
        }}],
    })
    assert 'seq="20240229010203" type="pre-context|continue"' in write_tei(result.segments)
