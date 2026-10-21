from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from lxml import etree


TEI_NS = "http://www.tei-c.org/ns/1.0"
NS = {"tei": TEI_NS}
SCHEMA_PATH = Path(__file__).parent / "schemas" / "tei_all.rng"

# TEI P5 4.12.0, generated 2026-07-28, from
# https://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng
# The schema's own header states TEI content is dual licensed CC BY / BSD-2.


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # "error" or "warning"
    code: str
    message: str
    location: str


@lru_cache(maxsize=4)
def _schema(path: Path) -> etree.RelaxNG:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    return etree.RelaxNG(etree.parse(str(path), parser))


def _location(element: etree._Element) -> str:
    return f"{element.getroottree().getpath(element)} (line {element.sourceline or '?'})"


def _valid_seq(value: str) -> bool:
    if not re.fullmatch(r"(?:\d{6}|\d{14})", value):
        return False
    try:
        datetime.strptime(value, "%H%M%S" if len(value) == 6 else "%Y%m%d%H%M%S")
    except ValueError:
        return False
    return True


def _loxensis_issues(root: etree._Element) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def report(severity: str, code: str, message: str, element: etree._Element) -> None:
        issues.append(ValidationIssue(severity, f"loxensis.{code}", message, _location(element)))

    body = root.find("tei:text/tei:body", NS)
    if body is None:
        report("error", "body", "Expected a TEI text/body.", root)
        return issues

    writing = body.xpath("./tei:p[@source='keystrokes']", namespaces=NS)
    if len(writing) != 1:
        report("error", "writing-paragraph", "Expected exactly one <p source='keystrokes'> in the body.", body)
    for paragraph in writing:
        for child in paragraph:
            if isinstance(child.tag, str) and child.tag != f"{{{TEI_NS}}}seg":
                report("error", "sentence-seg", "Writing paragraphs must contain sentence <seg> elements.", child)

    sources = body.xpath("./tei:p[@source='sources']", namespaces=NS)
    for paragraph in sources:
        for child in paragraph:
            if isinstance(child.tag, str) and child.tag not in {f"{{{TEI_NS}}}add", f"{{{TEI_NS}}}lb"}:
                report("error", "source-operation", "Source paragraphs should contain focus <add> elements or <lb/>.", child)
        for add in paragraph.xpath(".//tei:add", namespaces=NS):
            if add.get("type") != "focus":
                report("error", "focus-type", "A source event must use <add type='focus'>.", add)
            if not add.xpath("./tei:media", namespaces=NS):
                report("error", "focus-media", "A focus addition must contain <media>.", add)
            for media in add.xpath("./tei:media", namespaces=NS):
                if not media.xpath("./tei:desc", namespaces=NS):
                    report("error", "media-desc", "A focus <media> must contain <desc>.", media)

    operation_tags = {f"{{{TEI_NS}}}{tag}" for tag in ("add", "del", "mod")}
    evidence_seen: dict[str, etree._Element] = {}
    for element in body.iter():
        if element.tag not in operation_tags:
            continue
        tag = etree.QName(element).localname
        for attribute in ("seq", "type", "evidence"):
            if not (element.get(attribute) or "").strip():
                report("error", f"missing-{attribute}", f"<{tag}> requires @{attribute}.", element)
        seq = element.get("seq")
        if seq and not _valid_seq(seq):
            report("error", "seq-format", "@seq must be a valid hhmmss or yyyymmddhhmmss timestamp.", element)
        kind = element.get("type")
        if kind:
            base, separator, suffix = kind.partition("|")
            allowed = ({"nt", "typo", "pre-context", "context", "translocation", "source"}
                       if tag == "add" else {"typo", "pre-context", "context", "translocation"}
                       if tag == "del" else {"continue"})
            if tag == "add" and element.getparent() in sources:
                allowed.add("focus")
            if base not in allowed or (separator and suffix != "continue"):
                report("error", "type-value", f"Unsupported Loxensis type {kind!r} for <{tag}>.", element)
        evidence = element.get("evidence")
        if evidence:
            if evidence in evidence_seen:
                report("warning", "duplicate-evidence", f"@evidence {evidence!r} is reused by another operation.", element)
            else:
                evidence_seen[evidence] = element
    return issues


def validate_tei(xml: str, *, schema_path: Path | None = None) -> list[ValidationIssue]:
    """Validate TEI P5 structure and the machine-checkable Loxensis conventions."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    try:
        root = etree.fromstring(xml.encode("utf-8"), parser)
    except etree.XMLSyntaxError as exc:
        return [ValidationIssue("error", "tei.xml", str(exc), f"line {exc.lineno}")]

    issues: list[ValidationIssue] = []
    try:
        schema = _schema(Path(schema_path or SCHEMA_PATH).resolve())
        if not schema.validate(root):
            issues.extend(ValidationIssue("error", "tei.schema", entry.message, f"line {entry.line}")
                          for entry in schema.error_log)
    except (OSError, etree.XMLSyntaxError, etree.RelaxNGParseError) as exc:
        issues.append(ValidationIssue("error", "tei.schema-unavailable", str(exc), str(schema_path or SCHEMA_PATH)))
    issues.extend(_loxensis_issues(root))
    return issues
