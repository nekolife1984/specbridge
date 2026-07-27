"""Tree-sitter AST-based code analysis (optional enhancement).

When tree-sitter is available, provides more accurate function/class
extraction compared to regex-based approaches:

- Correctly handles nested functions, decorators, and complex syntax
- Supports multiple languages via grammar packages
- Falls back gracefully to regex when tree-sitter not available

Supported languages:
  - Python  (via ``tree-sitter-python``)
  - TypeScript / JavaScript  (via ``tree-sitter-typescript``)
  - Go       (via ``tree-sitter-go``)
  - Rust     (via ``tree-sitter-rust``)

Usage:
    pip install specbridge[ast]
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from specbridge.discovery.code import FuncBlock

# ---------------------------------------------------------------------------
# Lazy tree-sitter imports (import errors → graceful fallback)
# ---------------------------------------------------------------------------

_TS_AVAILABLE = False
_TS_PYTHON = None
_TS_TYPESCRIPT = None
_TS_TSX = None
_TS_GO = None
_TS_RUST = None

try:
    import tree_sitter_go as _ts_go_mod
    import tree_sitter_python as _ts_python_mod
    import tree_sitter_rust as _ts_rust_mod
    import tree_sitter_typescript as _ts_ts_mod
    from tree_sitter import Language, Parser

    _TS_PYTHON = Language(_ts_python_mod.language())
    _TS_TYPESCRIPT = Language(_ts_ts_mod.language_typescript())
    _TS_TSX = Language(_ts_ts_mod.language_tsx())
    _TS_GO = Language(_ts_go_mod.language())
    _TS_RUST = Language(_ts_rust_mod.language())
    _TS_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Language support map
# ---------------------------------------------------------------------------

TS_LANGUAGE_MAP: dict[str, str] = {
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "typescript",   # TypeScript grammar handles JS too
    ".jsx": "tsx",
    ".mjs": "typescript",
    ".cjs": "typescript",
}

# Rust node types that count as "definitions"
_RUST_DEF_KINDS: dict[str, str] = {
    "function_item": "function",
    "struct_item": "class",
    "enum_item": "class",
    "trait_item": "class",
    "impl_item": "class",
    "type_item": "class",
    "const_item": "function",
}

# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """Check if tree-sitter and language grammars are installed."""
    return _TS_AVAILABLE


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def extract_functions(file_path: str | Path) -> list[FuncBlock]:
    """Auto-dispatch to the correct language parser based on file extension.

    Falls back to regex-based extraction when tree-sitter is not available
    or the language grammar is not installed.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".py":
        return extract_functions_python(file_path)
    if ext in TS_LANGUAGE_MAP:
        return extract_functions_typescript(file_path)
    if ext == ".go":
        return extract_functions_go(file_path)
    if ext == ".rs":
        return extract_functions_rust(file_path)

    # Unknown extension — use regex fallback
    try:
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        from specbridge.discovery.code import _extract_func_blocks
        return _extract_func_blocks(text, lines)
    except Exception:
        return []


def extract_functions_python(file_path: str | Path) -> list[FuncBlock]:
    """Extract function/class definitions from Python using tree-sitter.

    Falls back to regex-based extraction if tree-sitter not available.
    """
    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    if not _TS_AVAILABLE or _TS_PYTHON is None:
        return _extract_functions_regex_fallback(text)

    parser = Parser(_TS_PYTHON)
    tree = parser.parse(bytes(text, "utf-8"))
    blocks: list[FuncBlock] = []
    lines = text.split("\n")
    _walk_python_tree(tree.root_node, text, lines, blocks)
    return blocks


def extract_functions_typescript(file_path: str | Path) -> list[FuncBlock]:
    """Extract function/class definitions from TypeScript/JavaScript.

    Falls back to regex-based extraction if tree-sitter not available.
    """
    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    if not _TS_AVAILABLE:
        return _extract_functions_regex_fallback(text)

    ext = path.suffix.lower()
    lang = TS_LANGUAGE_MAP.get(ext, "typescript")
    if lang == "tsx" and _TS_TSX is not None:
        grammar = _TS_TSX
    elif _TS_TYPESCRIPT is not None:
        grammar = _TS_TYPESCRIPT
    else:
        return _extract_functions_regex_fallback(text)

    parser = Parser(grammar)
    tree = parser.parse(bytes(text, "utf-8"))
    blocks: list[FuncBlock] = []
    lines = text.split("\n")
    _walk_ts_typescript_tree(tree.root_node, text, lines, blocks)
    return blocks


def extract_functions_go(file_path: str | Path) -> list[FuncBlock]:
    """Extract function/method definitions from Go.

    Falls back to regex-based extraction if tree-sitter not available.
    """
    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    if not _TS_AVAILABLE or _TS_GO is None:
        return _extract_functions_regex_fallback(text)

    parser = Parser(_TS_GO)
    tree = parser.parse(bytes(text, "utf-8"))
    blocks: list[FuncBlock] = []
    lines = text.split("\n")
    _walk_ts_go_tree(tree.root_node, text, lines, blocks)
    return blocks


def extract_functions_rust(file_path: str | Path) -> list[FuncBlock]:
    """Extract function/struct/enum/trait definitions from Rust.

    Falls back to regex-based extraction if tree-sitter not available.
    """
    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    if not _TS_AVAILABLE or _TS_RUST is None:
        return _extract_functions_regex_fallback(text)

    parser = Parser(_TS_RUST)
    tree = parser.parse(bytes(text, "utf-8"))
    blocks: list[FuncBlock] = []
    lines = text.split("\n")
    _walk_ts_rust_tree(tree.root_node, text, lines, blocks)
    return blocks


# ---------------------------------------------------------------------------
# Python AST walker
# ---------------------------------------------------------------------------


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
            kind = "class" if ntype == "class_definition" else "function"

            blocks.append(FuncBlock(
                name=name,
                kind=kind,
                line=line,
                body_hash=body_hash,
                body_lines=blines,
                body_preview=preview,
            ))

    for child in getattr(node, "children", []):
        _walk_python_tree(child, text, lines, blocks, depth + 1)


# ---------------------------------------------------------------------------
# TypeScript / JavaScript AST walker
# ---------------------------------------------------------------------------


def _walk_ts_typescript_tree(
    node: object,
    text: str,
    lines: list[str],
    blocks: list[FuncBlock],
    depth: int = 0,
) -> None:
    """Recursively walk the tree-sitter AST for TypeScript/JS definitions."""
    if depth > 200:
        return

    ntype = getattr(node, "type", "")

    _extract_ts_def(node, ntype, text, blocks)

    # Handle arrow functions in const/let declarations
    if ntype == "lexical_declaration":
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "variable_declarator":
                # Check for arrow_function or function in the value
                for grandchild in getattr(child, "children", []):
                    if getattr(grandchild, "type", "") == "arrow_function":
                        _extract_ts_arrow(grandchild, child, text, blocks)
                    elif getattr(grandchild, "type", "") == "function":
                        _extract_ts_def(grandchild, "function", text, blocks)

    for child in getattr(node, "children", []):
        _walk_ts_typescript_tree(child, text, lines, blocks, depth + 1)


def _extract_ts_def(
    node: object,
    ntype: str,
    text: str,
    blocks: list[FuncBlock],
) -> None:
    """Extract a named function/class definition from a TS/JS AST node."""
    if ntype not in ("function_declaration", "class_declaration", "method_definition", "function", "generator_function_declaration"):
        return

    # TS/JS uses different identifier node types depending on context:
    #   function_declaration → identifier
    #   class_declaration    → type_identifier
    #   method_definition    → property_identifier
    name_node = _find_child_by_types(node, ("identifier", "type_identifier", "property_identifier"))
    if name_node is None:
        return

    name = _get_node_text(name_node, text)
    kind = "class" if ntype == "class_declaration" else "function"
    _append_block(node, name, kind, text, blocks)


def _extract_ts_arrow(
    arrow_node: object,
    declarator_node: object,
    text: str,
    blocks: list[FuncBlock],
) -> None:
    """Extract a named arrow function assigned to a variable."""
    name_node = _find_child_by_types(declarator_node, ("identifier",))
    if name_node is None:
        return

    name = _get_node_text(name_node, text)
    # The whole declaration is "const foo = (...) => {...}"
    # We use the declarator node for the body text scope
    _append_block(declarator_node, name, "function", text, blocks)


# ---------------------------------------------------------------------------
# Go AST walker
# ---------------------------------------------------------------------------


def _walk_ts_go_tree(
    node: object,
    text: str,
    lines: list[str],
    blocks: list[FuncBlock],
    depth: int = 0,
) -> None:
    """Recursively walk the tree-sitter AST for Go function/method definitions."""
    if depth > 200:
        return

    ntype = getattr(node, "type", "")

    if ntype in ("function_declaration", "method_declaration"):
        # Go: function_declaration name → identifier, method_declaration name → field_identifier
        name_node = _find_child_by_types(node, ("identifier", "field_identifier"))
        if name_node is None:
            pass
        else:
            name = _get_node_text(name_node, text)
            _append_block(node, name, "function", text, blocks)

    for child in getattr(node, "children", []):
        _walk_ts_go_tree(child, text, lines, blocks, depth + 1)


# ---------------------------------------------------------------------------
# Rust AST walker
# ---------------------------------------------------------------------------


def _walk_ts_rust_tree(
    node: object,
    text: str,
    lines: list[str],
    blocks: list[FuncBlock],
    depth: int = 0,
) -> None:
    """Recursively walk the tree-sitter AST for Rust definitions."""
    if depth > 200:
        return

    ntype = getattr(node, "type", "")

    if ntype in _RUST_DEF_KINDS:
        kind = _RUST_DEF_KINDS[ntype]
        # Rust: function_item name → identifier, struct_item etc. → type_identifier
        name_node = _find_child_by_types(node, ("identifier", "type_identifier"))
        # impl_item: try the type_identifier (the type being implemented)
        if name_node is None and ntype == "impl_item":
            for child in getattr(node, "children", []):
                if getattr(child, "type", "") == "type_identifier":
                    name_node = child
                    break

        if name_node is None:
            pass
        else:
            name = _get_node_text(name_node, text)
            # For impl_item, prefix with "impl " to distinguish from struct
            if ntype == "impl_item":
                name = f"impl {name}"
            _append_block(node, name, kind, text, blocks)

    for child in getattr(node, "children", []):
        _walk_ts_rust_tree(child, text, lines, blocks, depth + 1)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _append_block(
    node: object,
    name: str,
    kind: str,
    text: str,
    blocks: list[FuncBlock],
) -> None:
    """Extract a FuncBlock from a tree-sitter node and append it."""
    text_bytes = text.encode("utf-8")
    body_text = text_bytes[
        getattr(node, "start_byte", 0):getattr(node, "end_byte", 0)
    ].decode("utf-8", errors="replace")
    body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()[:16]
    blines = body_text.count("\n") + 1
    preview = body_text.strip()[:80].replace("\n", " ")
    start = getattr(node, "start_point", (0, 0))
    line = start[0] + 1 if isinstance(start, tuple) else getattr(start, "row", 0) + 1

    blocks.append(FuncBlock(
        name=name,
        kind=kind,
        line=line,
        body_hash=body_hash,
        body_lines=blines,
        body_preview=preview,
    ))


def _get_node_text(node: object, text: str) -> str:
    """Extract text from a tree-sitter node using byte offsets."""
    text_bytes = text.encode("utf-8")
    return text_bytes[
        getattr(node, "start_byte", 0):getattr(node, "end_byte", 0)
    ].decode("utf-8", errors="replace")


def _find_child(node: object, field_name: str) -> object | None:
    """Find a child node by type name or field name."""
    for child in getattr(node, "children", []):
        if getattr(child, "type", "") == field_name:
            return child  # type: ignore[no-any-return]
        field = getattr(child, "field_name", None)
        if field is not None and field == field_name:
            return child  # type: ignore[no-any-return]
    return None


def _find_child_by_types(node: object, type_names: tuple[str, ...]) -> object | None:
    """Find the first child node matching one of the given type names.

    Checks children by their ``type`` attribute (not ``field_name``).
    Some tree-sitter grammars (e.g. Python, Rust 0.24+) set ``field_name`` on
    named children, while others (TypeScript, Go) only set ``type`` — so
    this helper only matches on ``type`` to stay grammar-agnostic.
    """
    for child in getattr(node, "children", []):
        if getattr(child, "type", "") in type_names:
            return child  # type: ignore[no-any-return]
    return None


def _extract_functions_regex_fallback(text: str) -> list[FuncBlock]:
    """Fallback: use the existing regex-based extraction logic."""
    from specbridge.discovery.code import _extract_func_blocks

    lines = text.split("\n")
    return _extract_func_blocks(text, lines)
