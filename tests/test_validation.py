from __future__ import annotations

from lxml import etree

from keystroke2tei.models import NodeKind, TEINode
from keystroke2tei.validation import validate_tei
from keystroke2tei.writer import write_tei


def _sample() -> str:
    return write_tei([
        TEINode(NodeKind.SEG, children=[
            TEINode(NodeKind.ADD, seq="120001", revision_type="nt", evidence="1-3", text="Hi."),
        ]),
    ])


def _codes(xml: str) -> set[str]:
    return {issue.code for issue in validate_tei(xml)}


def test_generated_xml_passes_tei_and_loxensis_checks() -> None:
    assert validate_tei(_sample()) == []


def test_schema_rejects_invalid_tei_even_when_xml_is_well_formed() -> None:
    root = etree.fromstring(_sample().encode())
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    seg = root.xpath("//tei:seg", namespaces=ns)[0]
    seg.tag = "{http://www.tei-c.org/ns/1.0}unknownTag"
    assert "tei.schema" in _codes(etree.tostring(root, encoding="unicode"))


def test_likelihood_of_missing_notation_is_reported_separately() -> None:
    root = etree.fromstring(_sample().encode())
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    add = root.xpath("//tei:add", namespaces=ns)[0]
    del add.attrib["seq"]
    del add.attrib["evidence"]
    codes = _codes(etree.tostring(root, encoding="unicode"))
    assert "loxensis.missing-seq" in codes
    assert "loxensis.missing-evidence" in codes


def test_bad_timestamp_and_type_are_reported() -> None:
    root = etree.fromstring(_sample().encode())
    add = root.xpath("//*[local-name()='add']")[0]
    add.set("seq", "250099")
    add.set("type", "unknown")
    codes = _codes(etree.tostring(root, encoding="unicode"))
    assert "loxensis.seq-format" in codes
    assert "loxensis.type-value" in codes


def test_addition_continuation_keeps_its_original_type() -> None:
    root = etree.fromstring(_sample().encode())
    add = root.xpath("//*[local-name()='add']")[0]
    add.set("type", "nt|continue")
    assert "loxensis.type-value" not in _codes(etree.tostring(root, encoding="unicode"))
    add.set("type", "continue|continue")
    assert "loxensis.type-value" in _codes(etree.tostring(root, encoding="unicode"))


def test_duplicate_evidence_is_a_warning() -> None:
    xml = write_tei([
        TEINode(NodeKind.SEG, children=[
            TEINode(NodeKind.ADD, seq="120001", revision_type="nt", evidence="1", text="Hi"),
            TEINode(NodeKind.ADD, seq="120002", revision_type="nt", evidence="1", text="."),
        ]),
    ])
    issues = validate_tei(xml)
    assert any(i.code == "loxensis.duplicate-evidence" and i.severity == "warning" for i in issues)


def test_source_media_requires_desc() -> None:
    root = etree.fromstring(_sample().encode())
    ns = "http://www.tei-c.org/ns/1.0"
    body = root.find(f"{{{ns}}}text/{{{ns}}}body")
    assert body is not None
    sources = etree.SubElement(body, f"{{{ns}}}p", source="sources")
    add = etree.SubElement(sources, f"{{{ns}}}add", seq="120002", type="focus", evidence="4")
    etree.SubElement(add, f"{{{ns}}}media", url="https://example.org", mimeType="Internet")
    assert "loxensis.media-desc" in _codes(etree.tostring(root, encoding="unicode"))


def test_malformed_xml_gets_parse_issue() -> None:
    issues = validate_tei("<TEI>")
    assert [issue.code for issue in issues] == ["tei.xml"]
