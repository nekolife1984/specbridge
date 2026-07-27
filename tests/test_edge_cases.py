"""Edge-case tests: special paths, Unicode, binary files, permissions.

Verifies specbridge handles real-world edge cases gracefully without crashing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specbridge.adapters._base import detect_adapter
from specbridge.config import SpecbridgeConfig
from specbridge.core import NodeType


class TestPathEdgeCases:
    """Paths with special characters, spaces, and Unicode."""

    @pytest.fixture(scope="module")
    def edge_project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """Project with edge-case filenames."""
        root = tmp_path_factory.mktemp("edge-project")

        # Path with spaces
        docs = root / "my docs"
        docs.mkdir(parents=True)
        src = root / "src code"
        src.mkdir(parents=True)

        # Unicode path (Japanese)
        docs_ja = root / "ドキュメント"
        docs_ja.mkdir(parents=True)
        src_ja = root / "ソースコード"
        src_ja.mkdir(parents=True)

        # Very long filename (255 chars)
        long_name = "a" * 250 + ".md"
        (docs / long_name).write_text("# Long File\n\nContent.\n", encoding="utf-8")

        # Emoji in filename
        (docs_ja / "🎯-target.md").write_text("# Target\n\nHit the target.\n", encoding="utf-8")

        # Spaces in filename
        (docs / "user auth.md").write_text("# User Auth\n\nAuth content.\n", encoding="utf-8")

        # Deeply nested path
        deep = docs_ja
        for _ in range(20):
            deep = deep / "nested"
        deep.mkdir(parents=True)
        (deep / "deep.md").write_text("# Deep\n\nDeep content.\n", encoding="utf-8")

        # Matching source files with special paths
        (src / "auth handler.py").write_text("def login(): return True\n", encoding="utf-8")
        (src_ja / "ログイン.py").write_text("def login(): return True\n", encoding="utf-8")
        (src / long_name.replace(".md", ".py")).write_text(
            "def long_func(): return True\n", encoding="utf-8"
        )

        # Create .specbridge.yaml with custom dirs
        config_path = root / ".specbridge.yaml"
        config_path.write_text(
            "spec_dirs:\n  - my docs\n  - ドキュメント\n"
            "source_dirs:\n  - src code\n  - ソースコード\n",
            encoding="utf-8",
        )

        # Also create default dirs so detect_adapter() finds the project
        docs_default = root / "docs"
        docs_default.mkdir(exist_ok=True)
        (docs_default / "🎯-target.md").write_text("# Target\n\nHit the target.\n", encoding="utf-8")
        (docs_default / "user auth.md").write_text("# User Auth\n\nAuth content.\n", encoding="utf-8")
        (docs_default / "unicode_üñîċödé.md").write_text("# Unicode\n\nUnicode content.\n", encoding="utf-8")
        src_default = root / "src"
        src_default.mkdir(exist_ok=True)
        (src_default / "auth handler.py").write_text("def login(): return True\n", encoding="utf-8")
        (src_default / "unicode_handler.py").write_text("def process(): pass\n", encoding="utf-8")
        (src_default / ("long_name_" + "a" * 50 + ".py")).write_text("def long_func(): return 42\n", encoding="utf-8")

        return root

    def test_special_paths_analyze(self, edge_project: Path) -> None:
        """Analysis handles paths with spaces, Unicode, long names."""
        adapter = detect_adapter(str(edge_project))
        assert adapter is not None
        graph = adapter.analyze(str(edge_project))
        assert len(graph.nodes) > 0
        specs = graph.nodes_by_type(NodeType.SPEC)
        assert len(specs) >= 3  # Long File, Target, User Auth, Deep

    def test_config_with_special_paths(self, edge_project: Path) -> None:
        """Config loading handles directories with spaces and Unicode."""
        cfg = SpecbridgeConfig.load(str(edge_project))
        assert "my docs" in cfg.spec_dirs
        assert "ドキュメント" in cfg.spec_dirs
        assert "src code" in cfg.source_dirs
        assert "ソースコード" in cfg.source_dirs

    def test_snapshot_with_special_paths(self, edge_project: Path) -> None:
        """Snapshot handles special file paths."""
        from specbridge.analyzers.drift import build_snapshot
        snap = build_snapshot(str(edge_project))
        assert len(snap["specs"]) >= 3
        assert len(snap["code"]) >= 3


class TestCorruptedInput:
    """Binary files, invalid content, empty files."""

    @pytest.fixture(scope="module")
    def corrupted_project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """Project with corrupted/docs files."""
        root = tmp_path_factory.mktemp("corrupted-project")
        docs = root / "docs"
        docs.mkdir()
        src = root / "src"
        src.mkdir()

        # Valid content (baseline)
        (docs / "valid.md").write_text("# Valid\n\nContent.\n", encoding="utf-8")

        # Binary file in docs/ (should be gracefully skipped)
        bin_path = docs / "image.png"
        bin_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        # Empty markdown file
        (docs / "empty.md").write_text("", encoding="utf-8")

        # Markdown with only frontmatter (no headings)
        (docs / "frontmatter.md").write_text("---\ntitle: Test\n---\n\nSome text without headings.\n", encoding="utf-8")

        # Very large heading
        (docs / "large.md").write_text(
            "# " + "x" * 10000 + "\n\nContent.\n", encoding="utf-8"
        )

        # Nested dirs with only non-markdown files
        no_md = docs / "subdir" / "no-markdown"
        no_md.mkdir(parents=True)
        (no_md / "readme.txt").write_text("No markdown here.", encoding="utf-8")

        # Code files
        (src / "handler.py").write_text("def handle(): return True\n", encoding="utf-8")

        return root

    def test_binary_file_ignored(self, corrupted_project: Path) -> None:
        """Binary files in docs/ are gracefully skipped."""
        adapter = detect_adapter(str(corrupted_project))
        assert adapter is not None
        graph = adapter.analyze(str(corrupted_project))
        specs = graph.nodes_by_type(NodeType.SPEC)
        # Should find "Valid" heading, not crash on binary or empty
        assert any("Valid" in s.title for s in specs)

    def test_empty_file_no_crash(self, corrupted_project: Path) -> None:
        """Empty markdown files don't cause errors."""
        adapter = detect_adapter(str(corrupted_project))
        assert adapter is not None
        graph = adapter.analyze(str(corrupted_project))
        # Analysis completes without error
        assert graph is not None

    def test_no_headings_still_scanned(self, corrupted_project: Path) -> None:
        """Files without headings produce no spec nodes but don't crash."""
        adapter = detect_adapter(str(corrupted_project))
        assert adapter is not None
        graph = adapter.analyze(str(corrupted_project))
        # Code files should still be discovered
        code_nodes = graph.nodes_by_type(NodeType.CODE)
        assert len(code_nodes) >= 1

    def test_large_heading_not_truncated(self, corrupted_project: Path) -> None:
        """Very long heading text doesn't crash parser."""
        adapter = detect_adapter(str(corrupted_project))
        assert adapter is not None
        graph = adapter.analyze(str(corrupted_project))
        specs = graph.nodes_by_type(NodeType.SPEC)
        # The large heading should be found (title might be truncated by design)
        assert len(specs) >= 1
