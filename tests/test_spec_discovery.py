"""Tests for spec discovery (discovery/spec.py)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from specbridge.discovery.spec import _parse_yaml_specs, discover_specs


class TestYamlSpecDiscovery:
    """YAML spec file parsing."""

    @pytest.fixture
    def yaml_project(self) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        specs_dir = tmpdir / "specs"
        specs_dir.mkdir()
        yaml_file = specs_dir / "security.yaml"
        yaml_file.write_text("""specs:
  - id: '1'
    title: Security
    description: Security architecture
    tags: [security, auth]
  - id: '1.1'
    title: Authentication
    description: User authentication flow
    parent: '1'
    tags: [auth]
  - id: '1.2'
    title: Authorization
    description: Access control
    parent: '1'
""")
        return tmpdir

    @pytest.fixture
    def multi_yaml_project(self) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        specs_dir = tmpdir / "specs"
        specs_dir.mkdir()
        (specs_dir / "auth.yaml").write_text("""specs:
  - id: 'A1'
    title: Login
    description: Login flow
  - id: 'A2'
    title: Signup
    description: Registration
""")
        (specs_dir / "api.yaml").write_text("""specs:
  - id: 'B1'
    title: REST API
    description: API endpoints
""")
        return tmpdir

    def test_parse_yaml_basic(self, yaml_project: Path) -> None:
        """Parse a basic YAML spec file."""
        file_path = yaml_project / "specs" / "security.yaml"
        text = file_path.read_text()
        candidates = _parse_yaml_specs(file_path, text, yaml_project)
        assert len(candidates) == 3

    def test_yaml_ids_and_titles(self, yaml_project: Path) -> None:
        file_path = yaml_project / "specs" / "security.yaml"
        text = file_path.read_text()
        candidates = _parse_yaml_specs(file_path, text, yaml_project)
        ids = {c.auto_id for c in candidates}
        assert "specs.security.1" in ids
        assert "specs.security.1.1" in ids
        assert "specs.security.1.2" in ids

    def test_yaml_parent_hierarchy(self, yaml_project: Path) -> None:
        file_path = yaml_project / "specs" / "security.yaml"
        text = file_path.read_text()
        candidates = _parse_yaml_specs(file_path, text, yaml_project)
        c_map = {c.auto_id: c for c in candidates}
        # Top-level: Security
        assert c_map["specs.security.1"].heading_depth == 1
        assert c_map["specs.security.1"].parent_chain is None
        # Children: depth=2, parent_chain includes parent title
        assert c_map["specs.security.1.1"].heading_depth == 2
        assert c_map["specs.security.1.1"].parent_chain == ["Security"]

    def test_yaml_body_text(self, yaml_project: Path) -> None:
        file_path = yaml_project / "specs" / "security.yaml"
        text = file_path.read_text()
        candidates = _parse_yaml_specs(file_path, text, yaml_project)
        c = candidates[0]
        assert "Security architecture" in c.body_text
        assert c.body_hash

    def test_yaml_tags_in_body(self, yaml_project: Path) -> None:
        file_path = yaml_project / "specs" / "security.yaml"
        text = file_path.read_text()
        candidates = _parse_yaml_specs(file_path, text, yaml_project)
        # Security has tags [security, auth]
        security = [c for c in candidates if c.title == "Security"][0]
        assert "Tags:" in security.body_text

    def test_yaml_without_specs_key(self) -> None:
        """File without 'specs' key returns empty."""
        tmpdir = Path(tempfile.mkdtemp())
        fp = tmpdir / "empty.yaml"
        fp.write_text("other: data")
        candidates = _parse_yaml_specs(fp, "other: data", tmpdir)
        assert len(candidates) == 0

    def test_yaml_empty_file(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        fp = tmpdir / "empty.yaml"
        fp.write_text("")
        candidates = _parse_yaml_specs(fp, "", tmpdir)
        assert len(candidates) == 0

    def test_yaml_integer_ids(self) -> None:
        """YAML ids can be integers."""
        tmpdir = Path(tempfile.mkdtemp())
        fp = tmpdir / "specs.yaml"
        content = "specs:\n  - id: 1\n    title: One\n  - id: 2\n    title: Two\n    parent: 1\n"
        fp.write_text(content)
        candidates = _parse_yaml_specs(fp, content, tmpdir)
        assert len(candidates) == 2

    def test_yaml_no_title_fallback(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        fp = tmpdir / "specs.yaml"
        content = "specs:\n  - id: 'x'\n"
        fp.write_text(content)
        candidates = _parse_yaml_specs(fp, content, tmpdir)
        assert len(candidates) == 1
        assert candidates[0].title == "x"

    def test_discover_specs_includes_yaml(self, yaml_project: Path) -> None:
        """discover_specs should pick up YAML files in spec_dirs."""
        candidates = discover_specs(
            str(yaml_project),
            spec_dirs=["specs"],
        )
        yaml_candidates = [c for c in candidates if c.file.endswith(".yaml")]
        assert len(yaml_candidates) >= 3

    def test_discover_specs_multi_yaml(self, multi_yaml_project: Path) -> None:
        """Multiple YAML files in spec dirs."""
        candidates = discover_specs(
            str(multi_yaml_project),
            spec_dirs=["specs"],
        )
        assert len(candidates) >= 3  # A1, A2, B1
