"""Spec document discovery: parse Markdown sections → spec candidates.

Headings are extracted as spec IDs. Each heading's body text
(between this heading and the next) is hashed for drift detection.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specbridge.discovery.scanner import walk_files

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
    # Parent heading texts (from top-level down to immediate parent)
    # e.g. for "### 2.1 TraceNode": parent_chain = ["Data Model", "Type Hierarchy"]
    parent_chain: list[str] | None = None
    # Section body (between this heading and the next, or EOF)
    body_text: str = ""
    body_hash: str = ""       # SHA256 of body_text (including heading line)
    body_hash_content: str = ""  # SHA256 of body without heading line
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


def _split_sections(text: str) -> list[dict[str, Any]]:
    """Split markdown into (heading_line_no, depth, heading_raw, body_lines)."""
    sections: list[dict[str, Any]] = []
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
    spec_dirs: list[str] | None = None,
    exclude_dirs: set[str] | None = None,
    spec_files: list[str] | None = None,
) -> list[SpecCandidate]:
    """Scan a project for spec documents. Returns one SpecCandidate per heading.

    *spec_files* lists individual Markdown files (relative to project root)
    to include as specs, bypassing ``_EXCLUDE_FILES``. Use this for root-level
    documents such as ``README.md``, ``AGENTS.md``, etc.
    """
    root = Path(directory).resolve()
    if spec_dirs is None:
        spec_dirs = ["docs", "spec", "specs"]
    if exclude_dirs is None:
        exclude_dirs = set(_EXCLUDE_DIRS)

    candidates: list[SpecCandidate] = []
    seen_files: set[str] = set()  # track processed file paths to avoid duplicates

    for sd in spec_dirs:
        scan_path = root / sd
        if not scan_path.exists():
            continue
        for fpath in walk_files(scan_path, {".md"}, exclude_dirs=exclude_dirs):
            if fpath.name in _EXCLUDE_FILES:
                continue
            try:
                text = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            rel = str(fpath.relative_to(root))
            seen_files.add(rel)
            candidates.extend(_parse_sections(fpath, text, root))
        # Also scan .yaml/.yml spec files (v1.1+)
        for fpath in walk_files(scan_path, {".yaml", ".yml"}, exclude_dirs=exclude_dirs):
            try:
                text = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            rel = str(fpath.relative_to(root))
            seen_files.add(rel)
            candidates.extend(_parse_yaml_specs(fpath, text, root))

    # ✨ Explicit spec files (bypass _EXCLUDE_FILES, skip if already seen)
    for fname in (spec_files or []):
        fpath = root / fname
        rel = str(Path(fname))
        if rel in seen_files:
            continue
        if not fpath.exists() or not fpath.is_file():
            import warnings
            warnings.warn(f"spec_file not found: {fname}", stacklevel=2)
            continue
        try:
            text = fpath.read_text(encoding="utf-8")
        except Exception:
            continue
        if fpath.suffix.lower() in (".yaml", ".yml"):
            candidates.extend(_parse_yaml_specs(fpath, text, root))
        else:
            candidates.extend(_parse_sections(fpath, text, root))

    return candidates


def _parse_sections(fpath: Path, text: str, root: Path) -> list[SpecCandidate]:
    """Parse markdown sections from a file. One candidate per heading."""
    rel = str(fpath.relative_to(root))
    parent_path = fpath.parent.relative_to(root)
    # Include the file stem to avoid cross-file ID collisions
    file_stem = fpath.stem
    id_prefix = str(parent_path).replace("/", ".") + "." if str(parent_path) != "." else "root."
    id_prefix += file_stem + "."

    sections = _split_sections(text)
    if not sections:
        return []

    result: list[SpecCandidate] = []
    counters: dict[int, int] = {}
    heading_chain: dict[int, str] = {}  # depth → heading text for parent tracking

    for sec in sections:
        depth = sec["depth"]
        raw = sec["raw"]

        # Update position counter
        counters[depth] = counters.get(depth, 0) + 1
        for d in range(depth + 1, 7):
            counters.pop(d, None)

        # Update heading chain: set this level, clear deeper
        heading_chain[depth] = raw
        for d in range(depth + 1, 7):
            heading_chain.pop(d, None)
        # Build parent chain (texts from level 1 up to depth-1)
        parent_chain = [heading_chain[d] for d in range(1, depth) if d in heading_chain]

        num_parts = [str(counters[d]) for d in range(1, depth + 1) if d in counters]
        hier_id = ".".join(num_parts)
        auto_id = f"{id_prefix}{hier_id}"
        title = _clean_title(raw)

        body = sec["body"]
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        # Body hash without the heading line (for rename detection)
        body_lines_for_hash = body.split("\n")
        body_without_heading = "\n".join(body_lines_for_hash[1:]) if len(body_lines_for_hash) > 1 else ""
        body_hash_content = hashlib.sha256(body_without_heading.encode("utf-8")).hexdigest()[:16]
        body_lines = body.count("\n") + 1 - 1  # exclude heading line itself
        # Actually body includes the heading line, so body_lines = total lines - 1 (heading)
        preview = body.strip()[:80].replace("\n", " ")

        result.append(SpecCandidate(
            file=rel,
            heading_depth=depth,
            heading_text=raw,
            parent_chain=parent_chain,
            auto_id=auto_id,
            title=title or raw,
            line=sec["line"],
            body_text=body,
            body_hash=body_hash,
            body_hash_content=body_hash_content,
            body_line_count=body_lines,
            body_preview=preview,
        ))

    return result


def _parse_yaml_specs(fpath: Path, text: str, root: Path) -> list[SpecCandidate]:
    """Parse YAML spec definitions from a .yaml/.yml file.

    Expected format:
    ```yaml
    specs:
      - id: 1.1
        title: Authentication
        description: User authentication flow
        parent: Security
        tags: [auth, security]
    ```

    The ``parent`` field builds the hierarchy. When absent, the spec is top-level.
    """
    import hashlib
    import yaml

    rel = str(fpath.relative_to(root))
    parent_path = fpath.parent.relative_to(root)
    file_stem = fpath.stem
    id_prefix = str(parent_path).replace("/", ".") + "." if str(parent_path) != "." else "root."
    id_prefix += file_stem + "."

    try:
        data = yaml.safe_load(text)
    except Exception:
        return []

    if not isinstance(data, dict) or "specs" not in data:
        return []

    raw_specs = data["specs"]
    if not isinstance(raw_specs, list):
        return []

    # Build depth map: id → (depth, parent_chain)
    depth_map: dict[str, tuple[int, list[str]]] = {}
    spec_map: dict[str, dict[str, Any]] = {}

    for entry in raw_specs:
        if not isinstance(entry, dict):
            continue
        sid = entry.get("id", "")
        if not isinstance(sid, str):
            sid = str(sid) if sid is not None else ""
        if not sid:
            continue
        spec_map[sid] = entry

    # Resolve parent hierarchy
    def _resolve_depth(sid: str, seen: set[str] | None = None) -> tuple[int, list[str]]:
        if seen is None:
            seen = set()
        if sid in seen:
            return 1, []  # circular reference guard
        if sid in depth_map:
            return depth_map[sid]
        entry = spec_map.get(sid)
        if not entry:
            return 1, []
        parent = entry.get("parent")
        if not parent or not isinstance(parent, str) or parent == sid:
            depth_map[sid] = (1, [])
            return (1, [])
        seen.add(sid)
        pdepth, pchain = _resolve_depth(parent, seen)
        chain = pchain + [spec_map.get(parent, {}).get("title", parent)]
        depth_map[sid] = (pdepth + 1, chain)
        return (pdepth + 1, chain)

    # Resolve all depths
    for sid in spec_map:
        _resolve_depth(sid)

    candidates: list[SpecCandidate] = []
    for idx, entry in enumerate(raw_specs):
        if not isinstance(entry, dict):
            continue
        raw_sid = entry.get("id", "")
        if not isinstance(raw_sid, str):
            raw_sid = str(raw_sid) if raw_sid is not None else ""
        spec_id_str: str = raw_sid
        raw_title = entry.get("title", spec_id_str) if isinstance(entry.get("title"), str) else str(entry.get("title", spec_id_str))
        title_str: str = raw_title if isinstance(raw_title, str) else str(raw_title)
        description = entry.get("description", "")
        raw_parent = entry.get("parent", "")
        parent = str(raw_parent) if raw_parent is not None else ""
        tags = entry.get("tags", [])

        depth, parent_chain = depth_map.get(spec_id_str, (1, []))
        hier_id = spec_id_str.replace(".", ".")
        auto_id = f"{id_prefix}{hier_id}" if spec_id_str else ""

        # Build body text from all YAML fields
        body_parts = []
        if description:
            body_parts.append(f"Description: {description}")
        if tags:
            body_parts.append(f"Tags: {', '.join(tags) if isinstance(tags, list) else str(tags)}")
        if parent:
            body_parts.append(f"Parent: {parent}")
        body_text = "\n".join(body_parts)
        body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()[:16]

        # Build YAML entry text (without heading line) for content hash
        yaml_lines = [f"id: {spec_id_str}", f"title: {title_str}"]
        if description:
            yaml_lines.append(f"description: {description}")
        if parent:
            yaml_lines.append(f"parent: {parent}")
        if tags:
            yaml_lines.append(f"tags: {tags}")
        yaml_content = "\n".join(yaml_lines)
        body_hash_content = hashlib.sha256(yaml_content.encode("utf-8")).hexdigest()[:16]

        candidates.append(SpecCandidate(
            file=rel,
            heading_depth=depth,
            heading_text=title_str,
            auto_id=auto_id,
            title=title_str,
            line=idx + 2,  # approximate: skip "specs:" line
            parent_chain=parent_chain if parent_chain else None,
            body_text=body_text,
            body_hash=body_hash,
            body_hash_content=body_hash_content,
            body_line_count=len(body_parts),
            body_preview=str(description[:80] if description else title_str),
        ))

    return candidates
