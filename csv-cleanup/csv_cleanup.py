#!/usr/bin/env python3
"""Deterministic, auditable CSV cleanup using only the Python standard library."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def normalize_cell(value: str, blank_tokens: set[str]) -> tuple[str, list[str]]:
    changes: list[str] = []
    normalized = value.strip()
    if normalized != value:
        changes.append("trimmed_whitespace")
    if normalized.casefold() in blank_tokens and normalized != "":
        normalized = ""
        changes.append("normalized_blank")
    return normalized, changes


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean(input_path: Path, output_path: Path, report_path: Path, dedupe_columns: list[str] | None = None) -> dict[str, Any]:
    resolved = [path.resolve() for path in (input_path, output_path, report_path)]
    if len(set(resolved)) != 3:
        raise ValueError("Input, output, and report paths must be different; the source is never overwritten")
    blank_tokens = {"n/a", "na", "null", "none"}
    with input_path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV must have a header row")
        headers = [header.strip() for header in reader.fieldnames]
        if len(set(headers)) != len(headers):
            raise ValueError("Headers become duplicated after whitespace trimming")
        rows = list(reader)
        for source_row_number, row in enumerate(rows, start=2):
            if None in row:
                raise ValueError(f"Row {source_row_number} has more fields than the header; refusing silent data loss")

    dedupe_columns = dedupe_columns or headers
    unknown = sorted(set(dedupe_columns) - set(headers))
    if unknown:
        raise ValueError(f"Unknown dedupe column(s): {', '.join(unknown)}")

    counts: Counter[str] = Counter()
    seen: set[tuple[str, ...]] = set()
    output_rows: list[dict[str, str]] = []
    removed: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    for source_row_number, row in enumerate(rows, start=2):
        cleaned: dict[str, str] = {}
        for original_header, header in zip(reader.fieldnames or [], headers):
            value, changes = normalize_cell(row.get(original_header, "") or "", blank_tokens)
            cleaned[header] = value
            counts.update(changes)
            if value.startswith(("=", "+", "-", "@")):
                counts["formula_like_cells"] += 1
                exceptions.append({"source_row": source_row_number, "column": header, "kind": "formula_like_cell", "value": value})
        key = tuple(cleaned[column] for column in dedupe_columns)
        if not any(key):
            counts["blank_dedupe_keys_preserved"] += 1
            exceptions.append({"source_row": source_row_number, "kind": "blank_dedupe_key", "columns": dedupe_columns})
            output_rows.append(cleaned)
            continue
        if key in seen:
            counts["duplicates_removed"] += 1
            removed.append({"source_row": source_row_number, "dedupe_key": dict(zip(dedupe_columns, key))})
            continue
        seen.add(key)
        output_rows.append(cleaned)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    report = {
        "input": str(input_path.resolve()),
        "output": str(output_path.resolve()),
        "input_sha256": sha256(input_path),
        "output_sha256": sha256(output_path),
        "rows_in": len(rows),
        "rows_out": len(output_rows),
        "headers": headers,
        "dedupe_columns": dedupe_columns,
        "changes": dict(sorted(counts.items())),
        "removed_duplicates": removed,
        "exceptions": exceptions,
        "policy": {
            "whitespace": "Trim leading/trailing whitespace in every cell.",
            "blanks": "Convert case-insensitive N/A, NA, NULL, and NONE to empty.",
            "dedupe": "Keep the first exact normalized non-blank match on the selected key; preserve all-blank keys; do not fuzzy-match or guess.",
            "formula_safety": "Flag cells beginning with =, +, -, or @ for review; preserve their values instead of guessing intent.",
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean and exactly deduplicate a CSV with a complete JSON change report.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dedupe-on", help="Comma-separated column names; defaults to the full row")
    args = parser.parse_args()
    columns = [item.strip() for item in args.dedupe_on.split(",")] if args.dedupe_on else None
    try:
        result = clean(args.input, args.output, args.report, columns)
    except (OSError, csv.Error, ValueError) as exc:
        print(f"error: {exc}")
        return 2
    print(json.dumps({key: result[key] for key in ("rows_in", "rows_out", "changes")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
