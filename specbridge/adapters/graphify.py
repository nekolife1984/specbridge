"""Graphify adapter: uses graphify's AST parsing for a deeper code graph.

This adapter shells out to `graphify extract . --code-only` to build a
deterministic tree-sitter AST graph of the codebase (functions, classes,
calls, imports) and maps it into specbridge's TraceGraph format.

Unlike the heuristic adapter which relies on regex-based symbol extraction,
graphify uses proper tree-sitter grammars for 15+ languages, producing a
more complete and accurate code graph with call-graph edges.

Requires: ``graphify`` CLI installed (``pipx install graphifyy``).

.. note::

   ``pip install specbridge[graphify]`` only ensures the adapter is
   importable; you still need ``pipx install graphifyy`` at the system
   level for the CLI that this adapter shells out to.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from specbridge.adapters._base import ProjectAdapter, register
from specbridge.core import (
    EdgeRelation,
    EdgeStrength,
    Evidence,
    NodeType,
    SourceRef,
    TraceEdge,
    TraceGraph,
    TraceNode,
)


@register
class GraphifyAdapter(ProjectAdapter):
    """Use graphify CLI to produce a deep AST-based code graph.

    Confidence:
      - 0.9 if ``graphify`` is on PATH and a graphify-out/ already exists
        (fast path — skip re-extraction).
      - 0.7 if ``graphify`` is on PATH but needs to run extraction
        (first run or stale cache).
      - 0.0 if ``graphify`` is not installed.

    .. note::

       The detect score is intentionally lower than HeuristicAdapter and
       SpectraAdapter so that GraphifyAdapter is **never** selected as the
       sole adapter in single-adapter mode (``analyze``, ``coverage``).
       It provides value only in ``--merge`` mode where all adapters
       contribute their nodes and edges.  In single mode it would produce
       a graph with code nodes but no spec nodes, yielding 0% coverage.
    """

    _GRAPHFIFY_OUT = "graphify-out"
    _GRAPHFIFY_JSON = "graphify-out/graph.json"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def detect(self, directory: str) -> float:
        root = Path(directory).resolve()

        # Is graphify CLI available?
        if not self._graphify_available():
            return 0.0

        # Quick sanity check: does the directory have any source files?
        # (Avoid matching empty or non-project directories just because
        #  graphify happens to be installed.)
        def _has_files(path: Path, pattern: str) -> bool:
            return any(True for _ in path.rglob(pattern))

        has_source = any(
            _has_files(root, f"*{ext}")
            for ext in [".py", ".ts", ".js", ".go", ".rs", ".java", ".c", ".cpp", ".rb"]
        )

        if not has_source:
            return 0.0

        graph_json = root / self._GRAPHFIFY_JSON
        if graph_json.exists():
            return 0.25  # already indexed (fast path, but below heuristic/spectra)
        return 0.15  # needs indexing (below heuristic's 0.4)

    def analyze(self, directory: str) -> TraceGraph:
        root = Path(directory).resolve()
        graph = TraceGraph()

        # 1. Ensure graphify output exists
        graph_json = root / self._GRAPHFIFY_JSON
        if not graph_json.exists():
            self._run_graphify(directory)

        # 2. Re-read (in case of concurrent writes)
        if not graph_json.exists():
            print("[graphify] graphify-out/graph.json not found — running graphify", file=sys.stderr)
            self._run_graphify(directory)

        # 3. Parse graphify output
        with open(graph_json) as f:
            gdata = json.load(f)

        # 3a. Convert code nodes
        for gnode in gdata.get("nodes", []):
            nid = self._graphify_id(gnode)
            src_file = gnode.get("source_file", "")
            rel_file = self._rel_path(root, src_file) if src_file else ""
            label = gnode.get("label", nid)
            gtype = gnode.get("type", "")

            # Skip non-code entries (packages, directories)
            if gtype == "package":
                continue

            node = TraceNode(
                id=nid,
                type=NodeType.CODE,
                title=label,
                source=SourceRef(file=rel_file, label=label),
                framework_origin="graphify",
                confidence=0.9,
                metadata={
                    "graphify_type": gtype,
                    "source_file": src_file,
                    "source_location": gnode.get("source_location"),
                },
            )
            graph.add_node(node)

        # 3b. Convert edges to TraceEdges
        relation_map = {
            "calls": EdgeRelation.REFERENCES,
            "imports": EdgeRelation.DEPENDS,
            "extends": EdgeRelation.REFERENCES,
            "implements": EdgeRelation.IMPLEMENTS,
            "references": EdgeRelation.REFERENCES,
            "imports_from": EdgeRelation.DEPENDS,
        }

        for gedge in gdata.get("links", []):
            src = gedge.get("source", "")
            tgt = gedge.get("target", "")
            relation_str = gedge.get("relation", "references")
            confidence = gedge.get("confidence", "EXTRACTED")

            if not src or not tgt:
                continue

            relation = relation_map.get(relation_str, EdgeRelation.REFERENCES)
            strength = EdgeStrength.EXPLICIT if confidence == "EXTRACTED" else EdgeStrength.INFERRED

            graph.add_edge(TraceEdge(
                src_id=src,
                dst_id=tgt,
                relation=relation,
                strength=strength,
                evidence=[
                    Evidence(
                        kind=f"graphify:{relation_str}",
                        value=f"graphify {relation_str} edge ({confidence})",
                        source=SourceRef(file=""),
                    ),
                ],
            ))

        # 4. Add community metadata if available
        analysis_file = root / "graphify-out" / ".graphify_analysis.json"
        if analysis_file.exists():
            try:
                with open(analysis_file) as f:
                    analysis = json.load(f)
                communities = analysis.get("community_labels", {})
                # Store as graph-level metadata (nice-to-have; skip on error)
                try:
                    graph.metadata = {}  # type: ignore[attr-defined]
                    graph.metadata["graphify_communities"] = communities  # type: ignore[attr-defined]
                except AttributeError:
                    pass
            except Exception:
                pass

        return graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _graphify_available() -> bool:
        """Check if graphify CLI is available on PATH (including ~/.local/bin)."""
        import shutil
        if shutil.which("graphify"):
            return True
        # Also check ~/.local/bin (common pipx install location)
        local_bin = Path.home() / ".local" / "bin" / "graphify"
        return local_bin.is_file()

    @staticmethod
    def _run_graphify(directory: str) -> None:
        """Run ``graphify extract . --code-only`` in the project directory."""
        import shutil
        graphify_path = shutil.which("graphify") or str(
            Path.home() / ".local" / "bin" / "graphify"
        )
        try:
            subprocess.run(
                [graphify_path, "extract", ".", "--code-only"],
                cwd=directory,
                capture_output=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            print("[graphify] graphify extract timed out after 300s", file=sys.stderr)
        except FileNotFoundError:
            print(f"[graphify] graphify CLI not found ({graphify_path})", file=sys.stderr)

    @staticmethod
    def _graphify_id(gnode: dict[str, Any]) -> str:
        """Return a stable ID from a graphify node."""
        nid: str = gnode.get("id", "")
        if nid:
            return nid
        # Fallback: construct from file + label
        src = gnode.get("source_file", "unknown")
        label = gnode.get("label", "unknown")
        return f"{src}::{label}"

    @staticmethod
    def _rel_path(root: Path, abs_path: str) -> str:
        try:
            return str(Path(abs_path).relative_to(root))
        except (ValueError, RuntimeError):
            return abs_path
