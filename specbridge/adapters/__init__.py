"""Adapter registry — re-exports from _base + eager-loads built-in adapters."""
from specbridge.adapters._base import ProjectAdapter, register, all_adapters, detect_adapter, detect_all, merge_graphs  # noqa: F401

# -- Eager-import adapters so their @register decorators fire --
# Order matters: heuristic is primary, spectra is optional extra
from specbridge.adapters import heuristic  # noqa: F401
from specbridge.adapters import spectra     # noqa: F401
