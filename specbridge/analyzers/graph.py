"""Code dependency graph — build code→code edges from import statements."""

from __future__ import annotations

from pathlib import Path

from specbridge.core import NodeType, TraceGraph


def build_code_dependency_graph(graph: TraceGraph, project_dir: str) -> None:
    """Add DEPENDS edges to the graph based on import analysis.

    Iterates over all CODE nodes and their import lists,
    then creates DEPENDS edges when one file imports another.

    Args:
        graph: TraceGraph to add dependency edges to (mutated in place).
        project_dir: Project root for resolving relative imports.
    """
    root = Path(project_dir).resolve()

    # Build a lookup: filename → node id
    # (e.g. "src/auth/login.py" → "src/auth/login.py")
    # Also build stem→node mapping for import resolution
    code_nodes = {n.source.file: (nid, n) for nid, n in graph.nodes.items()
                  if n.type in (NodeType.CODE, NodeType.TEST)}

    stem_to_file: dict[str, list[str]] = {}
    for filepath in code_nodes:
        stem = Path(filepath).stem
        stem_to_file.setdefault(stem, []).append(filepath)

    for filepath, (nid, node) in code_nodes.items():
        imports = node.metadata.get("imports", [])
        for imp in imports:
            # Try matching import paths to files
            target = _resolve_import(imp, filepath, root, code_nodes, stem_to_file)
            if target:
                _add_depends_edge(graph, nid, target)


def _resolve_import(
    imp: str,
    source_file: str,
    root: Path,
    code_nodes: dict[str, tuple[str, object]],
    stem_to_file: dict[str, list[str]],
) -> str | None:
    """Resolve an import string to a file path in the project.

    Resolution strategies:
    1. Exact file path match (e.g. "src/auth/login" → "src/auth/login.py")
    2. Module → file mapping (e.g. "auth.login" → "src/auth/login.py")
    3. Stem match (e.g. "login" → "src/auth/login.py")
    """
    source_dir = Path(source_file).parent

    # Strategy 1: Try common source root prefixes
    for prefix in ["src", "lib", "app"]:
        # If the import already starts with the prefix, try it directly
        if imp.startswith(prefix):
            candidate = f"{imp.replace('.', '/')}.py"
            if candidate in code_nodes:
                return candidate
            dir_path = f"{imp.replace('.', '/')}/__init__.py"
            if dir_path in code_nodes:
                return dir_path

        # Otherwise prepend the prefix
        candidate = f"{prefix}/{imp.replace('.', '/')}.py"
        if candidate in code_nodes:
            return candidate
        dir_path = f"{prefix}/{imp.replace('.', '/')}/__init__.py"
        if dir_path in code_nodes:
            return dir_path

    # Strategy 2: Relative to source file directory
    for _ in ["src", "lib", "app"]:
        relative = source_dir / imp.replace(".", "/")
        for ext in [".py", ".ts", ".js", ".go", ".rs", ".java"]:
            candidate = str(relative.with_suffix(ext))
            if candidate in code_nodes:
                return candidate

    # Strategy 3: Stem-based lookup for short names
    stem = imp.split(".")[-1]
    if stem in stem_to_file:
        candidates = stem_to_file[stem]
        # Pick the one with the most overlap in parent path
        if len(candidates) == 1:
            return candidates[0]
        # Multi-match: prefer one in same directory
        for c in candidates:
            if Path(c).parent == source_dir:
                return c
        return candidates[0]

    return None


def _add_depends_edge(graph: TraceGraph, src_id: str, dst_id: str) -> None:
    """Add a DEPENDS edge if it doesn't exist yet."""
    from specbridge.core import EdgeRelation, EdgeStrength, Evidence, SourceRef, TraceEdge

    existing = {(e.src_id, e.dst_id, e.relation.value) for e in graph.edges}
    if (src_id, dst_id, "depends") in existing:
        return

    graph.edges.append(TraceEdge(
        src_id=src_id,
        dst_id=dst_id,
        relation=EdgeRelation.DEPENDS,
        strength=EdgeStrength.INFERRED,
        evidence=[Evidence(
            kind="import_graph",
            value=f"{src_id} imports {dst_id}",
            source=SourceRef(file=src_id),
        )],
    ))
