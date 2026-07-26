"""Heuristic adapter: pure structural analysis, no tags required.

This is the PRIMARY adapter for specbridge. It works on ANY project
that has Markdown specs (in docs/ or spec/ or specs/) and source code
(in src/ or lib/ or app/).

Tag-based adapters (spectra, cc-sdd) are OPTIONAL extras that run
on top of this to add EXPLICIT edges when annotations exist.
"""

from __future__ import annotations

from pathlib import Path

from specbridge.adapters._base import ProjectAdapter, register
from specbridge.infer import build_heuristic_graph


@register
class HeuristicAdapter(ProjectAdapter):
    """Detect spec↔code relationships using structure + heuristics only.

    Confidence > 0.0 for any project that has both a docs/ (or spec/)
    directory and a src/ (or lib/ or app/) directory.
    """

    def detect(self, directory: str) -> float:
        root = Path(directory).resolve()

        # Check for spec directories
        has_specs = any((root / d).exists() for d in ["docs", "spec", "specs"])
        # Check for source directories
        has_code = any((root / d).exists() for d in ["src", "lib", "app"])

        if has_specs and has_code:
            return 0.8
        if has_specs or has_code:
            return 0.4
        return 0.0

    def analyze(self, directory: str) -> "TraceGraph":
        from specbridge.infer import build_heuristic_graph
        return build_heuristic_graph(directory)
