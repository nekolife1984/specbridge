"""Read-only guards — keep specbridge from writing outside its management dir."""

from __future__ import annotations

from pathlib import Path
from typing import Union


ALLOWED_WRITE_DIR = ".specbridge"
ALLOWED_WRITE_DIRS = {ALLOWED_WRITE_DIR, ".specbridge"}


def validate_write_path(
    target_path: Union[str, Path],
    project_root: Union[str, Path],
) -> Path:
    """Validate that *target_path* is inside the allowed write directory.

    Returns the resolved absolute path if valid.
    Raises PermissionError if path would write outside .specbridge/.
    """
    root = Path(project_root).resolve()
    target = Path(target_path).resolve()

    # Allow writes anywhere inside .specbridge/
    allowed = root / ALLOWED_WRITE_DIR
    try:
        target.relative_to(allowed)
        return target
    except ValueError:
        pass

    # Check against protected spec/source directories
    spec_dirs = {root / d for d in ["docs", "spec", "specs"]}
    source_dirs = {root / d for d in ["src", "lib", "app", "tests"]}

    for forbidden in spec_dirs | source_dirs:
        try:
            target.relative_to(forbidden)
            raise PermissionError(
                f"Write blocked: {target} is inside '{forbidden.name}/' which "
                f"is a protected spec or source directory. "
                f"specbridge is read-only and only writes to .specbridge/."
            )
        except ValueError:
            continue

    # If outside project root entirely, also block
    try:
        target.relative_to(root)
    except ValueError:
        raise PermissionError(
            f"Write blocked: {target} is outside the project root {root}. "
            f"specbridge only writes to .specbridge/ within the project."
        )

    # Inside project root but not in .specbridge/ — still block
    raise PermissionError(
        f"Write blocked: {target} is not inside {allowed}. "
        f"specbridge is read-only and only writes to .specbridge/."
    )
