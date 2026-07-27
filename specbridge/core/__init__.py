"""
specbridge core model: framework-agnostic traceability primitives.

A TraceNode is anything traceable (spec, design, code file, test, task).
A TraceEdge is a directed relationship between two nodes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    SPEC = "spec"
    DESIGN = "design"
    CODE = "code"
    TEST = "test"
    TASK = "task"


class EdgeRelation(str, Enum):
    SATISFIES = "satisfies"          # design → spec
    IMPLEMENTS = "implements"        # code → spec
    VERIFIES = "verifies"            # test → spec
    DEPENDS = "depends"             # task → task
    REFERENCES = "references"        # catch-all


class EdgeStrength(str, Enum):
    EXPLICIT = "explicit"            # from a concrete tag, e.g. @impl, @verifies
    INFERRED = "inferred"            # from AST / heuristics
    WEAK = "weak"                   # speculative (filename match, etc.)


@dataclass
class SourceRef:
    """Points to the physical location of a traceable element."""
    file: str                        # relative path from project root
    line: int | None = None
    column: int | None = None
    label: str | None = None      # e.g. heading name, function name


@dataclass
class Evidence:
    """What justifies a trace edge."""
    kind: str                        # "tag:impl", "tag:spec", "ast:call", "heuristic:filename", …
    value: str                       # the extracted value
    source: SourceRef


@dataclass
class TraceNode:
    id: str                          # stable ID  (e.g. "1.1", "auth-login")
    type: NodeType
    title: str                       # human-readable
    source: SourceRef
    framework_origin: str            # "spectra", "cc-sdd", "plain", …
    confidence: float = 1.0          # 0.0 ~ 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceEdge:
    src_id: str
    dst_id: str
    relation: EdgeRelation
    strength: EdgeStrength
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class TraceGraph:
    """The full result of analyzing a project."""
    nodes: dict[str, TraceNode] = field(default_factory=dict)
    edges: list[TraceEdge] = field(default_factory=list)
    _edge_keys: set[tuple[str, str, EdgeRelation]] = field(default_factory=set)

    def add_node(self, node: TraceNode) -> str:
        uid = node.id or str(uuid.uuid4())
        node.id = uid
        self.nodes[uid] = node
        return uid

    def add_edge(self, edge: TraceEdge) -> None:
        key = (edge.src_id, edge.dst_id, edge.relation)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self.edges.append(edge)

    def nodes_by_type(self, t: NodeType) -> list[TraceNode]:
        return [n for n in self.nodes.values() if n.type == t]

    def edges_to(self, node_id: str) -> list[TraceEdge]:
        return [e for e in self.edges if e.dst_id == node_id]

    def edges_from(self, node_id: str) -> list[TraceEdge]:
        return [e for e in self.edges if e.src_id == node_id]


def find_spec_nodes(graph: TraceGraph, query: str) -> list[TraceNode]:
    """Find spec nodes by exact ID, suffix match, or title match.

    Resolution order:
      1. Exact node ID match (e.g. ``docs.en.07-cli-commands.1.1``)
      2. ``spec::`` prefix match (e.g. ``1.1`` → ``spec::1.1``)
      3. ID suffix match (e.g. ``1.1`` → ``docs.en.07-cli-commands.1.1``)
      4. Title substring match (e.g. ``TraceNode``)
      5. Heading text substring match (fallback)
    """
    # 1-2. Exact ID or spec:: prefix
    node = graph.nodes.get(query) or graph.nodes.get(f"spec::{query}")
    if node:
        return [node]

    specs = graph.nodes_by_type(NodeType.SPEC)

    # 3. Suffix match: query matches the trailing part of an ID
    #    Also handles spec:: prefix (e.g. query "1.1" matches "spec::1.1")
    suffix_matches = [n for n in specs if n.id.endswith(f".{query}") or n.id == f"spec::{query}"]
    if suffix_matches:
        return sorted(suffix_matches, key=lambda x: x.id)

    # 4. Title substring match
    title_matches = [n for n in specs if query.lower() in n.title.lower()]
    if title_matches:
        return sorted(title_matches, key=lambda x: x.id)

    # 5. Heading text substring match (fallback)
    heading_matches = [
        n for n in specs
        if query.lower() in n.metadata.get("heading_text", "").lower()
    ]
    return sorted(heading_matches, key=lambda x: x.id)


def find_specs_by_file(graph: TraceGraph, file_path: str) -> list[dict[str, Any]]:
    """Find all specs that are connected to a given file path.

    This is the reverse of ``find_spec_nodes`` — given a code/test/design file,
    find all spec nodes it implements, verifies, or satisfies.

    Returns a list of dicts with:
      - ``file``: the matched file path (as stored in the graph)
      - ``specs``: list of ``{spec_id, title, relation, strength, evidence}``
    """
    results: list[dict[str, Any]] = []

    # Find all code/test/design nodes whose source.file matches
    matched_node_ids: list[str] = []
    for nid, node in graph.nodes.items():
        if node.type in (NodeType.SPEC, NodeType.TASK):
            continue
        if file_path in node.source.file or node.source.file.endswith(file_path):
            matched_node_ids.append(nid)

    if not matched_node_ids:
        return results

    for nid in matched_node_ids:
        matched_node = graph.nodes.get(nid)
        if not matched_node:
            continue

        # Find edges FROM this code node TO spec nodes
        spec_edges: list[dict[str, Any]] = []
        for e in graph.edges_from(nid):
            if e.relation in (EdgeRelation.IMPLEMENTS, EdgeRelation.VERIFIES, EdgeRelation.SATISFIES):
                dst = graph.nodes.get(e.dst_id)
                spec_edges.append({
                    "spec_id": e.dst_id,
                    "title": dst.title if dst else "?",
                    "relation": e.relation.value,
                    "strength": e.strength.value,
                    "confidence": dst.confidence if dst else 0.0,
                    "evidence": [{"kind": ev.kind, "value": ev.value} for ev in e.evidence],
                })

        if spec_edges:
            results.append({
                "file": matched_node.source.file,
                "node_type": matched_node.type.value,
                "specs": spec_edges,
            })

    return results
