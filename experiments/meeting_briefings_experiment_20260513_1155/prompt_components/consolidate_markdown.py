#!/usr/bin/env python3
"""Consolidate markdown files into meeting_briefing_runbook.md."""

from __future__ import annotations

import argparse
from pathlib import Path


def _order_files_by_briefing_template(folder: Path, files: list[Path]) -> list[Path]:
    briefing_file = folder / "meeting_briefing.md"
    if not briefing_file.exists():
        return sorted(files)

    text = briefing_file.read_text(encoding="utf-8")
    ordered_names: list[str] = []
    for token in text.split("`"):
        token = token.strip()
        if token.endswith(".md") and token not in ordered_names:
            ordered_names.append(token)

    ordered_files: list[Path] = []
    remaining_files = list(files)
    for name in ordered_names:
        match = next((path for path in remaining_files if path.name == name), None)
        if match:
            ordered_files.append(match)
            remaining_files.remove(match)

    ordered_files.extend(sorted(remaining_files))
    return ordered_files


def consolidate_markdown(folder: Path, output_name: str = "meeting_briefing_runbook.md") -> None:
    folder = folder.resolve()
    target = folder / output_name

    source_files = [path for path in folder.glob("*.md") if path.name != output_name]
    source_files = _order_files_by_briefing_template(folder, source_files)

    if not source_files:
        raise FileNotFoundError(f"No markdown files found in {folder}")

    parts = []
    for path in source_files:
        text = path.read_text(encoding="utf-8").rstrip()
        parts.append(f"<!-- Source: {path.name} -->\n{text}")

    consolidated = "\n\n".join(parts).rstrip() + "\n"
    target.write_text(consolidated, encoding="utf-8")
    print(f"Wrote consolidated file: {target}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consolidate markdown files in a folder into meeting_briefing_runbook.md"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=Path(__file__).parent,
        type=Path,
        help="Folder containing markdown files to consolidate",
    )
    parser.add_argument(
        "--output",
        default="meeting_briefing_runbook.md",
        help="Name of the output markdown file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    consolidate_markdown(args.folder, args.output)


if __name__ == "__main__":
    main()
