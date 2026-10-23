from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from keystroke2tei.parser import parse_csv
from keystroke2tei.idfx_parser import parse_idfx
from keystroke2tei.idfx_replay import parse_idfx_with_initial_text
from keystroke2tei.docx_text import read_docx_text
from keystroke2tei.klicke_parser import parse_klicke
from keystroke2tei.html_parser import parse_html
from keystroke2tei.converter import convert
from keystroke2tei.review import apply_overrides, build_review_report, load_overrides
from keystroke2tei.replay_parser import parse_replay_html
from keystroke2tei.validation import validate_tei
from keystroke2tei.writer import tei_reading_text, write_tei

SUPPORTED_EXTENSIONS = {".csv", ".idfx", ".html"}


def _resolve_inputs(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in inputs:
        if p.is_dir():
            for ext in SUPPORTED_EXTENSIONS:
                files.extend(sorted(p.glob(f"*{ext}")))
        elif p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(p)
        else:
            print(f"Skipping {p} (not a CSV/IDFX file or directory)", file=sys.stderr)
    return files


def _resolve_output(csv_path: Path, output: Path | None) -> Path:
    if output is None:
        return csv_path.with_suffix(".tei.xml")
    if output.is_dir() or (not output.exists() and not output.suffix):
        output.mkdir(parents=True, exist_ok=True)
        return output / csv_path.with_suffix(".tei.xml").name
    return output


def _is_klicke_csv(path: Path) -> bool:
    try:
        with open(path, encoding="utf-8-sig") as f:
            header = f.readline()
        return "DownEvent" in header and "TextChange" in header
    except Exception:
        return False


def _process_single(
    csv_path: Path, out_path: Path, verbose: bool, write_stats: bool,
    classify: bool = False,
    review_report: bool = False,
    overrides_path: Path | None = None,
    validate: bool = False,
    replay_path: Path | None = None,
    final_docx_path: Path | None = None,
    original_docx_path: Path | None = None,
) -> bool:
    try:
        replay = parse_replay_html(replay_path) if replay_path is not None else None
        if replay is not None and original_docx_path is None:
            raise ValueError("--replay-html requires --original-docx; replay HTML is verification only")
        initial_text = read_docx_text(original_docx_path) if original_docx_path is not None else ""
        final_docx_text = read_docx_text(final_docx_path) if final_docx_path is not None else None
        baseline_match = replay is None or initial_text == replay.initial_text
        if csv_path.suffix.lower() == ".idfx":
            if original_docx_path is not None:
                events, metadata, parse_warnings = parse_idfx_with_initial_text(
                    csv_path, initial_text, final_docx_text,
                )
            else:
                events, metadata, parse_warnings = parse_idfx(csv_path)
        elif csv_path.suffix.lower() == ".html":
            events, metadata, parse_warnings = parse_html(csv_path)
        elif _is_klicke_csv(csv_path):
            events, metadata, parse_warnings = parse_klicke(csv_path)
        else:
            events, metadata, parse_warnings = parse_csv(csv_path)
        result = convert(
            events, metadata=metadata, parse_warnings=len(parse_warnings),
            initial_text=initial_text,
        )

        if classify:
            from keystroke2tei.classifier import reclassify_with_llm
            changed = reclassify_with_llm(
                result.segments, result.final_document_text, result.actions,
            )
            if verbose and changed:
                print(f"    [classify] LLM reclassified {changed} revision(s)", file=sys.stderr)

        if overrides_path is not None:
            apply_overrides(result, load_overrides(overrides_path))

        xml = write_tei(result.segments, metadata=metadata, focus_sources=result.focus_sources)
        xml_reading = tei_reading_text(xml)
        xml_reading_match = xml_reading == result.final_document_text
        replay_reading_match = replay is None or xml_reading == replay.final_document_text
        final_docx_match = final_docx_text is None or xml_reading == final_docx_text
        validation_issues = validate_tei(xml) if validate else []

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml, encoding="utf-8")

        s = result.stats
        print(f"  {csv_path.name} -> {out_path.name}  "
              f"({s.typed_chars} chars, {s.deletions} dels, "
              f"{s.episodes} episodes, {s.segments} segments)")

        text_mismatch = False
        for diagnostic in result.diagnostics:
            if diagnostic.message.startswith("TEI reading text differs"):
                text_mismatch = True
                print(f"    [warning] {diagnostic.message}", file=sys.stderr)

        replay_typed_match = replay is None or result.final_text == replay.final_added_text
        replay_document_match = (
            replay is None or result.final_document_text == replay.final_document_text
        )
        source_insertions = sum(
            len(action.text) for action in result.actions
            if action.kind in {"insert", "replace", "linebreak", "paste"}
        )
        source_deletions = sum(
            len(action.deleted_text) for action in result.actions
            if action.kind in {"delete", "replace", "cut"}
        )
        replay_count_match = replay is None or (
            source_insertions == replay.inserted_chars
            and source_deletions == replay.deleted_added_chars + replay.deleted_initial_chars
        )
        replay_match = (
            baseline_match and replay_typed_match and replay_document_match and replay_count_match
            and replay_reading_match
        )
        if not baseline_match:
            print(
                "    [warning] Original DOCX text differs from the replay's starting document",
                file=sys.stderr,
            )
        if not xml_reading_match:
            print(
                "    [warning] TEI reading text differs from reconstructed IDFX document "
                f"(XML={len(xml_reading)} chars, reconstruction={len(result.final_document_text)} chars)",
                file=sys.stderr,
            )
        if final_docx_text is not None and not final_docx_match:
            mismatch = next((index for index, (left, right) in enumerate(zip(xml_reading, final_docx_text))
                             if left != right), min(len(xml_reading), len(final_docx_text)))
            print(
                "    [warning] TEI reading text differs from saved final DOCX "
                f"at character {mismatch} (XML={len(xml_reading)} chars, "
                f"DOCX={len(final_docx_text)} chars)",
                file=sys.stderr,
            )
        if replay is not None and not replay_match:
            print(
                "    [warning] Conversion differs from replay HTML "
                f"(typed={replay_typed_match}, document={replay_document_match}, "
                f"edit counts={replay_count_match})",
                file=sys.stderr,
            )

        for issue in validation_issues:
            print(f"    [{issue.severity}] {issue.code} at {issue.location}: {issue.message}",
                  file=sys.stderr)

        if verbose:
            if parse_warnings:
                for w in parse_warnings:
                    print(f"    [parse] {w}", file=sys.stderr)
            for d in result.diagnostics:
                if d.message.startswith("TEI reading text differs"):
                    continue
                print(f"    [{d.level}] event {d.event_id} (t={d.timestamp}): {d.message}",
                      file=sys.stderr)
        elif parse_warnings:
            for warning in parse_warnings:
                if "cannot be verified from IDFX" in warning:
                    print(f"    [warning] {warning}", file=sys.stderr)

        if write_stats:
            stats_path = out_path.with_name(out_path.stem.removesuffix(".tei") + ".stats.json")
            stats_path.write_text(
                json.dumps(s.to_dict(), indent=2) + "\n",
                encoding="utf-8",
            )

        if review_report:
            report = build_review_report(result)
            report["parse_warnings"] = parse_warnings
            if final_docx_text is not None:
                report["final_docx_comparison"] = {
                    "source": str(final_docx_path),
                    "tei_reading_matches": final_docx_match,
                    "tei_reading_length": len(xml_reading),
                    "final_docx_length": len(final_docx_text),
                }
            if replay is not None:
                report["replay_comparison"] = {
                    "source": str(replay_path),
                    "initial_document_matches": baseline_match,
                    "final_typed_text_matches": replay_typed_match,
                    "final_typed_text_length": len(replay.final_added_text),
                    "final_document_matches": replay_document_match,
                    "tei_reading_matches": replay_reading_match,
                    "tei_reading_length": len(xml_reading),
                    "final_document_length": len(replay.final_document_text),
                    "edit_counts_match": replay_count_match,
                    "source_inserted_chars": source_insertions,
                    "source_deleted_chars": source_deletions,
                    "inserted_chars": replay.inserted_chars,
                    "deleted_added_chars": replay.deleted_added_chars,
                    "deleted_initial_chars": replay.deleted_initial_chars,
                }
            if validate:
                report["validation_issues"] = [
                    {"severity": issue.severity, "code": issue.code,
                     "message": issue.message, "location": issue.location}
                    for issue in validation_issues
                ]
            report_path = out_path.with_name(
                out_path.stem.removesuffix(".tei") + ".review.json"
            )
            report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        return not (any(issue.severity == "error" for issue in validation_issues)
                    or (validate and (text_mismatch or not xml_reading_match
                                      or not replay_match or not final_docx_match)))
    except Exception as e:
        print(f"  ERROR {csv_path.name}: {e}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Inputlog CSV keystroke logs to TEI XML genetic editions",
    )
    parser.add_argument(
        "inputs", nargs="+", type=Path,
        help="CSV file(s) or directory containing CSVs",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output file (single input) or directory (multiple inputs)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print diagnostics (doclength drift, unknown deletions, etc.)",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Write a JSON sidecar with conversion statistics",
    )
    parser.add_argument(
        "--classify", action="store_true",
        help="Use LLM (Gemini Flash via OpenRouter) to refine revision type classification",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate output against TEI P5 and Keystroke Loxensis rules",
    )
    parser.add_argument(
        "--review-report", action="store_true",
        help="Write a JSON sidecar listing editorial review items",
    )
    parser.add_argument(
        "--original-docx", type=Path,
        help="Use the original Word document as the starting text for an IDFX session",
    )
    parser.add_argument(
        "--replay-html", type=Path,
        help="Optionally verify IDFX conversion; requires --original-docx and never supplies conversion input",
    )
    parser.add_argument(
        "--final-docx", type=Path,
        help="Check the TEI reading against the saved final Word document and resolve ambiguous one-character insertions",
    )
    parser.add_argument(
        "--overrides", type=Path,
        help="Apply editorial overrides from a JSON file, or a directory of <stem>.overrides.json files",
    )
    args = parser.parse_args()

    if args.classify:
        from dotenv import load_dotenv
        load_dotenv()

    csv_files = _resolve_inputs(args.inputs)
    if not csv_files:
        print("No CSV files found.", file=sys.stderr)
        sys.exit(1)

    if len(csv_files) > 1 and args.output is not None and (
        args.output.is_file() or (not args.output.exists() and bool(args.output.suffix))
    ):
        parser.error("multiple inputs require an output directory")
    if args.replay_html is not None:
        if args.original_docx is None:
            parser.error("--replay-html requires --original-docx; replay HTML is verification only")
        if len(csv_files) != 1 or csv_files[0].suffix.lower() != ".idfx":
            parser.error("--replay-html requires one IDFX input")
        if not args.replay_html.is_file():
            parser.error("--replay-html path does not exist")
    if args.original_docx is not None:
        if len(csv_files) != 1 or csv_files[0].suffix.lower() != ".idfx":
            parser.error("--original-docx requires one IDFX input")
        if not args.original_docx.is_file():
            parser.error("--original-docx path does not exist")
    if args.final_docx is not None:
        if args.original_docx is None:
            parser.error("--final-docx requires --original-docx")
        if not args.final_docx.is_file():
            parser.error("--final-docx path does not exist")

    out_paths = [_resolve_output(path, args.output) for path in csv_files]
    if len(set(out_paths)) != len(out_paths):
        parser.error("multiple inputs would write to the same output file")
    if args.overrides is not None:
        if not args.overrides.exists():
            parser.error("--overrides path does not exist")
        if args.overrides.is_file() and len(csv_files) > 1:
            parser.error("a single overrides file requires a single input")

    ok = 0
    fail = 0
    for csv_path, out_path in zip(csv_files, out_paths):
        overrides_path = None
        if args.overrides is not None:
            candidate = (args.overrides / f"{csv_path.stem}.overrides.json"
                         if args.overrides.is_dir() else args.overrides)
            if candidate.is_file():
                overrides_path = candidate
        if _process_single(
            csv_path, out_path, args.verbose, args.stats, args.classify,
            args.review_report, overrides_path, args.validate,
            args.replay_html,
            args.final_docx,
            args.original_docx,
        ):
            ok += 1
        else:
            fail += 1

    if len(csv_files) > 1:
        print(f"\nProcessed {ok + fail} files: {ok} ok, {fail} errors")

    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
