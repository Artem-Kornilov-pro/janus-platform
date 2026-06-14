"""Pure helpers for turning MCP `find_relationships` results into a drawable graph.

Kept free of any Qt imports so the layout logic can be unit tested without a
display.
"""

from __future__ import annotations

import math
from typing import Any

NODE_COLORS: dict[str, str] = {
    "Document": "#5e8bff",
    "Clause": "#9b7bff",
    "Party": "#ffb84d",
    "Obligation": "#4dd0a1",
    "Risk": "#ff6b6b",
    "LegalNorm": "#6bd3ff",
    "CourtDecision": "#c0c4cc",
}
DEFAULT_NODE_COLOR = "#8a8d99"


def _node_key(node: dict[str, Any], labels: list[str]) -> str:
    label = labels[0] if labels else "Node"
    identifier = node.get("name") or node.get("title") or node.get("id") or node.get("code") or str(node)
    return f"{label}:{identifier}"


def _node_display(node: dict[str, Any], labels: list[str]) -> str:
    label = labels[0] if labels else "Node"
    identifier = node.get("name") or node.get("title") or node.get("id") or node.get("code") or "?"
    return f"{identifier}\n({label})"


def build_graph_elements(relationships: list[dict[str, Any]]) -> tuple[dict[str, dict], list[dict]]:
    """Build a node map and edge list from `find_relationships` records.

    Returns (nodes, edges):
      - nodes: key -> {"label": str, "display": str, "color": str}
      - edges: [{"source": key, "target": key, "label": str}]
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    for rel in relationships:
        source_labels = rel.get("source_labels") or []
        target_labels = rel.get("target_labels") or []
        source = rel.get("source") or {}
        target = rel.get("target") or {}

        source_key = _node_key(source, source_labels)
        target_key = _node_key(target, target_labels)

        nodes.setdefault(source_key, {
            "label": source_labels[0] if source_labels else "Node",
            "display": _node_display(source, source_labels),
            "color": NODE_COLORS.get(source_labels[0] if source_labels else "", DEFAULT_NODE_COLOR),
        })
        nodes.setdefault(target_key, {
            "label": target_labels[0] if target_labels else "Node",
            "display": _node_display(target, target_labels),
            "color": NODE_COLORS.get(target_labels[0] if target_labels else "", DEFAULT_NODE_COLOR),
        })

        edges.append({
            "source": source_key,
            "target": target_key,
            "label": rel.get("relationship", ""),
        })

    return nodes, edges


def circular_layout(node_keys: list[str], radius: float = 250.0) -> dict[str, tuple[float, float]]:
    """Place nodes evenly around a circle, returning key -> (x, y)."""
    count = len(node_keys)
    if count == 0:
        return {}
    if count == 1:
        return {node_keys[0]: (0.0, 0.0)}

    positions: dict[str, tuple[float, float]] = {}
    for i, key in enumerate(node_keys):
        angle = 2 * math.pi * i / count
        positions[key] = (radius * math.cos(angle), radius * math.sin(angle))
    return positions
