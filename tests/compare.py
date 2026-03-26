from __future__ import annotations

from pathlib import Path

from lxml import etree

from keystroke2tei import parse_csv, convert, write_tei


def compare_structure(generated: str, reference: str) -> None:
    gen_tree = etree.fromstring(generated.encode())
    ref_tree = etree.fromstring(reference.encode())

    ns = {"tei": "http://www.tei-c.org/ns/1.0"}

    def count_elements(tree: etree._Element) -> dict[str, int]:
        counts: dict[str, int] = {}
        for el in tree.iter():
            tag = etree.QName(el.tag).localname if isinstance(el.tag, str) else str(el.tag)
            counts[tag] = counts.get(tag, 0) + 1
        return counts

    def get_text_content(tree: etree._Element) -> str:
        body = tree.find(".//tei:body", ns)
        if body is None:
            body = tree.find(".//body")
        if body is None:
            return ""
        return "".join(body.itertext()).strip()

    gen_counts = count_elements(gen_tree)
    ref_counts = count_elements(ref_tree)

    print("=" * 60)
    print("STRUCTURAL COMPARISON")
    print("=" * 60)

    all_tags = sorted(set(gen_counts) | set(ref_counts))
    print(f"\n{'Element':<20} {'Generated':>10} {'Reference':>10}")
    print("-" * 42)
    for tag in all_tags:
        g = gen_counts.get(tag, 0)
        r = ref_counts.get(tag, 0)
        marker = " =" if g == r else " ~"
        print(f"{tag:<20} {g:>10} {r:>10}{marker}")

    gen_text = get_text_content(gen_tree)
    ref_text = get_text_content(ref_tree)
    print(f"\n{'='*60}")
    print("TEXT CONTENT")
    print(f"{'='*60}")
    print(f"Generated: {gen_text[:100]!r}...")
    print(f"Reference: {ref_text[:100]!r}...")

    print(f"\n{'='*60}")
    print("VALIDATION")
    print(f"{'='*60}")

    has_tei = gen_tree.tag == "{http://www.tei-c.org/ns/1.0}TEI" or gen_tree.tag == "TEI"
    body = gen_tree.find(".//tei:body", ns) or gen_tree.find(".//body")
    has_header = gen_tree.find(".//tei:teiHeader", ns) is not None or gen_tree.find(".//teiHeader") is not None

    print(f"  <TEI> root:     {'yes' if has_tei else 'NO'}")
    print(f"  <teiHeader>:    {'yes' if has_header else 'NO'}")
    print(f"  <body>:         {'yes' if body is not None else 'NO'}")
    print(f"  Well-formed:    yes")


def main() -> None:
    base = Path(__file__).parent.parent

    events, metadata, warnings = parse_csv(base / "data/input/doc.csv")
    result = convert(events, metadata=metadata, parse_warnings=len(warnings))
    generated_xml = write_tei(result.segments, metadata=metadata)

    out = base / "data/output" / "doc_generated.tei.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(generated_xml, encoding="utf-8")
    print(f"Generated: {out}\n")

    reference_xml = (base / "data/input/doc.xml").read_text(encoding="utf-8")
    compare_structure(generated_xml, reference_xml)


if __name__ == "__main__":
    main()
