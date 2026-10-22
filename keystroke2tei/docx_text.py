"""Read the plain document text used by Inputlog's Word replay."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_docx_text(path: Path) -> str:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.iter(f"{_W}p"):
        chars = []
        for element in paragraph.iter():
            if element.tag == f"{_W}t":
                chars.append(element.text or "")
            elif element.tag == f"{_W}tab":
                chars.append("\t")
            elif element.tag == f"{_W}br":
                chars.append("\n")
        paragraphs.append("".join(chars))
    return "\n".join(paragraphs) + "\n"
