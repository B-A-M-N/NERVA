"""In-memory knowledge graph for NERVA."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


@dataclass
class Node:
    node_id: str
    label: str
    type: str
    metadata: Dict[str, str] = field(default_factory=dict)


class KnowledgeGraph:
    """Simple adjacency graph storing nodes, edges, and lightweight queries."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # src -> [(relation, dst)]
        self.reverse_edges: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    def add_node(self, node: Node) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, src: str, relation: str, dst: str) -> None:
        if src not in self.nodes or dst not in self.nodes:
            return
        self.edges[src].append((relation, dst))
        self.reverse_edges[dst].append((relation, src))

    def neighbors(self, node_id: str, relation: Optional[str] = None) -> List[Node]:
        entries = self.edges.get(node_id, [])
        if relation:
            entries = [entry for entry in entries if entry[0] == relation]
        return [self.nodes[dst] for _, dst in entries]

    def related(self, node_id: str, max_depth: int = 2) -> List[Node]:
        visited = set([node_id])
        queue = [(node_id, 0)]
        result: List[Node] = []
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for _, dst in self.edges.get(current, []):
                if dst in visited:
                    continue
                visited.add(dst)
                result.append(self.nodes[dst])
                queue.append((dst, depth + 1))
        return result

    def ingest_thread(self, thread_id: str, thread_title: str, entries: List[Dict[str, str]]) -> None:
        """Create graph nodes/edges for a task thread."""
        thread_node = Node(node_id=thread_id, label=thread_title, type="thread")
        self.add_node(thread_node)

        for entry in entries:
            entry_id = entry.get("entry_id")
            if not entry_id:
                continue
            node = Node(
                node_id=entry_id,
                label=entry.get("text", "")[:80],
                type="entry",
                metadata={"author": entry.get("author", "nerva")},
            )
            self.add_node(node)
            self.add_edge(thread_id, "HAS_ENTRY", entry_id)
            if "project" in entry.get("metadata", {}):
                proj = entry["metadata"]["project"]
                proj_id = f"project:{proj}"
                if proj_id not in self.nodes:
                    self.add_node(Node(node_id=proj_id, label=proj, type="project"))
                self.add_edge(proj_id, "OWNS_THREAD", thread_id)
