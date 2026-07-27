"""Tests for specbridge configuration (config.py)."""

from __future__ import annotations

from pathlib import Path

from specbridge.config import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_SOURCE_DIRS,
    DEFAULT_SPEC_DIRS,
    SpecbridgeConfig,
)


class TestConfigDefaults:
    """Default configuration values."""

    def test_defaults(self) -> None:
        config = SpecbridgeConfig()
        assert config.spec_dirs == ["docs", "spec", "specs"]
        assert config.source_dirs == ["src", "lib", "app"]
        assert config.min_confidence == 0.15
        assert config.max_output_nodes == 20
        assert ".git" in config.exclude_dirs

    def test_load_no_project_file(self, tmp_path: Path) -> None:
        """load() on empty project returns defaults."""
        config = SpecbridgeConfig.load(str(tmp_path / "empty"))
        assert config.spec_dirs == DEFAULT_SPEC_DIRS
        assert config.source_dirs == DEFAULT_SOURCE_DIRS

    def test_load_without_file_at_root(self, tmp_path: Path) -> None:
        """load() at project root without config file returns defaults."""
        config = SpecbridgeConfig.load(str(tmp_path))
        assert config.spec_dirs == DEFAULT_SPEC_DIRS


class TestConfigYaml:
    """.specbridge.yaml loading."""

    def test_yaml_custom_spec_dirs(self, tmp_path: Path) -> None:
        """spec_dirs from .specbridge.yaml."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".specbridge.yaml").write_text("""\
spec_dirs:
  - specs
  - design
""")
        config = SpecbridgeConfig.load(str(project))
        assert config.spec_dirs == ["specs", "design"]
        assert config.source_dirs == DEFAULT_SOURCE_DIRS  # not changed

    def test_yaml_custom_source_dirs(self, tmp_path: Path) -> None:
        """source_dirs from .specbridge.yaml."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".specbridge.yaml").write_text("""\
source_dirs:
  - cmd
  - internal
""")
        config = SpecbridgeConfig.load(str(project))
        assert config.source_dirs == ["cmd", "internal"]

    def test_yaml_min_confidence(self, tmp_path: Path) -> None:
        """min_confidence from .specbridge.yaml."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".specbridge.yaml").write_text("min_confidence: 0.5\n")
        config = SpecbridgeConfig.load(str(project))
        assert config.min_confidence == 0.5

    def test_yaml_max_output_nodes(self, tmp_path: Path) -> None:
        """max_output_nodes from .specbridge.yaml."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".specbridge.yaml").write_text("max_output_nodes: 5\n")
        config = SpecbridgeConfig.load(str(project))
        assert config.max_output_nodes == 5

    def test_yaml_exclude_dirs(self, tmp_path: Path) -> None:
        """exclude_dirs from .specbridge.yaml."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".specbridge.yaml").write_text("""\
exclude_dirs:
  - .git
  - vendor
""")
        config = SpecbridgeConfig.load(str(project))
        assert ".git" in config.exclude_dirs
        assert "vendor" in config.exclude_dirs

    def test_yaml_partial_config(self, tmp_path: Path) -> None:
        """Partial config merges with defaults."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".specbridge.yaml").write_text("min_confidence: 0.8\n")
        config = SpecbridgeConfig.load(str(project))
        assert config.min_confidence == 0.8
        assert config.spec_dirs == DEFAULT_SPEC_DIRS  # unchanged
        assert config.source_dirs == DEFAULT_SOURCE_DIRS  # unchanged

    def test_broken_yaml(self, tmp_path: Path) -> None:
        """Broken YAML falls back to defaults."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".specbridge.yaml").write_text(": broken\n")
        config = SpecbridgeConfig.load(str(project))
        assert config.min_confidence == DEFAULT_MIN_CONFIDENCE


class TestConfigCLI:
    """specbridge config CLI command."""

    def test_config_command_defaults(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from specbridge.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "spec_dirs" in result.output
        assert "max_output_nodes" in result.output

    def test_config_command_shows_source(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from specbridge.cli import cli

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".specbridge.yaml").write_text("min_confidence: 0.5\n")

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--dir", str(project)])
        assert ".specbridge.yaml" in result.output
        assert "0.5" in result.output

    def test_config_command_yaml(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from specbridge.cli import cli

        project = tmp_path / "proj"
        project.mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--dir", str(project), "--yaml"])
        assert result.exit_code == 0
        assert "spec_dirs" in result.output


class TestConfigEdgeCases:
    """Config loading with invalid/edge-case inputs."""

    def test_invalid_yaml_returns_defaults(self, tmp_path: Path) -> None:
        """Invalid .specbridge.yaml gracefully falls through to defaults."""
        project = tmp_path / "invalid-yaml"
        project.mkdir()
        cfg_path = project / ".specbridge.yaml"
        cfg_path.write_text(": invalid yaml [[[", encoding="utf-8")
        cfg = SpecbridgeConfig.load(str(project))
        assert cfg.min_confidence == 0.15  # default
        assert "docs" in cfg.spec_dirs

    def test_empty_yaml_returns_defaults(self, tmp_path: Path) -> None:
        """Empty .specbridge.yaml returns default config."""
        project = tmp_path / "empty-yaml"
        project.mkdir()
        cfg_path = project / ".specbridge.yaml"
        cfg_path.write_text("", encoding="utf-8")
        cfg = SpecbridgeConfig.load(str(project))
        assert cfg.min_confidence == 0.15

    def test_unknown_keys_ignored(self, tmp_path: Path) -> None:
        """Unknown keys in .specbridge.yaml are silently ignored."""
        project = tmp_path / "unknown-keys"
        project.mkdir()
        cfg_path = project / ".specbridge.yaml"
        cfg_path.write_text(
            "unknown_key: value\nanother_unknown: 42\n", encoding="utf-8"
        )
        cfg = SpecbridgeConfig.load(str(project))
        assert cfg.min_confidence == 0.15  # still default

    def test_wrong_value_types(self, tmp_path: Path) -> None:
        """Wrong value types fall back to defaults."""
        project = tmp_path / "wrong-types"
        project.mkdir()
        cfg_path = project / ".specbridge.yaml"
        cfg_path.write_text(
            "min_confidence: not_a_number\n"
            "max_output_nodes: also_not_a_number\n",
            encoding="utf-8",
        )
        cfg = SpecbridgeConfig.load(str(project))
        # Should use defaults when conversion fails
        assert isinstance(cfg.min_confidence, float)
        assert isinstance(cfg.max_output_nodes, int)

    def test_validation_reports_missing_dirs(self, tmp_path: Path) -> None:
        """Config validation reports missing spec/source directories."""
        from specbridge.cli import _validate_config

        project = tmp_path / "validate-missing"
        project.mkdir()
        cfg = SpecbridgeConfig(
            spec_dirs=["nonexistent-docs"],
            source_dirs=["nonexistent-src"],
        )
        issues = _validate_config(cfg, project)
        assert any("nonexistent-docs" in i for i in issues)
        assert any("nonexistent-src" in i for i in issues)

    def test_validation_out_of_range(self, tmp_path: Path) -> None:
        """Config validation catches out-of-range values."""
        from specbridge.cli import _validate_config

        project = tmp_path / "validate-range"
        project.mkdir()
        cfg = SpecbridgeConfig(
            spec_dirs=["docs"],
            source_dirs=["src"],
            min_confidence=5.0,  # out of range
            max_output_nodes=0,  # invalid
        )
        issues = _validate_config(cfg, project)
        assert any("5.0" in i for i in issues)
        assert any("0" in i for i in issues)
