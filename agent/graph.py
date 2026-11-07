from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import sqlite3

@dataclass
class Node:
    id: str
    type: str
    label: str
    tenant_id: str
    props: Dict[str, Any]

@dataclass
class Edge:
    src: str
    type: str
    dst: str

class Graph:
    def __init__(self, nodes: Dict[str, Node], edges: List[Edge]):
        self._nodes = nodes
        self._edges = edges
        self._adj: Dict[str, List[Edge]] = {}
        for e in edges:
            self._adj.setdefault(e.src, []).append(e)
            self._adj.setdefault(e.dst, []).append(Edge(src=e.dst, type=e.type, dst=e.src))

    def tenant_of(self, node_id: str) -> Optional[str]:
        n = self._nodes.get(node_id)
        return n.tenant_id if n else None

    def get(self, node_id: str) -> Optional[Node]:
        return self._nodes.get(node_id)

    def retrieve(self, tenant_id: str, finding_id: str, k: int = 2, question: Optional[str] = None) -> Dict[str, Any]:
        anchor_id = f"finding:{finding_id}" if not finding_id.startswith("finding:") else finding_id
        if self.tenant_of(anchor_id) != tenant_id:
            return {"anchor_ids": [anchor_id], "nodes": [], "edges": [], "context_text": "", "retrieve_ms": 1}
        visited: Set[str] = set([anchor_id])
        result_nodes: Dict[str, Node] = {}
        result_edges: List[Edge] = []
        frontier: List[Tuple[str, int]] = [(anchor_id, 0)]
        while frontier:
            nid, depth = frontier.pop(0)
            n = self._nodes.get(nid)
            if n and n.tenant_id == tenant_id:
                result_nodes[n.id] = n
            if depth < k:
                for e in self._adj.get(nid, []):
                    n2 = self._nodes.get(e.dst)
                    if not n2:
                        continue
                    if n2.tenant_id != tenant_id:
                        continue
                    result_edges.append(e)
                    if e.dst not in visited:
                        visited.add(e.dst)
                        frontier.append((e.dst, depth + 1))
        nodes_ser = [{"id": n.id, "type": n.type, "label": n.label, "props": n.props} for n in result_nodes.values()]
        edges_ser = [{"src": e.src, "type": e.type, "dst": e.dst} for e in result_edges if e.src in result_nodes and e.dst in result_nodes]
        context_text = ", ".join(sorted(n.id for n in result_nodes.values()))
        return {"anchor_ids": [anchor_id], "nodes": nodes_ser, "edges": edges_ser, "context_text": context_text, "retrieve_ms": 1}

    def snapshot(self, tenant_id: str) -> Dict[str, Any]:
        """Every node and edge this tenant owns. Other tenants stay out."""
        nodes = [n for n in self._nodes.values() if n.tenant_id == tenant_id]
        ids = {n.id for n in nodes}
        edges = [e for e in self._edges if e.src in ids and e.dst in ids]
        by_type: Dict[str, int] = {}
        for n in nodes:
            by_type[n.type] = by_type.get(n.type, 0) + 1
        return {
            "nodes": [{"id": n.id, "type": n.type, "label": n.label} for n in nodes],
            "edges": [{"src": e.src, "type": e.type, "dst": e.dst} for e in edges],
            "counts": {"nodes": len(nodes), "edges": len(edges), "by_type": by_type},
        }

_ACTIVE_GRAPH: Optional[Graph] = None


def _load_seed_json(path: Path) -> Tuple[Dict[str, Node], List[Edge]]:
    data = json.loads(Path(path).read_text())
    nodes = {n["id"]: Node(id=n["id"], type=n.get("type", "node"), label=n.get("label", n["id"]), tenant_id=n.get("tenant_id", "tenant_demo_acme"), props=n.get("props", {})) for n in data.get("nodes", [])}
    edges = [Edge(src=e["src"], type=e.get("type", "RELATED"), dst=e["dst"]) for e in data.get("edges", [])]
    return nodes, edges


def load_seed(path: Path | str) -> Graph:
    global _ACTIVE_GRAPH
    nodes, edges = _load_seed_json(Path(path))
    _ACTIVE_GRAPH = Graph(nodes, edges)
    # Persist to SQLite for demo acceptance (no Postgres)
    try:
        persist_to_sqlite(Path("backend/var/graph.db"))
    except Exception:
        pass
    return _ACTIVE_GRAPH


def tenant_of(node_id: str) -> Optional[str]:
    if _ACTIVE_GRAPH is None:
        return None
    return _ACTIVE_GRAPH.tenant_of(node_id)


def persist_to_sqlite(db_path: Path | str) -> None:
    """Persist current in-memory graph to a simple SQLite schema (nodes, edges)."""
    if _ACTIVE_GRAPH is None:
        return
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            type TEXT,
            label TEXT,
            tenant_id TEXT,
            props TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            src TEXT,
            type TEXT,
            dst TEXT
        )
    """)
    cur.execute("DELETE FROM nodes")
    cur.execute("DELETE FROM edges")
    for n in _ACTIVE_GRAPH._nodes.values():
        cur.execute("INSERT INTO nodes (id, type, label, tenant_id, props) VALUES (?, ?, ?, ?, ?)",
                    (n.id, n.type, n.label, n.tenant_id, json.dumps(n.props)))
    for e in _ACTIVE_GRAPH._edges:
        cur.execute("INSERT INTO edges (src, type, dst) VALUES (?, ?, ?)", (e.src, e.type, e.dst))
    con.commit()
    con.close()
