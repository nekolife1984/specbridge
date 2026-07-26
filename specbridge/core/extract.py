"""Framework-agnostic tag extractor.

Supports:
  - Line comments: # @impl 1.1, // @impl 1.1, 1.2
  - Doc-comments:  # @module auth, # @feature login
  - HTML comments: <!-- @spec 1 -->, <!-- @design AuthService -->
  - Verifies:      # @verifies 1.1, // @verifies 1.1
  - Satisfies:     <!-- @satisfies 1.1, 1.2 -->
  - Boundaries:    _Boundary:_ src/path/

Python files use tokenize-based extraction to avoid matching
tags inside string literals (f-strings, docstrings, etc).
Other languages use regex-based extraction.
"""

from __future__ import annotations

import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path

# Languages that use // (C-style)
_SLASH_COMMENT_EXT = frozenset({
    ".c", ".h", ".cpp", ".hpp", ".cs",
    ".ts", ".tsx", ".js", ".jsx",
    ".go", ".rs", ".kt", ".swift",
    ".java", ".scala", ".dart",
    ".php", ".phtml",
})

# Languages that use # (hash-style)
_HASH_COMMENT_EXT = frozenset({
    ".py", ".rb", ".sh", ".bash", ".zsh",
    ".yaml", ".yml", ".toml",
})

# Spec documents (HTML comments in Markdown)
_SPEC_EXT = frozenset({".md", ".mdx", ".rst"})

# All source extensions we scan
_SOURCE_EXT = _SLASH_COMMENT_EXT | _HASH_COMMENT_EXT

# Only .py uses tokenize-based extraction
_PYTHON_EXT = frozenset({".py"})


# Regex patterns
RE_IMPL_COMMENT = re.compile(
    r"(?:#|//)\s*@impl\s+([a-zA-Z0-9_./-]+(?:\s*,\s*[a-zA-Z0-9_./-]+)*)",
)
RE_MODULE_COMMENT = re.compile(
    r"(?:#|//)\s*@module\s+([a-zA-Z0-9_./,-]+)",
)
RE_FEATURE_COMMENT = re.compile(
    r"(?:#|//)\s*@feature\s+([a-zA-Z0-9_./,-]+)",
)
RE_VERIFIES_COMMENT = re.compile(
    r"(?:#|//)\s*@verifies\s+([a-zA-Z0-9_./-]+(?:\s*,\s*[a-zA-Z0-9_./-]+)*)",
)
RE_SPEC_HTML = re.compile(r"<!--\s*@spec\s+(.+?)\s*-->")
RE_DESIGN_HTML = re.compile(r"<!--\s*@design\s+(.+?)\s*-->")
RE_SATISFIES_HTML = re.compile(r"<!--\s*@satisfies\s+(.+?)\s*-->")
RE_BOUNDARY = re.compile(r"^_Boundary:_\s+(.+)$", re.MULTILINE)

# Shared regex patterns for comment extraction (used by both tokenize and regex paths)
_SOURCE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (RE_IMPL_COMMENT, "impl"),
    (RE_MODULE_COMMENT, "module"),
    (RE_FEATURE_COMMENT, "feature"),
    (RE_VERIFIES_COMMENT, "verifies"),
]


@dataclass
class Tag:
    kind: str        # "impl", "module", "feature", "verifies", "spec", "design", "satisfies"
    value: str       # the parsed value(s)
    file: str        # relative path
    line: int        # 1-indexed
    col: int = 0


def _is_source_file(path: Path) -> bool:
    return path.suffix in _SOURCE_EXT and path.exists()


def _is_spec_file(path: Path) -> bool:
    return path.suffix in _SPEC_EXT and path.exists()


def extract_tags_from_file(path: Path, project_root: Path) -> list[Tag]:
    """Extract all tags from a single file. Returns [] if not a supported format."""
    rel = str(path.relative_to(project_root))

    if _is_spec_file(path):
        return _extract_spec_tags(path, rel)
    if _is_source_file(path):
        return _extract_source_tags(path, rel)
    return []


def _extract_spec_tags(path: Path, rel: str) -> list[Tag]:
    """Extract HTML-comment tags from spec docs."""
    tags: list[Tag] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return tags

    for pattern, kind in [
        (RE_SPEC_HTML, "spec"),
        (RE_DESIGN_HTML, "design"),
        (RE_SATISFIES_HTML, "satisfies"),
    ]:
        for m in pattern.finditer(text):
            lineno = text[: m.start()].count("\n") + 1
            tags.append(Tag(kind=kind, value=m.group(1).strip(), file=rel, line=lineno))

    # Also scan for _Boundary:_ markers
    for m in RE_BOUNDARY.finditer(text):
        lineno = text[: m.start()].count("\n") + 1
        tags.append(Tag(kind="boundary", value=m.group(1).strip(), file=rel, line=lineno))

    return tags


# ── Tokenize-based Python extractor ──────────────────────────────────


def _extract_python_comments(text: str) -> list[tuple[int, str]]:
    """Extract actual comment lines from Python source using tokenize.

    Returns list of (line_number_1_indexed, comment_text).
    Only returns COMMENT tokens, ignoring STRING tokens (docstrings, f-strings, etc).
    """
    comments: list[tuple[int, str]] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                comments.append((tok.start[0], tok.line))
    except (tokenize.TokenError, IndentationError):
        # Fall back to regex if tokenize fails (e.g. syntax errors in source)
        pass
    return comments


def _extract_python_source_tags(path: Path, rel: str) -> list[Tag]:
    """Extract tags from Python source using tokenize (only real comments)."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    tags: list[Tag] = []
    comments = _extract_python_comments(text)

    for lineno, line in comments:
        for pattern, kind in _SOURCE_PATTERNS:
            m = pattern.search(line)
            if m:
                tags.append(Tag(kind=kind, value=m.group(1).strip(), file=rel, line=lineno))
                break  # one tag kind per comment line

    return tags


# ── Regex-based source extractor (all non-Python source files) ─────────


def _extract_regex_source_tags(path: Path, rel: str) -> list[Tag]:
    """Extract tags from non-Python source using regex."""
    tags: list[Tag] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return tags

    for pattern, kind in _SOURCE_PATTERNS:
        for m in pattern.finditer(text):
            lineno = text[: m.start()].count("\n") + 1
            tags.append(Tag(kind=kind, value=m.group(1).strip(), file=rel, line=lineno))

    return tags


def _extract_source_tags(path: Path, rel: str) -> list[Tag]:
    """Extract tags from source code — tokenize for Python, regex for others."""
    if path.suffix in _PYTHON_EXT:
        return _extract_python_source_tags(path, rel)
    return _extract_regex_source_tags(path, rel)


# ── Directory scanner ─────────────────────────────────────────────────


def extract_tags_from_dir(
    directory: str,
    *,
    exclude_dirs: set[str] | None = None,
) -> list[Tag]:
    """Recursively scan *directory* for all known tags."""
    if exclude_dirs is None:
        exclude_dirs = {".git", "node_modules", ".venv", "__pycache__", "dist", "build",
                        ".spectra", ".specbridge", ".artgraph", ".trace"}

    root = Path(directory).resolve()
    all_tags: list[Tag] = []

    for fpath in sorted(root.rglob("*")):
        if not fpath.is_file():
            continue
        if any(part in exclude_dirs for part in fpath.parts):
            continue
        all_tags.extend(extract_tags_from_file(fpath, root))

    return all_tags
