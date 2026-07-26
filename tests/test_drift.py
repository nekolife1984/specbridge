"""Tests for drift detection (analyzers/drift.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specbridge.analyzers.drift import (
    DriftReport,
    build_snapshot,
    compute_drift,
    load_snapshot,
    save_snapshot,
)
from specbridge.discovery.code import discover_code
from specbridge.discovery.spec import discover_specs


class TestSnapshot:
    """Snapshot construction and I/O."""

    def test_build_snapshot(self, tmp_project_heuristic: Path) -> None:
        """Snapshot has all expected keys."""
        snap = build_snapshot(str(tmp_project_heuristic))
        assert "timestamp" in snap
        assert "specs" in snap
        assert "code" in snap
        assert "coverage" in snap
        assert len(snap["specs"]) >= 2
        assert len(snap["code"]) >= 2

    def test_snapshot_spec_hashes(self, tmp_project_heuristic: Path) -> None:
        """Spec sections have body_hashes."""
        snap = build_snapshot(str(tmp_project_heuristic))
        for s in snap["specs"]:
            assert "body_hash" in s
            assert len(s["body_hash"]) == 16
            assert "body_line_count" in s
            assert s["body_line_count"] >= 1

    def test_snapshot_code_hashes(self, tmp_project_heuristic: Path) -> None:
        """Code files have file_hash and function hashes."""
        snap = build_snapshot(str(tmp_project_heuristic))
        for c in snap["code"]:
            assert "file_hash" in c
            assert len(c["file_hash"]) == 16
            for f in c.get("functions", []):
                assert "body_hash" in f
                assert len(f["body_hash"]) == 16

    def test_save_load_snapshot(self, tmp_project_heuristic: Path) -> None:
        """Snapshot is written and readable."""
        project = tmp_project_heuristic
        snap = build_snapshot(str(project))
        path = save_snapshot(snap, str(project))
        assert path.exists()
        assert path.name == "snapshot.json"
        assert path.parent.name == ".specbridge"

        loaded = load_snapshot(str(project))
        assert loaded is not None
        assert loaded["timestamp"] == snap["timestamp"]
        assert len(loaded["specs"]) == len(snap["specs"])

    def test_load_nonexistent(self, tmp_project_heuristic: Path) -> None:
        """Loading from project without snapshot returns None."""
        snap = load_snapshot(str(tmp_project_heuristic))
        assert snap is None

    def test_snapshot_coverage(self, tmp_project_heuristic: Path) -> None:
        """Coverage stats in snapshot."""
        snap = build_snapshot(str(tmp_project_heuristic))
        cov = snap["coverage"]
        assert "coverage_pct" in cov
        assert "spec_count" in cov
        assert "code_count" in cov
        assert cov["spec_count"] >= 2


class TestDriftCompute:
    """Drift computation between snapshots and current state."""

    def test_no_drift(self, tmp_project_heuristic: Path) -> None:
        """Identical state produces no drift."""
        snap = build_snapshot(str(tmp_project_heuristic))
        report = compute_drift(snap, str(tmp_project_heuristic))
        assert not report.has_drift

    def test_drift_add_spec(self, tmp_project_heuristic: Path) -> None:
        """Adding a spec heading triggers specs_added."""
        project = tmp_project_heuristic
        snap = build_snapshot(str(project))

        # Add a new spec heading
        auth_file = project / "docs" / "auth.md"
        auth_file.write_text(auth_file.read_text() + "\n## API Keys\nNew keys.\n")

        report = compute_drift(snap, str(project))
        assert len(report.specs_added) >= 1

    def test_drift_remove_spec(self, tmp_project_heuristic: Path) -> None:
        """Removing a spec heading triggers specs_removed."""
        project = tmp_project_heuristic
        snap = build_snapshot(str(project))

        # Remove the second heading from auth.md
        (project / "docs" / "auth.md").write_text("# User Login\nLogin spec.\n")

        report = compute_drift(snap, str(project))
        assert len(report.specs_removed) >= 1

    def test_drift_body_change(self, tmp_project_heuristic: Path) -> None:
        """Changing spec body (same heading) triggers specs_body_changed."""
        project = tmp_project_heuristic
        snap = build_snapshot(str(project))

        # Change body text without changing heading
        (project / "docs" / "auth.md").write_text(
            "# User Login\n\nUsers authenticate with SSO now.\n"
        )

        report = compute_drift(snap, str(project))
        assert len(report.specs_body_changed) >= 1

    def test_drift_add_code(self, tmp_project_heuristic: Path) -> None:
        """Adding a code file triggers code_added."""
        project = tmp_project_heuristic
        snap = build_snapshot(str(project))

        (project / "src" / "auth" / "register.py").write_text(
            "def register(): pass\n"
        )

        report = compute_drift(snap, str(project))
        assert len(report.code_added) >= 1

    def test_drift_remove_code(self, tmp_project_heuristic: Path) -> None:
        """Removing a code file triggers code_removed."""
        project = tmp_project_heuristic
        snap = build_snapshot(str(project))

        (project / "src" / "auth" / "login.py").unlink()

        report = compute_drift(snap, str(project))
        assert len(report.code_removed) >= 1

    def test_drift_func_body_change(self, tmp_project_heuristic: Path) -> None:
        """Changing function body triggers code_funcs_changed."""
        project = tmp_project_heuristic
        snap = build_snapshot(str(project))

        # Change function body in login.py
        (project / "src" / "auth" / "login.py").write_text(
            "def login(email: str) -> bool:\n    return False  # changed\n"
        )

        report = compute_drift(snap, str(project))
        assert len(report.code_funcs_changed) >= 1

    def test_drift_symbol_change(self, tmp_project_heuristic: Path) -> None:
        """Adding/removing symbols triggers code_symbols_changed."""
        project = tmp_project_heuristic
        snap = build_snapshot(str(project))

        # Add a new function
        (project / "src" / "auth" / "login.py").write_text(
            "def login(email: str) -> bool:\n    return True\n"
            "def new_feature(): pass\n"
        )

        report = compute_drift(snap, str(project))
        assert len(report.code_symbols_changed) >= 1

    def test_drift_coverage_change(self, tmp_project_heuristic: Path) -> None:
        """Coverage stats are tracked before and after."""
        project = tmp_project_heuristic
        snap = build_snapshot(str(project))
        report = compute_drift(snap, str(project))
        assert report.coverage_before is not None
        assert report.coverage_after is not None

    def test_drift_empty_project(self, tmp_path: Path) -> None:
        """Empty project snapshot compared with same empty state produces no drift."""
        project = tmp_path / "empty"
        project.mkdir()
        snap = build_snapshot(str(project))
        report = compute_drift(snap, str(project))
        assert not report.has_drift


class TestDriftReport:
    """DriftReport rendering."""

    def test_render_no_drift(self) -> None:
        """Empty report shows 'No drift detected'."""
        r = DriftReport()
        text = r.render_text()
        assert "No drift detected" in text

    def test_render_has_drift(self) -> None:
        """Non-empty report shows details."""
        r = DriftReport()
        r.specs_added.append({"id": "3", "title": "New", "file": "docs/new.md"})
        text = r.render_text()
        assert "New specs" in text
        assert "3" in text

    def test_to_dict(self) -> None:
        """to_dict() returns all fields."""
        r = DriftReport()
        r.specs_added.append({"id": "1"})
        d = r.to_dict()
        assert d["has_drift"] is True
        assert "specs_added" in d
        assert "code_removed" in d
        assert "coverage_before" in d

    @property
    def test_has_drift_true_when_changes(self) -> None:
        r = DriftReport()
        assert not r.has_drift
        r.specs_added.append({"id": "1", "title": "x", "file": "x.md"})
        assert r.has_drift
