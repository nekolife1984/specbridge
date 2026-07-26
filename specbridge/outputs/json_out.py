"""JSON output."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from specbridge.core import TraceGraph


def _node_dict(n: Any) -> dict[str, Any]:
    d = asdict(n)
    d["type"] = n.type.value
    return d


def _edge_dict(e: Any) -> dict[str, Any]:
    d = asdict(e)
    d["relation"] = e.relation.value
    d["strength"] = e.strength.value
    return d


def render_json(graph: TraceGraph, indent: int = 2) -> str:
    payload = {
        "specbridge_version": "0.0.1.dev0",
        "nodes": [_node_dict(n) for n in graph.nodes.values()],
        "edges": [_edge_dict(e) for e in graph.edges],
    }
    return json.dumps(payload, indent=indent, ensure_ascii=False, default=str)
