"""Tree-sitter AST-based code analysis (optional enhancement).

When tree-sitter is available, provides more accurate function/class
extraction compared to regex-based approaches:

- Correctly handles nested functions, decorators, and complex syntax
- Supports multiple languages via grammar packages
- Falls back gracefully to regex when tree-sitter not available

Usage:
    pip install specbridge[ast]
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from specbridge.discovery.code import FuncBlock

_TS_AVAILABLE = False
_TS_PYTHON = None

try:
    import tree_sitter_python as _ts_python  # type: ignore[import-not-found]
    from tree_sitter import Language, Parser  # type: ignore[import-not-found]

    _TS_AVAILABLE = True
    _TS_PYTHON = Language(_ts_python.language())
except ImportError:
    pass


def is_available() -> bool:
    """Check if tree-sitter and language grammars are installed."""
    return _TS_AVAILABLE


def extract_functions_python(file_path: str | Path) -> list[FuncBlock]:
    """Extract function/class definitions from Python using tree-sitter.

    Falls back to regex-based extraction if tree-sitter not available.
    """
    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    if not _TS_AVAILABLE:
        return _extract_functions_regex_fallback(text)

    parser = Parser(_TS_PYTHON)
    tree = parser.parse(bytes(text, "utf-8"))
    blocks: list[FuncBlock] = []
    lines = text.split("\n")

    _walk_python_tree(tree.root_node, text, lines, blocks)
    return blocks


def _walk_python_tree(
    node: object,
    text: str,
    lines: list[str],
    blocks: list[FuncBlock],
    depth: int = 0,
) -> None:
    """Recursively walk the tree-sitter AST for Python function/class definitions."""
    if depth > 200:
        return

    ntype = getattr(node, "type", "")

    if ntype in ("function_definition", "class_definition", "decorated_definition"):
        def_node = node
        if ntype == "decorated_definition":
            for child in getattr(node, "children", []):
                if getattr(child, "type", "") in ("function_definition", "class_definition"):
                    def_node = child
                    break

        name_node = _find_child(def_node, "name") or _find_child(def_node, "identifier")
        if name_node is None:
            pass
        else:
            text_bytes = text.encode("utf-8")
            body_text = text_bytes[
                getattr(node, "start_byte", 0):getattr(node, "end_byte", 0)
            ].decode("utf-8", errors="replace")
            body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()[:16]
            blines = body_text.count("\n") + 1
            preview = body_text.strip()[:80].replace("\n", " ")
            start = getattr(node, "start_point", (0, 0))
            line = start[0] + 1 if isinstance(start, tuple) else getattr(start, "row", 0) + 1
            name = _get_node_text(name_node, text)

            blocks.append(FuncBlock(
                name=name,
                kind="class" if ntype == "class_definition" else "function",
                line=line,
                body_hash=body_hash,
                body_lines=blines,
                body_preview=preview,
            ))

    for child in getattr(node, "children", []):
        _walk_python_tree(child, text, lines, blocks, depth + 1)


def _get_node_text(node: object, text: str) -> str:
    """Extract text from a tree-sitter node using byte offsets."""
    text_bytes = text.encode("utf-8")
    return text_bytes[
        getattr(node, "start_byte", 0):getattr(node, "end_byte", 0)
    ].decode("utf-8", errors="replace")


def _find_child(node: object, field_name: str) -> object | None:
    """Find a child node by type name."""
    for child in getattr(node, "children", []):
        if getattr(child, "type", "") == field_name:
            return child  # type: ignore[no-any-return]
        field = getattr(child, "field_name", None)
        if field is not None and field == field_name:
            return child  # type: ignore[no-any-return]
    return None


def _extract_functions_regex_fallback(text: str) -> list[FuncBlock]:
    """Fallback: use the existing regex-based extraction logic."""
    from specbridge.discovery.code import _extract_func_blocks

    lines = text.split("\n")
    return _extract_func_blocks(text, lines)
