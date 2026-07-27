"""File-hash cache for skipping unchanged files during repeated scans.

Stores a JSON cache in .specbridge/cache.json that maps file paths to
their SHA256 content hash and modification time.  On subsequent runs,
files whose mtime and hash match the cache are skipped.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CACHE_RELPATH = ".specbridge/cache.json"

# Default exclude patterns (merged with per-call excludes)
DEFAULT_EXCLUDES: set[str] = {
    ".git", "node_modules", ".venv", "__pycache__", "dist", "build",
    ".spectra", ".specbridge", ".artgraph", ".trace",
    "venv", "env", ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".egg-info", "site-packages", "coverage", "htmlcov",
}


def _file_hash(path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _should_exclude(rel_path: str, exclude_dirs: set[str]) -> bool:
    """Check if a relative path falls under any excluded directory."""
    parts = rel_path.replace("\\", "/").split("/")
    return any(part in exclude_dirs for part in parts)


# ── Public API ──────────────────────────────────────────────


def load_cache(project_dir: str | Path) -> dict[str, Any]:
    """Load the cache file, returning an empty dict if missing or corrupt."""
    path = Path(project_dir).resolve() / CACHE_RELPATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(project_dir: str | Path, cache: dict[str, Any]) -> None:
    """Persist the cache to .specbridge/cache.json."""
    from specbridge.guard import validate_write_path

    path = Path(project_dir).resolve() / CACHE_RELPATH
    validate_write_path(path, Path(project_dir).resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def resolved_file_list(
    directory: str,
    extensions: set[str],
    *,
    source_dirs: list[str] | None = None,
    exclude_dirs: set[str] | None = None,
) -> list[str]:
    """Walk *directory* for files matching *extensions* and return relative paths.

    Used by both spec discovery and code discovery to get the list of files
    before checking the cache.
    """
    root = Path(directory).resolve()
    excludes = (exclude_dirs or set()) | DEFAULT_EXCLUDES
    dirs_to_scan = source_dirs or ["."]
    files: list[str] = []

    for sd in dirs_to_scan:
        scan_dir = root / sd
        if not scan_dir.exists():
            continue
        for f in sorted(scan_dir.rglob("*")):
            if not f.is_file():
                continue
            rel = str(f.relative_to(root))
            if _should_exclude(rel, excludes):
                continue
            if f.suffix.lower() in extensions:
                files.append(rel)

    return files


def filter_cached(
    project_dir: str | Path,
    files: list[str],
) -> tuple[list[str], dict[str, Any]]:
    """Filter *files* to only those whose content has changed since the cache.

    Returns ``(changed_files, updated_cache)`` where *updated_cache* is a
    dict of ``{rel_path: {"hash": ..., "mtime": ...}}`` that should be
    merged into the persistent cache after processing.
    """
    root = Path(project_dir).resolve()
    cache = load_cache(str(root))
    changed: list[str] = []
    updated: dict[str, Any] = {}

    for rel in files:
        full = root / rel
        try:
            st = full.stat()
            mtime = int(st.st_mtime)
            cached_entry = cache.get(rel)
            # Quick mtime check first — if unchanged, skip hash
            if cached_entry and cached_entry.get("mtime") == mtime:
                continue
            # Hash check for reliability
            h = _file_hash(full)
            if cached_entry and cached_entry.get("hash") == h:
                # mtime changed but content didn't — update mtime in-place
                updated[rel] = {"hash": h, "mtime": mtime}
                continue
        except (OSError, FileNotFoundError):
            # File disappeared — treat as changed so discovery handles it
            changed.append(rel)
            continue

        changed.append(rel)
        updated[rel] = {"hash": h, "mtime": mtime}

    return changed, updated


def clear_cache(project_dir: str | Path) -> None:
    """Remove the cache file (e.g. after config changes that invalidate everything)."""
    path = Path(project_dir).resolve() / CACHE_RELPATH
    if path.exists():
        path.unlink()
