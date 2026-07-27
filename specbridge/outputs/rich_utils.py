"""Rich console utilities for progress display and styled output."""

from __future__ import annotations

import contextlib
from collections.abc import Generator

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

_console = Console(stderr=True)


def get_console() -> Console:
    """Return the shared Rich Console instance (stderr by default)."""
    return _console


@contextlib.contextmanager
def progress_spinner(description: str = "Working...") -> Generator[Progress, None, None]:
    """Show an indeterminate spinner while a task runs.

    Usage::

        with progress_spinner("Scanning files...") as progress:
            # long operation
            result = do_work()
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=_console,
    ) as progress:
        progress.add_task(description=description, total=None)
        yield progress


@contextlib.contextmanager
def progress_bar(
    description: str = "Processing...",
    total: int = 100,
    transient: bool = True,
) -> Generator[tuple[Progress, TaskID], None, None]:
    """Show a determinate progress bar for a known number of steps.

    Usage::

        with progress_bar("Analyzing files...", total=len(files)) as (progress, task):
            for f in files:
                # process file
                progress.advance(task)
    """
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
        console=_console,
        transient=transient,
    ) as progress:
        task = progress.add_task(description=description, total=total)
        yield progress, task
