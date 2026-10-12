"""Validate subgraph workflow IR documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "schemas"
    / "workflows"
    / "subgraph.schema.json"
)


def _load_schema() -> dict[str, Any]:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_subgraph(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with open(path) as f:
        return json.load(f)


def validate_subgraph(doc: dict[str, Any]) -> list[str]:
    """Return a list of human-readable errors (empty if valid)."""
    errors: list[str] = []
    try:
        jsonschema.validate(instance=doc, schema=_load_schema())
    except jsonschema.ValidationError as exc:
        errors.append(f"schema: {exc.message}")
        return errors

    node_ids = {n["id"] for n in doc["nodes"]}
    if doc["entry"] not in node_ids:
        errors.append(f"entry {doc['entry']!r} is not a node id")

    for edge in doc.get("edges", []):
        if edge["from"] not in node_ids:
            errors.append(f"edge from unknown node {edge['from']!r}")
        if edge["to"] not in node_ids:
            errors.append(f"edge to unknown node {edge['to']!r}")

    # Disallow map type semantically (enum already blocks); check agent/tool payloads
    for node in doc["nodes"]:
        ntype = node["type"]
        if ntype == "tool" and "tool" not in node:
            errors.append(f"node {node['id']!r}: tool payload required")
        if ntype == "agent" and "agent" not in node:
            errors.append(f"node {node['id']!r}: agent payload required")
        if ntype == "router" and "router" not in node:
            errors.append(f"node {node['id']!r}: router payload required")
        if ntype == "code" and "code" not in node:
            errors.append(f"node {node['id']!r}: code payload required")

    # Detect unconditional cycles on default/success ports (rework allowed)
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for edge in doc.get("edges", []):
        port = edge.get("port", "default")
        if port == "rework":
            continue
        if edge.get("when"):
            continue
        adjacency[edge["from"]].append(edge["to"])

    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(nid: str) -> None:
        if nid in visiting:
            errors.append(f"cycle detected at {nid!r} (non-rework edges)")
            return
        if nid in visited:
            return
        visiting.add(nid)
        for nxt in adjacency.get(nid, []):
            dfs(nxt)
        visiting.remove(nid)
        visited.add(nid)

    if doc["entry"] in node_ids:
        dfs(doc["entry"])

    return errors


def validate_subgraph_file(path: str | Path) -> dict[str, Any]:
    doc = load_subgraph(path)
    errs = validate_subgraph(doc)
    return {
        "path": str(path),
        "id": doc.get("id"),
        "valid": not errs,
        "errors": errs,
    }
