"""spectra adapter: reads .spectra/trace-mapping.yaml + @impl / <!-- @spec --> tags.

This adapter is **read-only** — it never writes to the project.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from specbridge.adapters._base import ProjectAdapter, register
from specbridge.core import (
    EdgeRelation,
    EdgeStrength,
    Evidence,
    NodeType,
    SourceRef,
    TraceEdge,
    TraceGraph,
    TraceNode,
)
from specbridge.core.extract import extract_tags_from_file


_TRACE_MAPPING_RELPATH = ".spectra/trace-mapping.yaml"

# Language profiles: line-comment character per extension
_SLASH_LANG_EXT = frozenset({
    ".c", ".h", ".cpp", ".hpp", ".cs",
    ".ts", ".tsx", ".js", ".jsx",
    ".go", ".rs", ".kt", ".swift",
    ".java", ".scala",
})
_HASH_LANG_EXT = frozenset({".py", ".rb", ".sh", ".bash", ".zsh"})
_SOURCE_EXT = _SLASH_LANG_EXT | _HASH_LANG_EXT | {".yaml", ".yml", ".toml", ".json"}


@register
class SpectraAdapter(ProjectAdapter):

    def detect(self, directory: str) -> float:
        root = Path(directory).resolve()
        tm = root / _TRACE_MAPPING_RELPATH
        if tm.exists():
            return 0.95
        # Quick scan for @impl tags without full analysis
        for ext in _SOURCE_EXT:
            tagged = list(root.rglob(f"*{ext}"))
            if any(f.is_file() and "@impl" in f.read_text(encoding="utf-8", errors="ignore")
                   for f in tagged):
                return 0.7
        # If .spectra/ directory exists, might still be spectra
        if (root / ".spectra").exists():
            return 0.5
        return 0.0

    def analyze(self, directory: str) -> TraceGraph:
        graph = TraceGraph()
        root = Path(directory).resolve()

        self._load_trace_mapping(root, graph)
        self._scan_code_tags(root, graph)
        self._scan_spec_tags(root, graph)

        return graph

    # ── private helpers ──────────────────────────────────────

    def _load_trace_mapping(self, root: Path, graph: TraceGraph) -> None:
        tm = root / _TRACE_MAPPING_RELPATH
        if not tm.exists():
            return

        try:
            data = yaml.safe_load(tm.read_text(encoding="utf-8"))
        except Exception:
            return

        for entry in data.get("mappings", []):
            mid = entry.get("id", "")
            if not mid:
                continue

            # spec node (if a spec path is given)
            spec_path = entry.get("spec", "")
            if spec_path:
                spec_node = TraceNode(
                    id=mid,
                    type=NodeType.SPEC,
                    title=entry.get("description", mid),
                    source=SourceRef(file=spec_path),
                    framework_origin="spectra",
                    confidence=0.9 if "@spec" in entry.get("tags", []) else 0.7,
                )
                graph.add_node(spec_node)

            # code nodes
            code_info = entry.get("code", {})
            for cf in code_info.get("files", []):
                syms = code_info.get("symbols", [])
                cid = f"{mid}::{cf}"
                code_node = TraceNode(
                    id=cid,
                    type=NodeType.CODE,
                    title=f"{' '.join(syms)}" if syms else cf,
                    source=SourceRef(file=cf),
                    framework_origin="spectra",
                    confidence=0.9,
                )
                graph.add_node(code_node)

                # edge: code → spec
                graph.add_edge(TraceEdge(
                    src_id=cid,
                    dst_id=mid,
                    relation=EdgeRelation.IMPLEMENTS,
                    strength=EdgeStrength.EXPLICIT,
                    evidence=[Evidence(
                        kind="mapping",
                        value=f".spectra/trace-mapping.yaml id={mid}",
                        source=SourceRef(file=str(tm.relative_to(root))),
                    )],
                ))

    def _scan_code_tags(self, root: Path, graph: TraceGraph) -> None:
        """Scan source files for @impl / @verifies / @module / @feature."""
        for suffix in _SOURCE_EXT:
            for fpath in root.rglob(f"*{suffix}"):
                if any(part.startswith((".", "__")) or part in {
                    "node_modules", ".venv", "__pycache__", "dist", "build",
                } for part in fpath.parts):
                    continue
                tags = extract_tags_from_file(fpath, root)
                for tag in tags:
                    if tag.kind == "impl":
                        for impl_id in re.split(r"[,，]\s*", tag.value.strip()):
                            impl_id = impl_id.strip()
                            if not impl_id:
                                continue
                            nid = f"{impl_id}::{tag.file}"
                            node = TraceNode(
                                id=nid,
                                type=NodeType.CODE,
                                title=tag.file,
                                source=SourceRef(file=tag.file, line=tag.line),
                                framework_origin="spectra",
                                confidence=0.9,
                            )
                            graph.add_node(node)
                            graph.add_edge(TraceEdge(
                                src_id=nid,
                                dst_id=impl_id,
                                relation=EdgeRelation.IMPLEMENTS,
                                strength=EdgeStrength.EXPLICIT,
                                evidence=[Evidence(
                                    kind="tag:impl",
                                    value=impl_id,
                                    source=SourceRef(file=tag.file, line=tag.line),
                                )],
                            ))
                    elif tag.kind == "verifies":
                        for vid in tag.value.split(","):
                            vid = vid.strip()
                            if not vid:
                                continue
                            nid = f"test-{vid}::{tag.file}"
                            node = TraceNode(
                                id=nid,
                                type=NodeType.TEST,
                                title=tag.file,
                                source=SourceRef(file=tag.file, line=tag.line),
                                framework_origin="spectra",
                                confidence=0.85,
                            )
                            graph.add_node(node)
                            graph.add_edge(TraceEdge(
                                src_id=nid,
                                dst_id=vid,
                                relation=EdgeRelation.VERIFIES,
                                strength=EdgeStrength.EXPLICIT,
                                evidence=[Evidence(
                                    kind="tag:verifies",
                                    value=vid,
                                    source=SourceRef(file=tag.file, line=tag.line),
                                )],
                            ))

    def _scan_spec_tags(self, root: Path, graph: TraceGraph) -> None:
        """Scan spec docs for <!-- @spec -->, <!-- @design -->, <!-- @satisfies -->, _Boundary:_."""
        for fpath in root.rglob("*.md"):
            if any(part.startswith((".", "__")) or part in {
                "node_modules", ".venv", "dist", "build",
            } for part in fpath.parts):
                continue
            tags = extract_tags_from_file(fpath, root)

            # Group boundary markers by spec ID context
            current_spec_id: str | None = None

            for tag in tags:
                if tag.kind == "spec":
                    current_spec_id = f"spec::{tag.value}"
                    nid = current_spec_id
                    node = TraceNode(
                        id=nid,
                        type=NodeType.SPEC,
                        title=f"Spec {tag.value}",
                        source=SourceRef(file=tag.file, line=tag.line),
                        framework_origin="spectra",
                        confidence=0.95,
                    )
                    graph.add_node(node)
                elif tag.kind == "satisfies":
                    for sid in tag.value.split(","):
                        sid = sid.strip()
                        if not sid:
                            continue
                        # design → spec edge
                        design_id = f"design::{tag.value}::{tag.file}"
                        ds_node = TraceNode(
                            id=design_id,
                            type=NodeType.DESIGN,
                            title=f"Design @{tag.value}",
                            source=SourceRef(file=tag.file, line=tag.line),
                            framework_origin="spectra",
                            confidence=0.8,
                        )
                        graph.add_node(ds_node)
                        graph.add_edge(TraceEdge(
                            src_id=design_id,
                            dst_id=f"spec::{sid}",
                            relation=EdgeRelation.SATISFIES,
                            strength=EdgeStrength.EXPLICIT,
                            evidence=[Evidence(
                                kind="tag:satisfies",
                                value=sid,
                                source=SourceRef(file=tag.file, line=tag.line),
                            )],
                        ))
                elif tag.kind == "boundary" and current_spec_id:
                    # Store boundary in the current spec's metadata
                    spec_node = graph.nodes.get(current_spec_id)
                    if spec_node:
                        boundaries = spec_node.metadata.setdefault("boundaries", [])
                        boundaries.append({
                            "path": tag.value,
                            "file": tag.file,
                            "line": tag.line,
                        })
