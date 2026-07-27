"""Scale tests: verify specbridge handles large projects without crashing.

Generates projects with many spec documents and source files to stress
the O(N×M) heuristic matching and ensure reasonable performance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specbridge.adapters._base import detect_adapter
from specbridge.analyzers import coverage_summary
from specbridge.analyzers.drift import build_snapshot, compute_drift
from specbridge.core import NodeType


def _generate_large_project(
    base: Path,
    *,
    spec_count: int = 30,
    code_count: int = 100,
    subheadings: int = 2,
) -> None:
    """Generate a project with *spec_count* spec files and *code_count* code files.

    Each spec file has a top-level heading plus *subheadings* sub-sections.
    Code files are distributed across src/ subdirectories matching spec topics.
    """
    docs = base / "docs"
    src = base / "src"
    docs.mkdir(parents=True)
    src.mkdir(parents=True)

    topics = [
        "authentication", "authorization", "billing", "caching", "database",
        "email", "files", "graphql", "http", "indexing", "jobs", "logging",
        "metrics", "notifications", "observability", "pagination", "queue",
        "rate-limiting", "search", "templates", "uploads", "validation",
        "webhooks", "xml", "yaml", "zip",
    ]

    for i in range(spec_count):
        topic = topics[i % len(topics)]
        doc_file = docs / f"{topic}-{i // len(topics)}.md"
        lines = [f"# {topic.title()} {i // len(topics)}", ""]
        for j in range(subheadings):
            lines.append(f"## {j+1}.{i+1} Sub Topic {topic} {j}")
            lines.append("")
            lines.append(f"Description for sub-topic {j} of {topic}.")
            lines.append("")
        doc_file.write_text("\n".join(lines), encoding="utf-8")

    for i in range(code_count):
        topic = topics[i % len(topics)]
        subdir = src / topic
        subdir.mkdir(exist_ok=True)
        code_file = subdir / f"handler_{i // len(topics)}.py"
        code_file.write_text(
            f"# handler for {topic}\n"
            f"def handle_{topic}_{i // len(topics)}():\n"
            f"    return True\n",
            encoding="utf-8",
        )


class TestLargeProjectScale:
    """Stress-test heuristic matching with many files."""

    @pytest.fixture(scope="module")
    def large_project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """Generate a project with ~150 specs and ~200 code files."""
        root = tmp_path_factory.mktemp("large-project")
        _generate_large_project(root, spec_count=50, code_count=200, subheadings=3)
        return root

    def test_analysis_completes(self, large_project: Path) -> None:
        """Analysis runs without error on a large project."""
        adapter = detect_adapter(str(large_project))
        assert adapter is not None
        graph = adapter.analyze(str(large_project))
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0
        spec_count = len(graph.nodes_by_type(NodeType.SPEC))
        assert spec_count >= 100  # 50 files × 3 headings + top-level
        code_count = len(graph.nodes_by_type(NodeType.CODE))
        assert code_count >= 100

    def test_coverage_summary(self, large_project: Path) -> None:
        """Coverage calculation works on large projects."""
        adapter = detect_adapter(str(large_project))
        assert adapter is not None
        graph = adapter.analyze(str(large_project))
        cov = coverage_summary(graph)
        assert cov["total"] > 0
        assert "coverage_pct" in cov
        assert 0 <= cov["coverage_pct"] <= 100

    def test_snapshot_and_drift(self, large_project: Path) -> None:
        """Snapshot and drift work on large projects without regression."""
        snap = build_snapshot(str(large_project))
        assert len(snap["specs"]) > 0
        assert len(snap["code"]) > 0
        report = compute_drift(snap, str(large_project))
        # No drift expected since project hasn't changed
        assert not report.has_drift

    def test_func_match_mode(self, large_project: Path) -> None:
        """Function-level matching mode (opt-in via func_match) works."""
        adapter = detect_adapter(str(large_project))
        assert adapter is not None
        adapter.fast = False
        graph = adapter.analyze(str(large_project))
        assert len(graph.nodes) > 0
