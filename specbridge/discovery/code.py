"""Code discovery: scan source files for modules, functions, classes.

Extracts function/class-level body hashes for drift detection.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from specbridge.discovery.scanner import walk_files

_SOURCE_MAP: dict[str, tuple[str, str]] = {
    ".py":   ("#",    "Python"),
    ".rb":   ("#",    "Ruby"),
    ".sh":   ("#",    "Shell"),
    ".bash": ("#",    "Bash"),
    ".zsh":  ("#",    "Zsh"),
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

# Function/class definition pattern (multi-language)
_RE_FUNC_DEF = re.compile(
    r"^\s*"
    r"(?:"
    r"(?:\s*(?:public|private|protected|static|async|export|pub|override"
    r"|abstract|virtual|sealed|internal|open)\s+)*"
    r"(?:def|function|fn|class|trait|interface|struct|enum|impl"
    r"|mixin|extension|typedef|record)"
    r"\s+([A-Za-z_]\w*)"
    r")"
    r".*?(?:\(|: |:|=>|=|{)",
    re.MULTILINE,
)

_EXCLUDE_DIRS = frozenset({
    ".git", "node_modules", ".venv", "__pycache__", "dist", "build",
    ".spectra", ".specbridge", ".artgraph", ".trace",
    "venv", "env", ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".egg-info", "site-packages", "coverage", "htmlcov",
})
_EXCLUDE_DIR_PREFIXES = ("__", ".")
_TEST_FILE_PATTERNS = ("test_", "_test", ".test.", ".spec.", "Test", "_spec.")
_DOC_DIRS = frozenset({"docs", "spec", "specs", "doc", "documentation"})


@dataclass
class FuncBlock:
    """A function or class definition with its body."""
    name: str
    kind: str           # "function", "class", "method"
    line: int
    body_hash: str      # SHA256[:16] of the function body text
    body_lines: int
    body_preview: str   # first 80 chars


@dataclass
class CodeCandidate:
    file: str
    module: str
    symbols: list[str]
    is_test: bool
    language: str
    imports: list[str]
    line_count: int
    functions: list[FuncBlock]             # per-function body hashes
    file_hash: str = ""                    # SHA256[:16] of full file


def _is_test_file(path: Path) -> bool:
    stem = path.stem.lower()
    return any(pattern in stem for pattern in _TEST_FILE_PATTERNS)


def _extract_imports(text: str, ext: str) -> list[str]:
    imports: list[str] = []
    if ext == ".py":
        for m in re.finditer(r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", text, re.MULTILINE):
            imports.append(m.group(1) or m.group(2))
    elif ext in (".ts", ".tsx", ".js", ".jsx"):
        for m in re.finditer(r'(?:import\s+.*?from\s+[\'"](.+?)[\'"]|require\([\'"](.+?)[\'"]\))', text):
            imports.append(m.group(1) or m.group(2))
    elif ext in (".rs",):
        for m in re.finditer(r"^use\s+([\w:]+)", text, re.MULTILINE):
            imports.append(m.group(1))
    return imports[:8]


def _extract_func_blocks(text: str, lines: list[str]) -> list[FuncBlock]:
    """Extract function/class definitions with their body text.

    Uses line-based extraction: each definition body spans from its
    own line to the line before the next definition (or EOF).
    """
    defs: list[tuple[int, str, str]] = []  # (line_no_0idx, name, kind)

    for i, line in enumerate(lines):
        m = _RE_FUNC_DEF.match(line)
        if not m:
            continue
        name = m.group(1)
        # Determine kind
        if line.lstrip().startswith(("class ", "trait ", "interface ", "struct ", "enum ", "record ")):
            kind = "class"
        elif "def " in line or "fn " in line or "function " in line:
            kind = "function"
        else:
            kind = "function"
        defs.append((i, name, kind))

    if not defs:
        return []

    blocks: list[FuncBlock] = []
    for idx, (start, name, kind) in enumerate(defs):
        end = defs[idx + 1][0] if idx + 1 < len(defs) else len(lines)
        body = "\n".join(lines[start:end])
        blines = end - start
        bhash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]

        preview = body.strip()[:80].replace("\n", " ")
        blocks.append(FuncBlock(
            name=name,
            kind=kind,
            line=start + 1,
            body_hash=bhash,
            body_lines=blines,
            body_preview=preview,
        ))

    return blocks


def discover_code(
    directory: str,
    *,
    source_dirs: list[str] | None = None,
    exclude_dirs: set[str] | None = None,
    source_files: list[str] | None = None,
) -> list[CodeCandidate]:
    root = Path(directory).resolve()
    if source_dirs is None:
        source_dirs = ["src", "lib", "app"]
    if exclude_dirs is None:
        exclude_dirs = set(_EXCLUDE_DIRS)

    candidates: list[CodeCandidate] = []
    source_extensions = set(_SOURCE_MAP.keys())

    for sd in source_dirs:
        scan_path = root / sd
        if not scan_path.exists():
            continue
        for fpath in walk_files(scan_path, source_extensions, exclude_dirs=exclude_dirs, exclude_prefixes=(".",)):
            ext = fpath.suffix
            _, lang = _SOURCE_MAP[ext]
            try:
                text = fpath.read_text(encoding="utf-8")
            except Exception:
                continue

            rel = str(fpath.relative_to(root))
            module = fpath.parent.name if fpath.parent != root else fpath.stem
            lines = text.split("\n")

            symbols = sorted(set(_extract_symbol_names(text)))
            is_test = _is_test_file(fpath)
            imports = _extract_imports(text, ext)
            funcs = _extract_func_blocks(text, lines)
            fhash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

            candidates.append(CodeCandidate(
                file=rel,
                module=module,
                symbols=symbols,
                is_test=is_test,
                language=lang,
                imports=imports,
                line_count=len(lines),
                functions=funcs,
                file_hash=fhash,
            ))

    # ✨ Explicit source files
    for fname in (source_files or []):
        fpath = root / fname
        if not fpath.exists() or not fpath.is_file():
            import warnings
            warnings.warn(f"source_file not found: {fname}", stacklevel=2)
            continue
        ext = fpath.suffix
        if ext not in _SOURCE_MAP:
            continue
        try:
            text = fpath.read_text(encoding="utf-8")
        except Exception:
            continue

        rel = str(fpath.relative_to(root))
        module = fpath.parent.name if fpath.parent != root else fpath.stem
        lines = text.split("\n")
        _, lang = _SOURCE_MAP[ext]

        symbols = sorted(set(_extract_symbol_names(text)))
        is_test = _is_test_file(fpath)
        imports = _extract_imports(text, ext)
        funcs = _extract_func_blocks(text, lines)
        fhash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        candidates.append(CodeCandidate(
            file=rel,
            module=module,
            symbols=symbols,
            is_test=is_test,
            language=lang,
            imports=imports,
            line_count=len(lines),
            functions=funcs,
            file_hash=fhash,
        ))

    return candidates


def _extract_symbol_names(text: str) -> list[str]:
    """Extract function/class/struct/enum names from source text."""
    seen: set[str] = set()
    names: list[str] = []
    for m in _RE_FUNC_DEF.finditer(text):
        name = m.group(1)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names
