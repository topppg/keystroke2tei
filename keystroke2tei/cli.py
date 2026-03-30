from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from keystroke2tei.parser import parse_csv
from keystroke2tei.idfx_parser import parse_idfx
from keystroke2tei.klicke_parser import parse_klicke
from keystroke2tei.html_parser import parse_html
from keystroke2tei.converter import convert
from keystroke2tei.writer import write_tei

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
) -> bool:
    try:
        if csv_path.suffix.lower() == ".idfx":
            events, metadata, parse_warnings = parse_idfx(csv_path)
        elif csv_path.suffix.lower() == ".html":
            events, metadata, parse_warnings = parse_html(csv_path)
        elif _is_klicke_csv(csv_path):
            events, metadata, parse_warnings = parse_klicke(csv_path)
        else:
            events, metadata, parse_warnings = parse_csv(csv_path)
        result = convert(events, metadata=metadata, parse_warnings=len(parse_warnings))

        if classify:
            from keystroke2tei.classifier import reclassify_with_llm
            changed = reclassify_with_llm(result.segments, result.final_text)
            if verbose and changed:
                print(f"    [classify] LLM reclassified {changed} revision(s)", file=sys.stderr)

        xml = write_tei(result.segments, metadata=metadata, focus_sources=result.focus_sources)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml, encoding="utf-8")

        s = result.stats
        print(f"  {csv_path.name} -> {out_path.name}  "
              f"({s.typed_chars} chars, {s.deletions} dels, "
              f"{s.episodes} episodes, {s.segments} segments)")

        if verbose:
            if parse_warnings:
                for w in parse_warnings:
                    print(f"    [parse] {w}", file=sys.stderr)
            for d in result.diagnostics:
                print(f"    [{d.level}] event {d.event_id} (t={d.timestamp}): {d.message}",
                      file=sys.stderr)

        if write_stats:
            stats_path = out_path.with_name(out_path.stem.removesuffix(".tei") + ".stats.json")
            stats_path.write_text(
                json.dumps(s.to_dict(), indent=2) + "\n",
                encoding="utf-8",
            )

        return True
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
    args = parser.parse_args()

    if args.classify:
        from dotenv import load_dotenv
        load_dotenv()

    csv_files = _resolve_inputs(args.inputs)
    if not csv_files:
        print("No CSV files found.", file=sys.stderr)
        sys.exit(1)

    ok = 0
    fail = 0
    for csv_path in csv_files:
        out_path = _resolve_output(csv_path, args.output)
        if _process_single(csv_path, out_path, args.verbose, args.stats, args.classify):
            ok += 1
        else:
            fail += 1

    if len(csv_files) > 1:
        print(f"\nProcessed {ok + fail} files: {ok} ok, {fail} errors")

    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
