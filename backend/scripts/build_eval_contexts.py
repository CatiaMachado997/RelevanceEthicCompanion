"""Build a deterministic, balanced DeepEval context file from the local KB."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


def read_source(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8", errors="replace")


def chunks(text: str, size: int = 600, overlap: int = 80) -> list[str]:
    words = re.sub(r"\s+", " ", text).strip().split(" ")
    step = size - overlap
    return [
        " ".join(words[i : i + size])
        for i in range(0, len(words), step)
        if len(words[i : i + size]) >= 120
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("knowledge_base", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()

    sources = sorted(
        path
        for path in args.knowledge_base.glob("**/*")
        if path.is_file()
        and path.suffix.lower() in {".pdf", ".md", ".txt"}
        and path.name not in {"README.md", "catalog.md", ".gitkeep"}
    )
    fingerprint = hashlib.sha256()
    per_source: list[tuple[Path, list[str]]] = []
    for source in sources:
        data = source.read_bytes()
        fingerprint.update(str(source.relative_to(args.knowledge_base)).encode())
        fingerprint.update(hashlib.sha256(data).digest())
        per_source.append((source, chunks(read_source(source))))

    selected: list[list[str]] = []
    selected_sources: list[dict[str, str]] = []
    offset = 0
    while len(selected) < args.count:
        progressed = False
        for source, source_chunks in per_source:
            if offset < len(source_chunks):
                selected.append([source_chunks[offset]])
                selected_sources.append(
                    {
                        "source_path": str(source.relative_to(args.knowledge_base)),
                        "source_name": source.name,
                    }
                )
                progressed = True
                if len(selected) == args.count:
                    break
        if not progressed:
            break
        offset += 1
    if len(selected) < args.count:
        raise SystemExit(
            f"Only {len(selected)} usable contexts; requested {args.count}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest = args.output.with_suffix(".manifest.json")
    state = {
        "fingerprint": fingerprint.hexdigest(),
        "count": len(selected),
        "contexts": selected_sources,
    }
    if args.output.exists() and manifest.exists():
        if json.loads(manifest.read_text()) == state:
            print(f"unchanged: {args.output} ({len(selected)} contexts)")
            return
    args.output.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n")
    manifest.write_text(json.dumps(state, indent=2) + "\n")
    print(
        f"wrote: {args.output} ({len(selected)} contexts from {len(sources)} sources)"
    )


if __name__ == "__main__":
    main()
