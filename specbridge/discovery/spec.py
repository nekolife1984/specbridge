"""Spec document discovery: parse Markdown sections → spec candidates.

Headings are extracted as spec IDs. Each heading's body text
(between this heading and the next) is hashed for drift detection.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_EXCLUDE_DIRS = frozenset({
    ".git", "node_modules", ".venv", "__pycache__", "dist", "build",
    ".spectra", ".specbridge", ".artgraph", ".trace",
    "venv", "env", ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
})
_EXCLUDE_FILES = frozenset({
    "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE.md",
    "index.md", "_sidebar.md", "_navbar.md",
})

_RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_RE_NUMBERED = re.compile(r"^([\d.]+)[.\s]\s*(.*)$")


@dataclass
class SpecCandidate:
    """A potential spec node discovered from a Markdown file."""
    file: str
    heading_depth: int
    heading_text: str
    auto_id: str
    title: str
    line: int
    # Section body (between this heading and the next, or EOF)
    body_text: str = ""
    body_hash: str = ""       # SHA256 of body_text
    body_line_count: int = 0
    body_preview: str = ""    # first 80 chars of body


def _clean_title(text: str) -> str:
    m = _RE_NUMBERED.match(text.strip())
    return m.group(2).strip() if m else text.strip()


def _auto_id(prefix: str, text: str) -> str:
    m = _RE_NUMBERED.match(text.strip())
    if m:
        return f"{prefix}{m.group(1).strip()}" if prefix else m.group(1).strip()
    slug = re.sub(r"[^a-zA-Z0-9_-]", "", text.strip().lower().replace(" ", "-"))[:30]
    return f"{prefix}{slug}" if prefix else slug


def _split_sections(text: str) -> list[dict]:
    """Split markdown into (heading_line_no, depth, heading_raw, body_lines)."""
    sections: list[dict] = []
    lines = text.split("\n")
    current_idx = 0  # line index where current section starts
    current_depth = 0
    current_raw = ""

    for i, line in enumerate(lines):
        m = _RE_HEADING.match(line)
        if not m:
            continue

        depth = len(m.group(1))
        raw = m.group(2).strip()
        if not raw:
            continue

        if current_raw:
            body = "\n".join(lines[current_idx:i])
            sections.append({
                "line": current_idx + 1,
                "depth": current_depth,
                "raw": current_raw,
                "body": body,
            })
        current_idx = i
        current_depth = depth
        current_raw = raw

    # Last section
    if current_raw:
        body = "\n".join(lines[current_idx:])
        sections.append({
            "line": current_idx + 1,
            "depth": current_depth,
            "raw": current_raw,
            "body": body,
        })

    return sections


def discover_specs(
    directory: str,
    *,
    spec_dirs: Optional[list[str]] = None,
    exclude_dirs: Optional[set[str]] = None,
) -> list[SpecCandidate]:
    """Scan a project for spec documents. Returns one SpecCandidate per heading."""
    root = Path(directory).resolve()
    if spec_dirs is None:
        spec_dirs = ["docs", "spec", "specs"]
    if exclude_dirs is None:
        exclude_dirs = set(_EXCLUDE_DIRS)

    candidates: list[SpecCandidate] = []

    for sd in spec_dirs:
        scan_path = root / sd
        if not scan_path.exists():
            continue
        for fpath in sorted(scan_path.rglob("*.md")):
            if any(part in exclude_dirs for part in fpath.parts):
                continue
            if fpath.name in _EXCLUDE_FILES:
                continue
            try:
                text = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            candidates.extend(_parse_sections(fpath, text, root))

    return candidates


def _parse_sections(fpath: Path, text: str, root: Path) -> list[SpecCandidate]:
    """Parse markdown sections from a file. One candidate per heading."""
    rel = str(fpath.relative_to(root))
    parent_path = fpath.parent.relative_to(root)
    id_prefix = str(parent_path).replace("/", ".") + "." if str(parent_path) != "." else ""

    sections = _split_sections(text)
    if not sections:
        return []

    result: list[SpecCandidate] = []
    counters: dict[int, int] = {}

    for sec in sections:
        depth = sec["depth"]
        raw = sec["raw"]

        # Update position counter
        counters[depth] = counters.get(depth, 0) + 1
        for d in range(depth + 1, 7):
            counters.pop(d, None)

        num_parts = [str(counters[d]) for d in range(1, depth + 1) if d in counters]
        hier_id = ".".join(num_parts)
        auto_id = f"{id_prefix}{hier_id}"
        title = _clean_title(raw)

        body = sec["body"]
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        body_lines = body.count("\n") + 1 - 1  # exclude heading line itself
        # Actually body includes the heading line, so body_lines = total lines - 1 (heading)
        preview = body.strip()[:80].replace("\n", " ")

        result.append(SpecCandidate(
            file=rel,
            heading_depth=depth,
            heading_text=raw,
            auto_id=auto_id,
            title=title or raw,
            line=sec["line"],
            body_text=body,
            body_hash=body_hash,
            body_line_count=body_lines,
            body_preview=preview,
        ))

    return result
