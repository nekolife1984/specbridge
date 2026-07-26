"""Example specbridge adapter plugin — demonstrates the Plugin SDK."""

from specbridge.adapters._base import ProjectAdapter, register
from specbridge.core import Evidence, NodeType, SourceRef, TraceEdge, TraceGraph, TraceNode


@register
class ExampleAdapter(ProjectAdapter):
    """A no-op adapter that only detects projects with a .example-plugin marker."""

    def detect(self, directory: str) -> float:
        from pathlib import Path
        marker = Path(directory) / ".example-plugin"
        return 0.8 if marker.exists() else 0.0

    def analyze(self, directory: str) -> TraceGraph:
        graph = TraceGraph()
        spec = TraceNode(
            id="example:001",
            type=NodeType.SPEC,
            title="Example Spec",
            source=SourceRef(file=".example-plugin"),
            framework_origin="example-plugin",
            confidence=0.8,
        )
        graph.add_node(spec)
        code = TraceNode(
            id="example:001::example_adapter.py",
            type=NodeType.CODE,
            title="example_adapter.py",
            source=SourceRef(file="example_adapter.py"),
            framework_origin="example-plugin",
            confidence=0.9,
        )
        graph.add_node(code)
        graph.add_edge(TraceEdge(
            src_id=code.id,
            dst_id=spec.id,
            relation="implements",
            strength="explicit",
            evidence=[Evidence(kind="tag:impl", value="example:001",
                               source=SourceRef(file="example_adapter.py"))],
        ))
        return graph
