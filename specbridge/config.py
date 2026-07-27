"""Specbridge configuration — read from .specbridge.yaml or pyproject.toml.

Configuration search order:
  1. .specbridge.yaml in project root
  2. [tool.specbridge] section in pyproject.toml
  3. Defaults (hardcoded)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_SPEC_DIRS = ["docs", "spec", "specs"]
DEFAULT_SOURCE_DIRS = ["src", "lib", "app"]
DEFAULT_EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "__pycache__", "dist", "build",
    ".spectra", ".specbridge", ".artgraph", ".trace",
    "venv", "env", ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".egg-info", "site-packages", "coverage", "htmlcov",
}
DEFAULT_MIN_CONFIDENCE = 0.15
DEFAULT_MAX_OUTPUT_NODES = 20  # truncation limit for --top
DEFAULT_MIN_COVERAGE = 50.0  # minimum coverage percentage for --gate


@dataclass
class SpecbridgeConfig:
    """Project-level configuration for specbridge."""
    spec_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_SPEC_DIRS))
    source_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCE_DIRS))
    exclude_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDE_DIRS))
    spec_files: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    max_output_nodes: int = DEFAULT_MAX_OUTPUT_NODES
    min_coverage: float = DEFAULT_MIN_COVERAGE

    @classmethod
    def load(cls, project_dir: str | Path, config_path: str | Path | None = None) -> SpecbridgeConfig:
        """Load config from project directory, merging from multiple sources.

        When *config_path* is provided, reads ONLY that file and skips automatic
        discovery of .specbridge.yaml / pyproject.toml.

        Resolution order when *config_path* is None (later sources override earlier ones):
          1. Defaults (hardcoded)
          2. pyproject.toml  [tool.specbridge]
          3. .specbridge.yaml (overrides pyproject)
        """
        root = Path(project_dir).resolve()

        # If an explicit config path was given, load only that file
        if config_path is not None:
            explicit = Path(config_path)
            if not explicit.exists():
                raise FileNotFoundError(
                    f"Config file not found: {explicit}\n"
                    f"  Provide a valid path with --config or remove the option to use "
                    f"auto-discovered .specbridge.yaml / pyproject.toml."
                )
            data = cls._try_read_yaml(explicit)
            if data is None:
                raise ValueError(
                    f"Could not parse config file: {explicit}\n"
                    f"  Ensure the file is valid YAML with specbridge keys "
                    f"(e.g. spec_dirs, source_dirs)."
                )
            return cls._merge_dict(cls(), data)

        # Auto-discovery mode
        config = cls()

        # 1. Try pyproject.toml as base
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            data = cls._try_read_pyproject(pyproject)
            if data:
                config = cls._merge_dict(config, data)

        # 2. Try .specbridge.yaml as override
        yaml_path = root / ".specbridge.yaml"
        if yaml_path.exists():
            data = cls._try_read_yaml(yaml_path)
            if data:
                config = cls._merge_dict(config, data)

        return config

    @classmethod
    def _try_read_yaml(cls, path: Path) -> dict[str, Any] | None:
        """Read .specbridge.yaml, returning None on error."""
        try:
            import yaml
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return data or None
        except Exception:
            return None

    @classmethod
    def _try_read_pyproject(cls, path: Path) -> dict[str, Any] | None:
        """Read [tool.specbridge] from pyproject.toml, returning None on error."""
        try:
            import tomllib  # type: ignore[import-not-found]  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # backport
            except ImportError:
                return None
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            specbridge_data = data.get("tool", {}).get("specbridge", {})
            return specbridge_data if specbridge_data else None
        except Exception:
            return None

    @classmethod
    def _merge_dict(cls, base: SpecbridgeConfig, overrides: dict[str, Any]) -> SpecbridgeConfig:
        """Merge a dict of overrides into an existing config, keeping unspecified fields."""
        def _safe_float(v: Any, default: float) -> float:
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        def _safe_int(v: Any, default: int) -> int:
            try:
                return int(v)
            except (ValueError, TypeError):
                return default

        return cls(
            spec_dirs=overrides.get("spec_dirs", base.spec_dirs),
            source_dirs=overrides.get("source_dirs", base.source_dirs),
            exclude_dirs=set(overrides.get("exclude_dirs", list(base.exclude_dirs))),
            spec_files=overrides.get("spec_files", base.spec_files),
            source_files=overrides.get("source_files", base.source_files),
            min_confidence=_safe_float(overrides.get("min_confidence"), base.min_confidence),
            max_output_nodes=_safe_int(overrides.get("max_output_nodes"), base.max_output_nodes),
            min_coverage=_safe_float(overrides.get("min_coverage"), base.min_coverage),
        )
