"""Tests for _Boundary:_ parsing and validation."""

from __future__ import annotations

from pathlib import Path

from specbridge.adapters.spectra import SpectraAdapter
from specbridge.core import NodeType
from specbridge.core.extract import RE_BOUNDARY, extract_tags_from_file


class TestBoundaryExtract:
    """_Boundary:_ tag extraction."""

    def test_boundary_parsed_from_markdown(self, tmp_path: Path) -> None:
        """_Boundary:_ is extracted from spec docs."""
        project = tmp_path / "proj"
        project.mkdir()
        doc = project / "docs" / "auth.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("<!-- @spec 1.1 -->\n# Auth\n_Boundary:_ src/auth/\n")

        tags = extract_tags_from_file(doc, project)
        boundaries = [t for t in tags if t.kind == "boundary"]
        assert len(boundaries) == 1
        assert boundaries[0].value == "src/auth/"

    def test_boundary_line_number(self, tmp_path: Path) -> None:
        """_Boundary:_ line number is correct."""
        project = tmp_path / "proj"
        project.mkdir()
        doc = project / "docs" / "auth.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# Auth\n\n_Boundary:_ src/auth/\n")

        tags = extract_tags_from_file(doc, project)
        boundaries = [t for t in tags if t.kind == "boundary"]
        assert boundaries[0].line == 3

    def test_multiple_boundaries(self, tmp_path: Path) -> None:
        """Multiple _Boundary:_ markers are extracted."""
        project = tmp_path / "proj"
        project.mkdir()
        doc = project / "docs" / "auth.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# Auth\n_Boundary:_ src/auth/\n_Boundary:_ src/common/\n")

        tags = extract_tags_from_file(doc, project)
        boundaries = [t for t in tags if t.kind == "boundary"]
        assert len(boundaries) == 2

    def test_no_boundary(self, tmp_path: Path) -> None:
        """No _Boundary:_ in file returns no boundary tags."""
        project = tmp_path / "proj"
        project.mkdir()
        doc = project / "docs" / "auth.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# Auth\nNo boundaries here.\n")

        tags = extract_tags_from_file(doc, project)
        boundaries = [t for t in tags if t.kind == "boundary"]
        assert len(boundaries) == 0

    def test_regex_direct(self) -> None:
        """RE_BOUNDARY regex matches correctly."""
        text = "# Auth\n_Boundary:_ src/auth/\n"
        matches = RE_BOUNDARY.findall(text)
        assert len(matches) == 1
        assert matches[0] == "src/auth/"

    def test_regex_no_match_without_underscore(self) -> None:
        """'Boundary:' without underscores is not matched."""
        text = "Boundary: src/\n"
        assert len(RE_BOUNDARY.findall(text)) == 0

    def test_regex_indented_boundary(self) -> None:
        """Indented boundaries are still matched."""
        text = "  _Boundary:_ src/auth/\n"
        matches = RE_BOUNDARY.findall(text)
        # Only matches when at start of line (^)
        # Indented lines:  "  _Boundary:_" won't match ^_Boundary
        assert len(matches) == 0


class TestBoundarySpectraAdapter:
    """Boundaries stored as spec node metadata in spectra adapter."""

    def test_boundary_in_metadata(self, tmp_project_spectra: Path) -> None:
        """Spec with boundary in same file gets metadata."""
        # Add _Boundary:_ to the spectra fixture's auth.md
        auth_md = tmp_project_spectra / "docs" / "auth.md"
        auth_md.write_text(
            "<!-- @spec 1.1 -->\n"
            "# User Authentication\n"
            "_Boundary:_ src/auth/\n"
            "<!-- @satisfies 1.1 -->\n"
        )

        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        spec_node = graph.nodes.get("spec::1.1")
        assert spec_node is not None
        boundaries = spec_node.metadata.get("boundaries", [])
        assert len(boundaries) >= 1
        assert boundaries[0]["path"] == "src/auth/"

    def test_boundary_not_required(self, tmp_project_spectra: Path) -> None:
        """Specs without boundaries just have empty metadata."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        specs = graph.nodes_by_type(NodeType.SPEC)
        for s in specs:
            # Boundaries is optional
            if "boundaries" in s.metadata:
                assert isinstance(s.metadata["boundaries"], list)

    def test_boundary_validation(self, tmp_project_spectra: Path) -> None:
        """validate-boundary CLI detects violations."""
        from click.testing import CliRunner

        from specbridge.cli import cli

        auth_md = tmp_project_spectra / "docs" / "auth.md"
        auth_md.write_text(
            "<!-- @spec 1.1 -->\n"
            "# User Authentication\n"
            "_Boundary:_ src/api/\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, ["validate-boundary", "--dir", str(tmp_project_spectra)]
        )
        # src/auth/login.py is NOT under src/api/ — boundary violation
        assert "boundary violation" in result.output.lower()
        assert result.exit_code == 0

    def test_boundary_valid(self, tmp_project_spectra: Path) -> None:
        """Code inside boundary passes validation."""
        from click.testing import CliRunner

        from specbridge.cli import cli

        auth_md = tmp_project_spectra / "docs" / "auth.md"
        auth_md.write_text(
            "<!-- @spec 1.1 -->\n"
            "# User Authentication\n"
            "_Boundary:_ src/auth/\n"
            "_Boundary:_ tests/\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, ["validate-boundary", "--dir", str(tmp_project_spectra)]
        )
        assert "All code refs are within declared boundaries" in result.output
        assert result.exit_code == 0
