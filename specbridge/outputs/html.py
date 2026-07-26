"""Interactive HTML graph output using D3.js force-directed layout."""

from __future__ import annotations

import json
from typing import Any

from specbridge.core import NodeType, TraceGraph

NODE_COLORS = {
    NodeType.SPEC: "#4A90D9",
    NodeType.CODE: "#50B86C",
    NodeType.TEST: "#F5A623",
    NodeType.DESIGN: "#9B59B6",
    NodeType.TASK: "#7F8C8D",
}

NODE_SHAPES = {
    NodeType.SPEC: "rect",
    NodeType.CODE: "circle",
    NodeType.TEST: "diamond",
    NodeType.DESIGN: "triangle",
    NodeType.TASK: "circle",
}

COLORS_CSS = {
    NodeType.SPEC: "#1a73e8",
    NodeType.CODE: "#34a853",
    NodeType.TEST: "#fbbc04",
    NodeType.DESIGN: "#9c27b0",
    NodeType.TASK: "#607d8b",
}


def _graph_data(graph: TraceGraph) -> dict:
    """Convert TraceGraph to JSON-compatible dict for D3."""
    nodes = []
    for nid, node in graph.nodes.items():
        color = COLORS_CSS.get(node.type, "#999")
        nodes.append({
            "id": nid,
            "label": node.title if len(node.title) < 60 else node.title[:57] + "...",
            "type": node.type.value,
            "color": color,
            "file": node.source.file or "",
            "framework": node.framework_origin,
            "confidence": node.confidence,
        })

    edges = []
    for e in graph.edges:
        edges.append({
            "source": e.src_id,
            "target": e.dst_id,
            "relation": e.relation.value,
            "strength": e.strength.value,
        })

    return {"nodes": nodes, "edges": edges}


def render_html(graph: TraceGraph) -> str:
    """Render the trace graph as a self-contained interactive HTML page.

    Uses D3.js force-directed layout with:
    - Color-coded nodes by type
    - Arrow-directed edges with relation labels
    - Interactive hover/click/tooltip
    - Zoom and pan
    - Legend
    """
    data = _graph_data(graph)
    data_json = json.dumps(data, indent=2)

    summary = {
        "specs": len(graph.nodes_by_type(NodeType.SPEC)),
        "codes": len(graph.nodes_by_type(NodeType.CODE)),
        "tests": len(graph.nodes_by_type(NodeType.TEST)),
        "designs": len(graph.nodes_by_type(NodeType.DESIGN)),
        "edges": len(graph.edges),
    }
    summary_json = json.dumps(summary)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>specbridge — Trace Graph</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; overflow: hidden; }}
  #header {{ position: fixed; top: 0; left: 0; right: 0; z-index: 100; padding: 12px 20px; background: rgba(26,26,46,0.9); backdrop-filter: blur(8px); border-bottom: 1px solid #333; display: flex; align-items: center; gap: 16px; }}
  #header h1 {{ font-size: 18px; font-weight: 600; }}
  #header .stats {{ font-size: 13px; color: #aaa; }}
  #header .stats span {{ margin-right: 12px; }}
  #legend {{ position: fixed; bottom: 20px; left: 20px; z-index: 100; background: rgba(0,0,0,0.7); padding: 10px 14px; border-radius: 8px; font-size: 12px; }}
  #legend div {{ display: flex; align-items: center; gap: 6px; margin: 3px 0; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
  .rect-dot {{ width: 10px; height: 10px; display: inline-block; }}
  #tooltip {{ position: fixed; display: none; background: rgba(0,0,0,0.85); padding: 8px 12px; border-radius: 6px; font-size: 12px; pointer-events: none; z-index: 200; max-width: 280px; border: 1px solid #555; }}
  #tooltip .tt-label {{ font-weight: 600; font-size: 13px; }}
  #tooltip .tt-detail {{ color: #aaa; margin-top: 2px; }}
  svg {{ width: 100vw; height: 100vh; }}
  .edge {{ stroke: #555; stroke-width: 1.5; fill: none; }}
  .edge-label {{ font-size: 9px; fill: #888; }}
  .node {{ cursor: pointer; transition: opacity 0.15s; }}
  .node:hover {{ opacity: 0.8; }}
  .node-label {{ font-size: 10px; fill: #ccc; pointer-events: none; }}
  .glow {{ filter: drop-shadow(0 0 6px rgba(255,255,255,0.3)); }}
</style>
</head>
<body>
<div id="header">
  <h1>🔍 specbridge</h1>
  <div class="stats" id="stats">Loading...</div>
</div>
<div id="legend"></div>
<div id="tooltip"></div>
<svg id="graph"></svg>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const data = {data_json};
const summary = {summary_json};

document.getElementById('stats').innerHTML =
  '<span>📄 ' + summary.specs + ' specs</span>' +
  '<span>📁 ' + summary.codes + ' code</span>' +
  '<span>🧪 ' + summary.tests + ' tests</span>' +
  '<span>🔗 ' + summary.edges + ' edges</span>';

const legendEl = document.getElementById('legend');
const types = [
  {{ type: 'spec', label: 'Spec', color: '#1a73e8' }},
  {{ type: 'code', label: 'Code', color: '#34a853' }},
  {{ type: 'test', label: 'Test', color: '#fbbc04' }},
  {{ type: 'design', label: 'Design', color: '#9c27b0' }},
];
types.forEach(t => {{
  const d = document.createElement('div');
  d.innerHTML = '<span class="dot" style="background:' + t.color + '"></span> ' + t.label;
  legendEl.appendChild(d);
}});

// D3 force-directed graph
const width = window.innerWidth;
const height = window.innerHeight;
const svg = d3.select('#graph');

// Define arrow markers per relation type
const defs = svg.append('defs');
['implements', 'verifies', 'satisfies', 'depends', 'references'].forEach(r => {{
  defs.append('marker')
    .attr('id', 'arrow-' + r)
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 20)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#777');
}});

const g = svg.append('g');

// Zoom
svg.call(d3.zoom().scaleExtent([0.1, 4]).on('zoom', (event) => {{
  g.attr('transform', event.transform);
}}));

// Build graph
const nodes = data.nodes.map(d => Object.assign({{}}, d));
const nodeMap = new Map(nodes.map(d => [d.id, d]));
const edges = data.edges.map(d => Object.assign({{}}, d));

const simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(edges).id(d => d.id).distance(120))
  .force('charge', d3.forceManyBody().strength(-300))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collision', d3.forceCollide(30));

// Draw edges
const link = g.append('g').selectAll('line')
  .data(edges).join('line')
  .attr('class', 'edge')
  .attr('marker-end', d => 'url(#arrow-' + d.relation + ')');

// Edge labels
const edgeLabel = g.append('g').selectAll('text')
  .data(edges).join('text')
  .attr('class', 'edge-label')
  .text(d => d.relation);

// Draw nodes
const nodeGroup = g.append('g').selectAll('g')
  .data(nodes).join('g')
  .attr('class', 'node')
  .call(d3.drag()
    .on('start', (event, d) => {{
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }})
    .on('drag', (event, d) => {{
      d.fx = event.x;
      d.fy = event.y;
    }})
    .on('end', (event, d) => {{
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }}));

// Node shapes
nodeGroup.each(function(d) {{
  const el = d3.select(this);
  const r = 6;
  if (d.type === 'spec') {{
    el.append('rect').attr('width', 14).attr('height', 14).attr('x', -7).attr('y', -7).attr('rx', 2).attr('fill', d.color);
  }} else if (d.type === 'test') {{
    el.append('polygon').attr('points', '0,-9 9,0 0,9 -9,0').attr('fill', d.color);
  }} else if (d.type === 'design') {{
    el.append('polygon').attr('points', '0,-9 9,6 -9,6').attr('fill', d.color);
  }} else {{
    el.append('circle').attr('r', r).attr('fill', d.color);
  }}
}});

// Node labels
nodeGroup.append('text')
  .attr('class', 'node-label')
  .attr('dx', 10)
  .attr('dy', 3)
  .text(d => d.label);

// Tooltip
nodeGroup.on('mouseover', (event, d) => {{
  const tt = document.getElementById('tooltip');
  tt.style.display = 'block';
  tt.style.left = (event.clientX + 12) + 'px';
  tt.style.top = (event.clientY - 10) + 'px';
  tt.innerHTML = '<div class="tt-label">' + d.label + '</div>' +
    '<div class="tt-detail">ID: ' + d.id + '</div>' +
    '<div class="tt-detail">Type: ' + d.type + '</div>' +
    '<div class="tt-detail">File: ' + d.file + '</div>' +
    '<div class="tt-detail">Framework: ' + d.framework + '</div>';
}})
.on('mousemove', (event) => {{
  const tt = document.getElementById('tooltip');
  tt.style.left = (event.clientX + 12) + 'px';
  tt.style.top = (event.clientY - 10) + 'px';
}})
.on('mouseout', () => {{
  document.getElementById('tooltip').style.display = 'none';
}});

// Highlight connections on click
nodeGroup.on('click', (event, d) => {{
  const connected = new Set();
  connected.add(d.id);
  data.edges.forEach(e => {{
    if (e.source === d.id || (typeof e.source === 'object' && e.source.id === d.id))
      connected.add(typeof e.target === 'object' ? e.target.id : e.target);
    if (e.target === d.id || (typeof e.target === 'object' && e.target.id === d.id))
      connected.add(typeof e.source === 'object' ? e.source.id : e.source);
  }});
  nodeGroup.attr('opacity', n => connected.has(n.id) ? 1 : 0.15);
  link.attr('opacity', e => {{
    const s = typeof e.source === 'object' ? e.source.id : e.source;
    const t = typeof e.target === 'object' ? e.target.id : e.target;
    return (s === d.id || t === d.id) ? 1 : 0.08;
  }});
  edgeLabel.attr('opacity', e => {{
    const s = typeof e.source === 'object' ? e.source.id : e.source;
    const t = typeof e.target === 'object' ? e.target.id ? e.target.id : e.target : e.target;
    return (s === d.id || t === d.id) ? 1 : 0.05;
  }});
}});

// Reset on background click
svg.on('click', (event) => {{
  if (event.target === svg.node()) {{
    nodeGroup.attr('opacity', 1);
    link.attr('opacity', 1);
    edgeLabel.attr('opacity', 1);
  }}
}});

// Simulation tick
simulation.on('tick', () => {{
  link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  edgeLabel.attr('x', d => (d.source.x + d.target.x) / 2)
            .attr('y', d => (d.source.y + d.target.y) / 2);
  nodeGroup.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
}});
</script>
</body>
</html>"""
