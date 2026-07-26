"""Tests for code discovery (discovery/code.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specbridge.discovery.code import CodeCandidate, discover_code


class TestDiscoverCode:
    """Code discovery from source directories."""

    def test_discover_python(self, tmp_project_heuristic: Path) -> None:
        """Python files are discovered with symbols."""
        codes = discover_code(str(tmp_project_heuristic))
        py_files = [c for c in codes if c.language == "Python"]
        assert len(py_files) >= 1
        assert any("login" in c.file for c in py_files)

    def test_discover_symbols(self, tmp_project_heuristic: Path) -> None:
        """Symbols are extracted from Python files."""
        codes = discover_code(str(tmp_project_heuristic))
        for c in codes:
            if "login.py" in c.file:
                assert len(c.symbols) >= 1
                assert "login" in c.symbols or "Session" in c.symbols
                break

    def test_discover_functions(self, tmp_project_heuristic: Path) -> None:
        """Function blocks are extracted."""
        codes = discover_code(str(tmp_project_heuristic))
        for c in codes:
            if c.functions:
                for f in c.functions:
                    assert f.name
                    assert f.kind in ("function", "class")
                    assert f.body_hash
                    assert len(f.body_hash) == 16  # SHA256[:16]
                    assert f.body_lines > 0
                break

    def test_discover_file_hash(self, tmp_project_heuristic: Path) -> None:
        """File-level hash is computed."""
        codes = discover_code(str(tmp_project_heuristic))
        for c in codes:
            assert c.file_hash
            assert len(c.file_hash) == 16

    def test_discover_imports(self, tmp_project_heuristic: Path) -> None:
        """Imports are extracted (Python)."""
        codes = discover_code(str(tmp_project_heuristic))
        for c in codes:
            assert isinstance(c.imports, list)

    def test_discover_test_detection(self, tmp_path: Path) -> None:
        """Files matching test patterns are marked is_test=True."""
        project = tmp_path / "test-check"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "test_auth.py").write_text("def test_auth(): pass\n")
        (project / "src" / "auth.py").write_text("def auth(): pass\n")

        codes = discover_code(str(project))
        test_files = [c for c in codes if c.is_test]
        nontest_files = [c for c in codes if not c.is_test]
        assert len(test_files) >= 1
        assert len(nontest_files) >= 1

    def test_discover_language(self, tmp_path: Path) -> None:
        """Language field is populated correctly."""
        project = tmp_path / "langs"
        project.mkdir()
        src = project / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass\n")
        (src / "app.ts").write_text("export function app(): void {}\n")
        (src / "server.go").write_text("package main\nfunc main() {}\n")

        codes = discover_code(str(project))
        langs = {c.language for c in codes}
        assert "Python" in langs
        assert "TypeScript" in langs
        assert "Go" in langs

    def test_discover_empty_source_dir(self, tmp_path: Path) -> None:
        """No source dir returns empty list."""
        project = tmp_path / "empty"
        project.mkdir()
        codes = discover_code(str(project))
        assert codes == []

    def test_discover_excluded_dirs(self, tmp_project_heuristic: Path) -> None:
        """node_modules/ is excluded."""
        project = tmp_project_heuristic
        node_mod = project / "node_modules" / "lib"
        node_mod.mkdir(parents=True)
        (node_mod / "index.js").write_text("export function foo() {}\n")

        codes = discover_code(str(project))
        js_files = [c for c in codes if c.file.startswith("node_modules")]
        assert len(js_files) == 0

    def test_discover_source_dirs_custom(self, tmp_path: Path) -> None:
        """Custom source_dirs parameter works."""
        project = tmp_path / "custom-src"
        project.mkdir()
        (project / "handlers").mkdir()
        (project / "handlers" / "main.py").write_text("def handle(): pass\n")

        codes = discover_code(str(project), source_dirs=["handlers"])
        assert len(codes) >= 1
