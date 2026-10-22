from __future__ import annotations

from urllib.parse import quote

from lxml import etree

from keystroke2tei.converter import FocusEvent, _ms_to_seq
from keystroke2tei.models import NodeKind, SessionMetadata, TEINode


TEI_NS = "http://www.tei-c.org/ns/1.0"
NSMAP = {None: TEI_NS}


def _node_to_xml(node: TEINode, parent: etree._Element) -> None:
    if node.kind == NodeKind.TEXT:
        if len(parent) == 0:
            parent.text = (parent.text or "") + node.text
        else:
            last = parent[-1]
            last.tail = (last.tail or "") + node.text
        return

    if node.kind == NodeKind.LB:
        etree.SubElement(parent, "lb")
        return

    if node.kind == NodeKind.SEG:
        el = etree.SubElement(parent, "seg")
        for child in node.children:
            _node_to_xml(child, el)
        return

    tag = node.kind.value
    attrs: dict[str, str] = {}
    if node.seq:
        attrs["seq"] = node.seq
    if node.revision_type:
        attrs["type"] = node.revision_type
    if node.evidence:
        attrs["evidence"] = node.evidence

    el = etree.SubElement(parent, tag, **attrs)

    if node.text and not node.children:
        el.text = node.text
    else:
        if node.text:
            el.text = node.text
        for child in node.children:
            _node_to_xml(child, el)


def _build_header(metadata: SessionMetadata | None = None) -> etree._Element:
    m = metadata or SessionMetadata()
    header = etree.Element("teiHeader")
    file_desc = etree.SubElement(header, "fileDesc")

    title_stmt = etree.SubElement(file_desc, "titleStmt")
    t = etree.SubElement(title_stmt, "title")
    t.text = m.filepath.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] if m.filepath else "Untitled"
    a = etree.SubElement(title_stmt, "author")
    a.text = m.participant or "Unknown"

    pub_stmt = etree.SubElement(file_desc, "publicationStmt")
    p_sess = etree.SubElement(pub_stmt, "p", corresp="session")
    p_sess.text = m.session or "1"
    p_lang = etree.SubElement(pub_stmt, "p", corresp="language")
    p_lang.text = m.language or "unknown"
    p_name = etree.SubElement(pub_stmt, "p", corresp="name")
    p_name.text = m.participant or "Unknown"

    source = etree.SubElement(file_desc, "sourceDesc")
    p_src = etree.SubElement(source, "p")
    date_el = etree.SubElement(p_src, "l")
    date_el.text = f"Date: {m.date}" if m.date else "Date: unknown"

    return header


def write_tei(
    segments: list[TEINode],
    metadata: SessionMetadata | None = None,
    focus_sources: list[FocusEvent] | None = None,
) -> str:
    root = etree.Element("TEI", nsmap=NSMAP)

    header = _build_header(metadata=metadata)
    root.append(header)

    text = etree.SubElement(root, "text")
    body = etree.SubElement(text, "body")
    p = etree.SubElement(body, "p", source="keystrokes")

    for seg_node in segments:
        _node_to_xml(seg_node, p)

    if focus_sources:
        p_sources = etree.SubElement(body, "p", source="sources")
        for fe in focus_sources:
            add_el = etree.SubElement(
                p_sources, "add", seq=_ms_to_seq(fe.timestamp),
                type="focus", evidence=str(fe.event_id),
            )
            source_type = (
                "Internet" if fe.app_name.startswith(("http://", "https://"))
                else "Application"
            )
            media_el = etree.SubElement(
                add_el, "media", url=quote(fe.app_name, safe="/:?&=#%"), mimeType=source_type,
            )
            desc_el = etree.SubElement(media_el, "desc")
            desc_el.text = fe.app_name

    return etree.tostring(
        root,
        pretty_print=False,
        encoding="unicode",
    )


def tei_reading_text(xml: str) -> str:
    """Extract the final document reading from the serialized keystroke body."""
    root = etree.fromstring(xml.encode("utf-8"))
    paragraph = root.find('.//{*}p[@source="keystrokes"]')
    if paragraph is None:
        return ""

    def read(element: etree._Element) -> str:
        if etree.QName(element).localname == "del":
            return ""
        parts = [element.text or ""]
        for child in element:
            parts.append("\n" if etree.QName(child).localname == "lb" else read(child))
            parts.append(child.tail or "")
        return "".join(parts)

    return read(paragraph)
