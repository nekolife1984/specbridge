"""Heuristic bridge: infer spec↔code relationships from structure alone.

No tags, no annotations — pure heuristics:
  - Directory name matching
  - File name matching
  - Symbol ↔ heading keyword overlap
  - Module ↔ test file proximity
"""

from __future__ import annotations

import os
import re
from pathlib import Path

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
from specbridge.discovery.code import CodeCandidate, discover_code
from specbridge.discovery.spec import SpecCandidate, discover_specs

# Weights for different heuristic signals
_W_DIRNAME = 0.6
_W_FILENAME = 0.4
_W_SYMBOL = 0.3
_W_KEYWORD = 0.2

# Minimum confidence to include an edge
_MIN_CONFIDENCE = 0.15

# Stopwords for keyword matching
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "is",
    "are", "was", "be", "has", "have", "do", "does", "should", "will",
    "with", "as", "at", "by", "from", "it", "its", "this", "that",
})


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase tokens, removing stopwords."""
    tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower()))
    return tokens - _STOPWORDS


def _dirname(file_path: str) -> str:
    """Get the immediate parent directory name."""
    return os.path.dirname(file_path).split("/")[0] if "/" in file_path else ""


def build_heuristic_graph(
    project_dir: str,
    *,
    specs: list[SpecCandidate] | None = None,
    codes: list[CodeCandidate] | None = None,
    spec_dirs: list[str] | None = None,
    source_dirs: list[str] | None = None,
) -> TraceGraph:
    """Build a TraceGraph using only structural heuristics.

    This is the PRIMARY entry point for the no-tag heuristic adapter.

    Pass pre-discovered *specs* and *codes* to avoid redundant re-discovery
    (used by drift detection which already has them).
    """
    graph = TraceGraph()

    # 1. Discover spec candidates (unless pre-provided)
    if specs is None:
        specs = discover_specs(project_dir, spec_dirs=spec_dirs)
    # 2. Discover code candidates (unless pre-provided)
    if codes is None:
        codes = discover_code(project_dir, source_dirs=source_dirs)

    # 3. Convert spec candidates → TraceNodes
    for sc in specs:
        node = TraceNode(
            id=sc.auto_id,
            type=NodeType.SPEC,
            title=sc.title or sc.heading_text,
            source=SourceRef(file=sc.file, line=sc.line),
            framework_origin="heuristic",
            confidence=0.8 if sc.auto_id else 0.5,
            metadata={"heading_depth": sc.heading_depth, "heading_text": sc.heading_text},
        )
        graph.add_node(node)

    # 4. Convert code candidates → TraceNodes
    for cc in codes:
        ntype = NodeType.TEST if cc.is_test else NodeType.CODE
        title = cc.file
        if cc.symbols:
            title = f"{cc.file} ({', '.join(cc.symbols[:3])})"
        node = TraceNode(
            id=cc.file,
            type=ntype,
            title=title,
            source=SourceRef(file=cc.file),
            framework_origin="heuristic",
            confidence=0.9,
            metadata={
                "module": cc.module,
                "symbols": cc.symbols,
                "language": cc.language,
                "imports": cc.imports,
                "line_count": cc.line_count,
            },
        )
        graph.add_node(node)

    # 5. Match specs ↔ code
    for sc in specs:
        spec_tokens = _tokenize(f"{sc.title} {sc.heading_text}")

        for cc in codes:
            conf, evidence = _score_edge(sc, cc, spec_tokens, project_dir)

            if conf < _MIN_CONFIDENCE:
                continue

            relation = EdgeRelation.VERIFIES if cc.is_test else EdgeRelation.IMPLEMENTS
            strength = EdgeStrength.WEAK if conf < 0.4 else EdgeStrength.INFERRED

            graph.add_edge(TraceEdge(
                src_id=cc.file,
                dst_id=sc.auto_id,
                relation=relation,
                strength=strength,
                evidence=evidence,
            ))

    return graph


def _score_edge(
    sc: SpecCandidate,
    cc: CodeCandidate,
    spec_tokens: set[str],
    project_dir: str,
) -> tuple[float, list[Evidence]]:
    """Compute heuristic confidence score between a spec and code candidate.

    Returns (confidence, list_of_evidence).
    """
    evidence: list[Evidence] = []
    total_weight = 0.0
    weighted_score = 0.0

    # --- Signal 1: Directory name matching ---
    spec_dir = _dirname(sc.file)
    code_dir = _dirname(cc.file)
    if spec_dir and code_dir and spec_dir == code_dir:
        weighted_score += _W_DIRNAME * 1.0
        evidence.append(Evidence(
            kind="heuristic:dirname",
            value=f"dir '{spec_dir}' matches",
            source=SourceRef(file=sc.file),
        ))
    elif spec_dir and code_dir:
        # Partial match: e.g. "auth" in "authentication"
        if spec_dir in code_dir or code_dir in spec_dir:
            weighted_score += _W_DIRNAME * 0.6
            evidence.append(Evidence(
                kind="heuristic:dirname",
                value=f"dir '{spec_dir}' ≈ '{code_dir}' (partial)",
                source=SourceRef(file=sc.file),
            ))
    total_weight += _W_DIRNAME

    # --- Signal 2: File name matching ---
    spec_stem = Path(sc.file).stem
    code_stem = Path(cc.file).stem
    if spec_stem.lower() == code_stem.lower():
        weighted_score += _W_FILENAME * 1.0
        evidence.append(Evidence(
            kind="heuristic:filename",
            value=f"basename '{spec_stem}' matches",
            source=SourceRef(file=sc.file),
        ))
    elif spec_stem.lower() in code_stem.lower() or code_stem.lower() in spec_stem.lower():
        weighted_score += _W_FILENAME * 0.5
        evidence.append(Evidence(
            kind="heuristic:filename",
            value=f"basename '{spec_stem}' ≈ '{code_stem}' (partial)",
            source=SourceRef(file=sc.file),
        ))
    total_weight += _W_FILENAME

    # --- Signal 3: Symbol ↔ heading keyword match ---
    code_keywords = _tokenize(f"{cc.file} {' '.join(cc.symbols)}")
    if spec_tokens and code_keywords:
        overlap = spec_tokens & code_keywords
        if overlap:
            jaccard = len(overlap) / len(spec_tokens | code_keywords)
            weighted_score += _W_SYMBOL * min(jaccard * 3, 1.0)
            evidence.append(Evidence(
                kind="heuristic:symbol",
                value=f"keyword overlap: {', '.join(sorted(overlap)[:5])}",
                source=SourceRef(file=cc.file),
            ))
    total_weight += _W_SYMBOL

    # --- Signal 4: Heading text ↔ file stem keyword match ---
    file_keywords = _tokenize(Path(cc.file).stem)
    if spec_tokens and file_keywords:
        overlap = spec_tokens & file_keywords
        if overlap:
            jaccard = len(overlap) / len(spec_tokens | file_keywords)
            weighted_score += _W_KEYWORD * min(jaccard * 3, 1.0)
            evidence.append(Evidence(
                kind="heuristic:keyword",
                value=f"keyword overlap: {', '.join(sorted(overlap)[:5])}",
                source=SourceRef(file=sc.file),
            ))
    total_weight += _W_KEYWORD

    if total_weight == 0:
        return 0.0, []

    confidence = weighted_score / total_weight
    return round(min(confidence, 1.0), 4), evidence
