"""Code discovery: scan source files for modules, functions, classes.

No tags required — pure file structure + basic AST analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Supported source file types (ext → comment style, language name)
_SOURCE_MAP: dict[str, tuple[str, str]] = {
    # Hash-comment languages
    ".py":   ("#",    "Python"),
    ".rb":   ("#",    "Ruby"),
    ".sh":   ("#",    "Shell"),
    ".bash": ("#",    "Bash"),
    ".zsh":  ("#",    "Zsh"),
    # Slash-comment languages
    ".ts":   ("//",   "TypeScript"),
    ".tsx":  ("//",   "TSX"),
    ".js":   ("//",   "JavaScript"),
    ".jsx":  ("//",   "JSX"),
    ".go":   ("//",   "Go"),
    ".rs":   ("//",   "Rust"),
    ".cpp":  ("//",   "C++"),
    ".hpp":  ("//",   "C++ Header"),
    ".c":    ("//",   "C"),
    ".h":    ("//",   "C Header"),
    ".cs":   ("//",   "C#"),
    ".java": ("//",   "Java"),
    ".kt":   ("//",   "Kotlin"),
    ".swift": ("//",  "Swift"),
    ".scala": ("//",  "Scala"),
    ".dart": ("//",   "Dart"),
    ".php":  ("//",   "PHP"),
    ".phtml": ("//",  "PHP (HTML)"),
}

# Basic function/class definition pattern (multi-language)
_RE_SYMBOL = re.compile(
    r"(?:"
    r"(?:^|\s)(?:def|class|function|fn|trait|interface|struct|enum|impl|mixin|extension|typedef)\s+([A-Za-z_]\w*)|"
    r"(?:public|private|protected|static|async|export)?\s*(?:function|class|enum)\s+([A-Za-z_]\w*)|"
    r"(?:^|\s)(?:let|var|const)\s+([A-Za-z_]\w*)\s*[=:]|"
    r"(?:^|\s)(?:func|pub fn)\s+([A-Za-z_]\w*)"
    r")",
    re.MULTILINE,
)

_EXCLUDE_DIRS = frozenset({
    ".git", "node_modules", ".venv", "__pycache__", "dist", "build",
    ".spectra", ".specbridge", ".artgraph", ".trace",
    "venv", "env", ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".egg-info", "site-packages", "coverage", "htmlcov", "node_modules",
})
_EXCLUDE_DIR_PREFIXES = ("__", ".")

_TEST_FILE_PATTERNS = (
    "test_", "_test", ".test.", ".spec.", "Test", "_spec.",
)

_DOC_DIRS = frozenset({"docs", "spec", "specs", "doc", "documentation"})


@dataclass
class CodeCandidate:
    """A potential code node discovered from the source tree."""
    file: str                     # relative path from project root
    module: str                   # directory-based module name
    symbols: list[str]            # extracted function/class names
    is_test: bool                 # likely a test file
    language: str                 # "Python", "TypeScript", etc.
    imports: list[str]            # import statements (basic)
    line_count: int               # total lines


def _is_test_file(path: Path) -> bool:
    stem = path.stem.lower()
    return any(pattern in stem for pattern in _TEST_FILE_PATTERNS)


def _extract_imports(text: str, ext: str) -> list[str]:
    """Basic import extraction per language."""
    imports: list[str] = []
    if ext == ".py":
        for m in re.finditer(r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", text, re.MULTILINE):
            imports.append(m.group(1) or m.group(2))
    elif ext in (".ts", ".tsx", ".js", ".jsx"):
        for m in re.finditer(r"(?:import\s+.*?from\s+['\"](.+?)['\"]|require\(['\"](.+?)['\"]\))", text):
            imports.append(m.group(1) or m.group(2))
    elif ext == ".go":
        for m in re.finditer(r'^\s*["\](.+?)["\]', text, re.MULTILINE):
            # Go imports are complex, skip for now
            pass
    elif ext in (".rs",):
        for m in re.finditer(r"^use\s+([\w:]+)", text, re.MULTILINE):
            imports.append(m.group(1))
    return imports[:10]  # cap at 10


def discover_code(
    directory: str,
    *,
    source_dirs: Optional[list[str]] = None,
    exclude_dirs: Optional[set[str]] = None,
) -> list[CodeCandidate]:
    """Scan a project directory for source code and extract candidates.

    Args:
        directory: Project root.
        source_dirs: Subdirectories to scan (default: ["src/", "lib/", "app/"]).
        exclude_dirs: Directories to skip.

    Returns:
        List of CodeCandidates, each representing one source file.
    """
    root = Path(directory).resolve()
    if source_dirs is None:
        source_dirs = ["src", "lib", "app"]
    if exclude_dirs is None:
        exclude_dirs = set(_EXCLUDE_DIRS)

    candidates: list[CodeCandidate] = []

    for sd in source_dirs:
        scan_path = root / sd
        if not scan_path.exists():
            continue
        for ext, (_, lang) in _SOURCE_MAP.items():
            for fpath in sorted(scan_path.rglob(f"*{ext}")):
                if any(part in exclude_dirs for part in fpath.parts):
                    continue
                if fpath.name.startswith("."):
                    continue
                try:
                    text = fpath.read_text(encoding="utf-8")
                except Exception:
                    continue

                rel = str(fpath.relative_to(root))
                # Module name = immediate parent directory name
                module = fpath.parent.name if fpath.parent != root else fpath.stem

                symbols = _extract_symbols(text)
                is_test = _is_test_file(fpath)
                imports = _extract_imports(text, ext)

                candidates.append(CodeCandidate(
                    file=rel,
                    module=module,
                    symbols=symbols,
                    is_test=is_test,
                    language=lang,
                    imports=imports,
                    line_count=text.count("\n") + 1,
                ))

    return candidates


def _extract_symbols(text: str) -> list[str]:
    """Extract function/class names from source text."""
    seen: set[str] = set()
    symbols: list[str] = []
    for m in _RE_SYMBOL.finditer(text):
        name = next((g for g in m.groups() if g), None)
        if name and name not in seen:
            seen.add(name)
            symbols.append(name)
    return symbols
