"""Tests for read-only guard (specbridge/guard.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specbridge.guard import validate_write_path


class TestValidateWritePath:
    """validate_write_path blocks writes outside .specbridge/."""

    def test_allowed_specbridge_dir(self, tmp_path: Path) -> None:
        """Writing inside .specbridge/ is allowed."""
        root = tmp_path / "proj"
        root.mkdir()
        target = root / ".specbridge" / "snapshot.json"
        result = validate_write_path(target, root)
        assert result == target.resolve()

    def test_allowed_specbridge_subdir(self, tmp_path: Path) -> None:
        """Writing inside .specbridge/subdir/ is allowed."""
        root = tmp_path / "proj"
        root.mkdir()
        target = root / ".specbridge" / "cache" / "data.json"
        result = validate_write_path(target, root)
        assert result == target.resolve()

    def test_block_docs_dir(self, tmp_path: Path) -> None:
        """Writing to docs/ raises PermissionError."""
        root = tmp_path / "proj"
        root.mkdir()
        target = root / "docs" / "auth.md"
        with pytest.raises(PermissionError, match="protected spec or source"):
            validate_write_path(target, root)

    def test_block_src_dir(self, tmp_path: Path) -> None:
        """Writing to src/ raises PermissionError."""
        root = tmp_path / "proj"
        root.mkdir()
        target = root / "src" / "login.py"
        with pytest.raises(PermissionError, match="protected spec or source"):
            validate_write_path(target, root)

    def test_block_lib_dir(self, tmp_path: Path) -> None:
        """Writing to lib/ raises PermissionError."""
        root = tmp_path / "proj"
        root.mkdir()
        target = root / "lib" / "main.py"
        with pytest.raises(PermissionError):
            validate_write_path(target, root)

    def test_block_tests_dir(self, tmp_path: Path) -> None:
        """Writing to tests/ raises PermissionError."""
        root = tmp_path / "proj"
        root.mkdir()
        target = root / "tests" / "test_main.py"
        with pytest.raises(PermissionError):
            validate_write_path(target, root)

    def test_block_spec_dir(self, tmp_path: Path) -> None:
        """Writing to spec/ raises PermissionError."""
        root = tmp_path / "proj"
        root.mkdir()
        target = root / "spec" / "index.md"
        with pytest.raises(PermissionError):
            validate_write_path(target, root)

    def test_block_outside_project(self, tmp_path: Path) -> None:
        """Writing outside project root raises PermissionError."""
        root = tmp_path / "proj"
        root.mkdir()
        target = tmp_path / "other" / "file.md"
        with pytest.raises(PermissionError, match="outside the project root"):
            validate_write_path(target, root)

    def test_block_project_root_itself(self, tmp_path: Path) -> None:
        """Writing to project root raises PermissionError."""
        root = tmp_path / "proj"
        root.mkdir()
        target = root / "somefile.md"
        with pytest.raises(PermissionError, match="not inside"):
            validate_write_path(target, root)

    def test_block_relative_path_traversal(self, tmp_path: Path) -> None:
        """Path traversal like ../docs/ is blocked."""
        root = tmp_path / "proj"
        root.mkdir()
        safe_dir = root / ".specbridge"
        safe_dir.mkdir(parents=True)
        # A path that tries to escape via relative symlink or just a path
        bad = root / ".specbridge" / ".." / "docs" / "auth.md"
        with pytest.raises(PermissionError):
            validate_write_path(bad, root)

    def test_snapshot_write_validated(self, tmp_project_heuristic: Path) -> None:
        """save_snapshot calls validate_write_path internally."""
        from specbridge.analyzers.drift import build_snapshot, save_snapshot
        snap = build_snapshot(str(tmp_project_heuristic))
        path = save_snapshot(snap, str(tmp_project_heuristic))
        assert path.exists()
        assert ".specbridge" in str(path)
