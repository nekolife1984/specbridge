"""Adapter registry — re-exports from _base + eager-loads built-in adapters."""
# -- Eager-import adapters so their @register decorators fire --
# Order matters: heuristic is primary, spectra is optional extra
from specbridge.adapters import (
    heuristic,  # noqa: F401
    spectra,  # noqa: F401
)
from specbridge.adapters._base import (  # noqa: F401
    ProjectAdapter,
    all_adapters,
    detect_adapter,
    detect_all,
    discover_plugins,
    merge_graphs,
    plugin_adapters,
    register,
)

__all__ = [
    "ProjectAdapter",
    "all_adapters",
    "detect_adapter",
    "detect_all",
    "discover_plugins",
    "merge_graphs",
    "plugin_adapters",
    "register",
    "heuristic",
    "spectra",
]
