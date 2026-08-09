"""Reconstruct source documents from a legacy Weaviate object export.

The legacy collection stored page/chunk text but not original file bytes. This
utility groups objects by source, sorts them by page/start offset, removes exact
duplicate chunks, and writes one readable Markdown file per source.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


def _safe_name(source: str) -> str:
    name = Path(source).name
    name = re.sub(r"%3A", "-", name, flags=re.IGNORECASE)
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    return f"{name or 'legacy-source'}.recovered.md"


def materialize(export_path: Path, output_dir: Path) -> list[Path]:
    payload: dict[str, Any] = json.loads(export_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obj in payload.get("objects", []):
        props = obj.get("properties") or {}
        text = str(props.get("text") or "").strip()
        if text:
            grouped[str(props.get("source") or "unknown-source")].append(props)

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source, chunks in sorted(grouped.items()):
        chunks.sort(
            key=lambda item: (
                int(item.get("page") or 0),
                int(item.get("start_index") or 0),
                str(item.get("text") or ""),
            )
        )
        seen: set[str] = set()
        unique = []
        for chunk in chunks:
            text = str(chunk.get("text") or "").strip()
            if text not in seen:
                seen.add(text)
                unique.append(chunk)

        title = next(
            (str(chunk["title"]) for chunk in unique if chunk.get("title")),
            Path(source).name,
        )
        lines = [
            f"# {title}",
            "",
            f"Legacy source: `{source}`",
            f"Recovered unique chunks: {len(unique)}",
            "",
        ]
        last_page: int | None = None
        for chunk in unique:
            page = int(chunk.get("page") or 0)
            if page != last_page:
                lines.extend([f"## Page {page + 1}", ""])
                last_page = page
            lines.extend([str(chunk.get("text") or "").strip(), ""])

        destination = output_dir / _safe_name(source)
        destination.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        written.append(destination)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    for path in materialize(args.export, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
