"""Specbridge configuration — read from .specbridge.yaml or pyproject.toml.

Configuration search order:
  1. .specbridge.yaml in project root
  2. [tool.specbridge] section in pyproject.toml
  3. Defaults (hardcoded)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


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


@dataclass
class SpecbridgeConfig:
    """Project-level configuration for specbridge."""
    spec_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_SPEC_DIRS))
    source_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCE_DIRS))
    exclude_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDE_DIRS))
    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    max_output_nodes: int = DEFAULT_MAX_OUTPUT_NODES

    @classmethod
    def load(cls, project_dir: str | Path) -> SpecbridgeConfig:
        """Load config from project directory, falling back to defaults."""
        root = Path(project_dir).resolve()

        # 1. Try .specbridge.yaml
        yaml_path = root / ".specbridge.yaml"
        if yaml_path.exists():
            return cls._from_yaml(yaml_path)

        # 2. Try pyproject.toml
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            return cls._from_pyproject(pyproject)

        # 3. Defaults
        return cls()

    @classmethod
    def _from_yaml(cls, path: Path) -> SpecbridgeConfig:
        """Parse .specbridge.yaml into config."""
        try:
            import yaml
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        return cls._from_dict(data or {})

    @classmethod
    def _from_pyproject(cls, path: Path) -> SpecbridgeConfig:
        """Parse [tool.specbridge] from pyproject.toml."""
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # backport
            except ImportError:
                return cls()
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            data = data.get("tool", {}).get("specbridge", {})
        except Exception:
            return cls()
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> SpecbridgeConfig:
        """Convert parsed dict to config, merging with defaults."""
        return cls(
            spec_dirs=data.get("spec_dirs", list(DEFAULT_SPEC_DIRS)),
            source_dirs=data.get("source_dirs", list(DEFAULT_SOURCE_DIRS)),
            exclude_dirs=set(data.get("exclude_dirs", list(DEFAULT_EXCLUDE_DIRS))),
            min_confidence=float(data.get("min_confidence", DEFAULT_MIN_CONFIDENCE)),
            max_output_nodes=int(data.get("max_output_nodes", DEFAULT_MAX_OUTPUT_NODES)),
        )
