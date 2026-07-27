"""Fast recursive file scanner using os.scandir.

Replaces multiple rglob() calls with a single directory walk,
skipping excluded directories at the directory level (not per-file).
"""

from __future__ import annotations

import os
from pathlib import Path


def walk_files(
    root: Path,
    extensions: set[str],
    exclude_dirs: set[str] | None = None,
    exclude_prefixes: tuple[str, ...] = (),
) -> list[Path]:
    """Recursively walk *root* using ``os.scandir`` and return sorted file paths.

    Unlike multiple ``rglob()`` calls (one per extension), this does a **single**
    directory walk and checks each file's extension against *extensions*.

    Excluded directories are skipped at the directory level (not re-checked per
    file), which makes this significantly faster than ``rglob`` + per-file exclude
    on large projects.

    Args:
        root: Directory to scan.
        extensions: Set of file extensions to include (e.g. ``{".py", ".ts"}``).
        exclude_dirs: Directory names to skip entirely.
        exclude_prefixes: File name prefixes to skip (e.g. ``(".",)`` for dotfiles).

    Returns:
        Sorted list of file :class:`Path` objects.
    """
    if exclude_dirs is None:
        exclude_dirs = set()

    result: list[Path] = []
    # Use a stack for iterative DFS (avoids recursion depth limits)
    stack: list[Path] = [root]

    while stack:
        path = stack.pop()
        try:
            scandir_iter = os.scandir(path)
        except PermissionError:
            continue
        dirs: list[Path] = []
        files: list[Path] = []
        with scandir_iter as entries:
            for entry in entries:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                except OSError:
                    continue
                name = entry.name
                if is_dir:
                    if not name.startswith(".") and name not in exclude_dirs:
                        dirs.append(Path(entry.path))
                elif is_file:
                    if exclude_prefixes and name.startswith(exclude_prefixes):
                        continue
                    ext = Path(name).suffix
                    if ext in extensions:
                        files.append(Path(entry.path))
        # Add dirs in reverse order so they're processed in sorted order
        # (stack is LIFO)
        for d in sorted(dirs, reverse=True):
            stack.append(d)
        result.extend(sorted(files))

    return result
