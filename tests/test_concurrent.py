"""Concurrent access tests: snapshot read/write during analysis.

Verifies specbridge handles concurrent operations without data corruption.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from specbridge.analyzers.drift import build_snapshot, compute_drift, save_snapshot
from specbridge.adapters._base import detect_adapter


class TestConcurrentSnapshot:
    """Concurrent snapshot save/load during analysis."""

    @pytest.fixture(scope="module")
    def project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        root = tmp_path_factory.mktemp("concurrent-project")
        docs = root / "docs"
        docs.mkdir()
        src = root / "src"
        src.mkdir()

        for i in range(20):
            (docs / f"spec_{i}.md").write_text(
                f"# Spec {i}\n\nContent for spec {i}.\n",
                encoding="utf-8",
            )
            (src / f"handler_{i}.py").write_text(
                f"def handle_{i}(): return {i}\n",
                encoding="utf-8",
            )

        return root

    def test_concurrent_snapshot_save(self, project: Path) -> None:
        """Multiple snapshot saves don't corrupt each other."""
        results: list[Exception | None] = [None] * 5

        def _save(idx: int) -> None:
            try:
                snap = build_snapshot(str(project))
                save_snapshot(snap, str(project))
            except Exception as e:
                results[idx] = e

        threads = [threading.Thread(target=_save, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # None should have errored
        for i, r in enumerate(results):
            assert r is None, f"Thread {i} failed: {r}"

    def test_concurrent_analysis_and_snapshot(self, project: Path) -> None:
        """Analysis while snapshot is being taken doesn't crash."""
        errors: list[Exception | None] = [None] * 4

        def _analyze(idx: int) -> None:
            try:
                adapter = detect_adapter(str(project))
                if adapter:
                    adapter.analyze(str(project))
            except Exception as e:
                errors[idx] = e

        def _snapshot(idx: int) -> None:
            try:
                snap = build_snapshot(str(project))
                compute_drift(snap, str(project))
            except Exception as e:
                errors[idx] = e

        threads = [
            threading.Thread(target=_analyze, args=(0,)),
            threading.Thread(target=_analyze, args=(1,)),
            threading.Thread(target=_snapshot, args=(2,)),
            threading.Thread(target=_snapshot, args=(3,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i, r in enumerate(errors):
            assert r is None, f"Thread {i} failed: {r}"
