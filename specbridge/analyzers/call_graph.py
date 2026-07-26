"""Call-graph analysis for transitive (indirect) impact.

Provides two modes:
1. **Lightweight** — regex-based function call detection (17 languages, no deps)
2. **CRG import** — reads ``code-review-graph`` JSON output for AST-precise graphs

The call graph is used for **transitive impact analysis**: if spec X is
implemented by ``auth/login.py::login_user()`` and ``login_user()`` calls
``db/user_repo.py::get_user()``, then changes to ``get_user()`` also
indirectly impact spec X.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specbridge.core import NodeType, TraceGraph


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CallGraphNode:
    """A function that appears in the call graph."""
    name: str                         # e.g. "login_user"
    file: str                         # relative path, e.g. "src/auth/login.py"
    language: str = ""                # "Python", "TypeScript", etc.


@dataclass
class CallGraph:
    """Function-level call graph.

    ``nodes`` maps ``f"{file}::{name}"`` to a ``CallGraphNode``.
    ``edges`` is a list of ``(caller_key, callee_key)`` tuples.
    """
    nodes: dict[str, CallGraphNode] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def add_call(self, caller_key: str, callee_key: str) -> None:
        if (caller_key, callee_key) not in self.edges:
            self.edges.append((caller_key, callee_key))

    def callees_of(self, key: str) -> list[str]:
        """Return all functions directly called by *key*."""
        return [callee for caller, callee in self.edges if caller == key]

    def callers_of(self, key: str) -> list[str]:
        """Return all functions that call *key*."""
        return [caller for caller, callee in self.edges if callee == key]

    def files_of(self, keys: list[str]) -> list[str]:
        """Return unique file paths for the given node keys."""
        seen: set[str] = set()
        files: list[str] = []
        for k in keys:
            node = self.nodes.get(k)
            if node and node.file not in seen:
                seen.add(node.file)
                files.append(node.file)
        return files


# ---------------------------------------------------------------------------
# Lightweight call-graph builder (regex-based, 17 languages)
# ---------------------------------------------------------------------------

# Function-call regex: matches name( ... ) — the name must be a valid identifier
_RE_CALL = re.compile(r"(?:^|[.\s{(,;!?&|:~=])([A-Za-z_]\w*)\s*\(")

# Languages to skip (built-in / stdlib names to filter out)
_STDLIB_LIKE = frozenset({
    "print", "len", "str", "int", "float", "list", "dict", "set", "tuple",
    "type", "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "open", "input", "isinstance", "hasattr", "getattr", "setattr",
    "require", "describe", "it", "expect", "assert",
    "console", "process", "Buffer", "module", "exports",
    "fmt", "log", "error", "panic", "recover", "make", "new", "append", "copy",
    "close", "delete", "println", "printf", "sprintf",
    "Some", "None", "Ok", "Err", "Box", "Rc", "Arc", "Mutex",
    "unwrap", "expect", "clone", "into", "from", "as_ref",
    "to_string", "to_owned", "collect", "iter", "into_iter",
    "map", "and_then", "or_else", "filter", "fold",
    "String", "Vec", "HashMap", "Option", "Result",
})


def build_call_graph(graph: TraceGraph, project_dir: str) -> CallGraph:
    """Build a lightweight call graph from function definitions and call sites.

    Scans source files referenced in the trace graph for function calls,
    building a ``CallGraph`` that can be used for transitive impact analysis.

    Args:
        graph: TraceGraph containing function-level CODE nodes.
        project_dir: Project root for resolving file paths.

    Returns:
        A ``CallGraph`` instance (may be empty if no function nodes exist).
    """
    cg = CallGraph()

    # Step 1: Collect all known function definitions from the trace graph
    # Function-level nodes have "::" in their ID, e.g. "src/auth/login.py::login_user"
    known_functions: dict[str, set[str]] = {}  # file → {func_name, ...}
    for nid, node in graph.nodes.items():
        if node.type not in (NodeType.CODE, NodeType.TEST):
            continue
        if "::" in nid:
            # Function-level node: nid = "file/path.py::func_name"
            parts = nid.split("::", 1)
            fpath, fname = parts[0], parts[1]
            known_functions.setdefault(fpath, set()).add(fname)
            cg.nodes[nid] = CallGraphNode(name=fname, file=fpath)

    if not known_functions:
        return cg

    # Step 2: Scan source files for function calls
    root = Path(project_dir).resolve()

    for fpath, funcs in known_functions.items():
        full_path = root / fpath
        if not full_path.exists():
            continue
        try:
            text = full_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Collect function names defined in this file as potential callees
        local_funcs = set(funcs)

        # Find all call sites
        calls_found = _find_calls(text)

        for called_name in calls_found:
            if called_name in _STDLIB_LIKE:
                continue
            if called_name == "__init__":
                continue

            # Resolve the called function to a file
            callee_key = _resolve_callee(called_name, fpath, known_functions, cg)
            if callee_key:
                for local_func in local_funcs:
                    caller_key = f"{fpath}::{local_func}"
                    cg.add_call(caller_key, callee_key)

    return cg


def _find_calls(text: str) -> set[str]:
    """Extract function call names from source text (deduplicated)."""
    names: set[str] = set()
    for m in _RE_CALL.finditer(text):
        name = m.group(1)
        # Skip method calls (obj.method), decorators (@decorator), import-like
        if len(name) > 1 and name[0].isupper():
            continue  # Likely a class constructor
        if name in ("if", "for", "while", "with", "switch", "catch", "elif", "else"):
            continue
        names.add(name)
    return names


def _resolve_callee(
    name: str,
    caller_file: str,
    known_functions: dict[str, set[str]],
    cg: CallGraph,
) -> str | None:
    """Resolve a function call to a ``CallGraph`` node key.

    Resolution order:
    1. Same file (local function call)
    2. Another file with a function of that name
    3. Fallback: create a synthetic node for unknown external calls
    """
    # 1. Check same file first
    caller_dir = Path(caller_file).parent
    if name in known_functions.get(caller_file, set()):
        return f"{caller_file}::{name}"

    # 2. Check other files
    candidates: list[str] = []
    for fpath, funcs in known_functions.items():
        if name in funcs:
            candidates.append(fpath)

    if len(candidates) == 1:
        return f"{candidates[0]}::{name}"

    if len(candidates) > 1:
        # Prefer file in same directory
        for c in candidates:
            if Path(c).parent == caller_dir:
                return f"{c}::{name}"
        return f"{candidates[0]}::{name}"

    return None


# ---------------------------------------------------------------------------
# CRG JSON importer (for external code-review-graph tool)
# ---------------------------------------------------------------------------


def import_crg_json(crg_path: str) -> CallGraph:
    """Import a ``CallGraph`` from ``code-review-graph`` JSON output.

    The CRG tool produces JSON with list of symbols and their relationships.
    Expected shape::

        [
            {"symbol": "login_user", "file": "src/auth/login.py",
             "callers": [...], "callees": [...], "importers": [...]},
            ...
        ]
    """
    cg = CallGraph()
    try:
        with open(crg_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[CRG] Error reading {crg_path}: {e}", file=sys.stderr)
        return cg

    if isinstance(data, dict):
        data = data.get("symbols", data.get("results", [data]))

    for entry in data if isinstance(data, list) else []:
        symbol = entry.get("symbol", entry.get("name", ""))
        filepath = entry.get("file", entry.get("filepath", ""))
        if not symbol or not filepath:
            continue

        key = f"{filepath}::{symbol}"
        cg.nodes[key] = CallGraphNode(name=symbol, file=filepath)

        for callee in entry.get("callees", entry.get("calls", [])):
            # CRG may return bare names or full keys; resolve to node key
            resolved = _resolve_crg_ref(callee, cg)
            if resolved:
                cg.add_call(key, resolved)

        for caller in entry.get("callers", entry.get("called_by", [])):
            resolved = _resolve_crg_ref(caller, cg)
            if resolved:
                cg.add_call(resolved, key)

    return cg


def _resolve_crg_ref(ref: str, cg: CallGraph) -> str | None:
    """Resolve a CRG reference (bare name or key) to a call-graph node key.

    Resolution order:
    1. Exact key match (e.g. ``src/auth.py::login``)
    2. Bare name match (e.g. ``login`` → ``src/auth.py::login``)
    """
    if ref in cg.nodes:
        return ref
    # Try bare name match
    candidates = [k for k in cg.nodes if k.endswith(f"::{ref}")]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return candidates[0]  # Ambiguous but better than nothing
    return None


def run_crg_tool(project_dir: str) -> CallGraph | None:
    """Run the ``code-review-graph`` tool and import its output.

    Returns ``None`` if the tool is not installed or fails.
    """
    try:
        result = subprocess.run(
            ["code-review-graph", "query", "--all", "--json"],
            capture_output=True, text=True, timeout=120,
            cwd=project_dir,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        # Convert to our format and import
        import tempfile
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(json.dumps(data))
        cg = import_crg_json(str(tmp))
        tmp.unlink()
        return cg
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Transitive impact analysis
# ---------------------------------------------------------------------------


def transitive_impact(
    graph: TraceGraph,
    call_graph: CallGraph,
    spec_node_id: str,
    *,
    max_depth: int = 3,
) -> dict[str, Any]:
    """Analyze the transitive (indirect) impact of changes to a spec.

    For a given spec, finds:
    - **Direct**: files with ``@impl`` / ``@verifies`` edges to the spec
    - **Transitive**: files called by those direct files (up to *max_depth* hops)

    Returns a dict with keys:
    - ``spec_id``: the spec ID
    - ``direct_files``: file paths of direct implementers
    - ``transitive_files``: file paths of indirect (impacted) files
    - ``transitive_edges``: list of ``(caller, callee)`` call-graph edges traversed
    - ``hops``: max depth reached during traversal
    """
    spec_nodes = [n for nid, n in graph.nodes.items()
                  if n.type == NodeType.SPEC and (nid == spec_node_id or nid.endswith(f".{spec_node_id}"))]

    result: dict[str, Any] = {
        "spec_id": spec_node_id,
        "direct_files": [],
        "transitive_files": [],
        "transitive_edges": [],
        "hops": 0,
    }

    if not spec_nodes or not call_graph.nodes:
        return result

    # Get direct implementers
    direct_keys: set[str] = set()
    for spec_node in spec_nodes:
        for edge in graph.edges_to(spec_node.id):
            src = graph.nodes.get(edge.src_id)
            if src and src.source.file:
                if "::" in edge.src_id:
                    direct_keys.add(edge.src_id)
                else:
                    # File-level node: add all functions in that file
                    for cg_key, cg_node in call_graph.nodes.items():
                        if cg_node.file == src.source.file:
                            direct_keys.add(cg_key)

    # BFS for transitive calls
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(k, 0) for k in direct_keys]
    transitive_edges: list[tuple[str, str]] = []
    max_hops = 0

    while queue:
        current_key, depth = queue.pop(0)
        if current_key in visited or depth > max_depth:
            continue
        visited.add(current_key)
        max_hops = max(max_hops, depth)

        for callee_key in call_graph.callees_of(current_key):
            if callee_key not in visited:
                transitive_edges.append((current_key, callee_key))
                queue.append((callee_key, depth + 1))

    direct_files = call_graph.files_of(list(direct_keys))
    # Transitive = visited minus direct
    transitive_keys = [k for k in visited if k not in direct_keys]

    result["direct_files"] = sorted(set(direct_files))
    result["transitive_files"] = sorted(set(call_graph.files_of(transitive_keys)))
    result["transitive_edges"] = [(c, l) for c, l in transitive_edges]
    result["hops"] = max_hops

    return result
