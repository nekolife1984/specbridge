"""Spec document discovery: parse Markdown headings → spec candidates.

No tags required — pure heading hierarchy analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Directories and files to skip
_EXCLUDE_DIRS = frozenset({
    ".git", "node_modules", ".venv", "__pycache__", "dist", "build",
    ".spectra", ".specbridge", ".artgraph", ".trace",
    "venv", "env", ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
})
_EXCLUDE_FILES = frozenset({
    "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE.md",
    "index.md", "_sidebar.md", "_navbar.md",
})

# Heading regex: ## 1. Title  or  ### 1.1 Subtitle
_RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Auto-ID from a numbered heading: "1. User Login" → "1", "1.1 Login Form" → "1.1"
_RE_NUMBERED = re.compile(r"^([\d.]+)[.\s]\s*(.*)$")


@dataclass
class SpecCandidate:
    """A potential spec node discovered from a Markdown file."""
    file: str              # relative path
    heading_depth: int     # 1-6
    heading_text: str      # raw heading text
    auto_id: str           # auto-generated ID (e.g. "auth/1", "auth/1.1")
    title: str             # cleaned title
    line: int              # line number in file


def _clean_title(text: str) -> str:
    """Strip numbering prefix from heading text."""
    m = _RE_NUMBERED.match(text.strip())
    if m:
        return m.group(2).strip()
    return text.strip()


def _auto_id(prefix: str, text: str) -> str:
    """Generate an auto-ID from heading text.

    Priority:
      1. Numbered heading: "1.1 Login" → "{prefix}1.1"
      2. Otherwise:        "Login"     → "{prefix}login" (sluggified)
    """
    m = _RE_NUMBERED.match(text.strip())
    if m:
        num_part = m.group(1).strip()
        return f"{prefix}{num_part}" if prefix else num_part
    # Fallback: slugify
    slug = re.sub(r"[^a-zA-Z0-9_-]", "", text.strip().lower().replace(" ", "-"))[:30]
    return f"{prefix}{slug}" if prefix else slug


def discover_specs(
    directory: str,
    *,
    spec_dirs: Optional[list[str]] = None,
    exclude_dirs: Optional[set[str]] = None,
) -> list[SpecCandidate]:
    """Scan a project directory for spec documents and extract candidates.

    Args:
        directory: Project root.
        spec_dirs: Subdirectories to scan (default: ["docs/", "spec/", "specs/"]).
        exclude_dirs: Directories to skip.

    Returns:
        List of SpecCandidates, each representing one markdown heading.
    """
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
            candidates.extend(_parse_headings(fpath, text, root))

    return candidates


def _parse_headings(fpath: Path, text: str, root: Path) -> list[SpecCandidate]:
    """Extract heading-based spec candidates from a single markdown file."""
    rel = str(fpath.relative_to(root))
    # Use the parent directory structure for ID prefix
    parent_path = fpath.parent.relative_to(root)
    id_prefix = str(parent_path).replace("/", ".") + "." if str(parent_path) != "." else ""

    result: list[SpecCandidate] = []
    # Track numbering for hierarchical ID generation
    counters: dict[int, int] = {}

    for m in _RE_HEADING.finditer(text):
        depth = len(m.group(1))
        raw_text = m.group(2).strip()
        if not raw_text:
            continue

        lineno = text[: m.start()].count("\n") + 1

        # Update counter at this depth
        counters[depth] = counters.get(depth, 0) + 1
        # Reset deeper counters
        for d in range(depth + 1, 7):
            counters.pop(d, None)

        # Generate hierarchical number
        num_parts = [str(counters[d]) for d in range(1, depth + 1) if d in counters]
        hier_id = ".".join(num_parts)

        auto_id = f"{id_prefix}{hier_id}"
        title = _clean_title(raw_text)

        # Skip "Overview", "Introduction" etc as leaf specs if they have children?
        result.append(SpecCandidate(
            file=rel,
            heading_depth=depth,
            heading_text=raw_text,
            auto_id=auto_id,
            title=title or raw_text,
            line=lineno,
        ))

    return result
