# nerva/dag.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Callable, Awaitable, Set
import asyncio
import logging

from .run_context import RunContext


logger = logging.getLogger(__name__)

DagFunc = Callable[[RunContext], Awaitable[None]]


@dataclass
class DagNode:
    """A single node in a DAG workflow."""
    name: str
    func: DagFunc
    deps: List[str] = field(default_factory=list)


class Dag:
    """
    Minimal async DAG executor with dependency support.

    Nodes are executed in topological order based on their dependencies.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._nodes: Dict[str, DagNode] = {}

    def add_node(self, node: DagNode) -> None:
        """Add a node to the DAG."""
        if node.name in self._nodes:
            raise ValueError(f"Node {node.name} already exists in DAG {self.name}")
        self._nodes[node.name] = node
        logger.debug(f"[{self.name}] Added node: {node.name} (deps={node.deps})")

    def _topological_order(self) -> List[DagNode]:
        """
        Compute topological ordering of nodes using DFS.
        Raises ValueError if cycle is detected.
        """
        visited: Set[str] = set()
        temp: Set[str] = set()
        order: List[DagNode] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in temp:
                raise ValueError(f"Cycle detected in DAG {self.name}: {name}")
            temp.add(name)
            node = self._nodes.get(name)
            if node is None:
                raise ValueError(f"Missing node {name} in DAG {self.name}")
            for dep in node.deps:
                visit(dep)
            temp.remove(name)
            visited.add(name)
            order.append(node)

        for name in self._nodes:
            visit(name)

        return order

    async def run(self, ctx: RunContext) -> RunContext:
        """
        Execute the DAG with the given context.
        Returns the mutated context after all nodes complete.
        """
        logger.info(f"[{self.name}] Starting DAG execution")
        order = self._topological_order()

        for i, node in enumerate(order):
            logger.info(f"[{self.name}] [{i+1}/{len(order)}] Running node: {node.name}")
            try:
                await node.func(ctx)
            except Exception as e:
                logger.error(f"[{self.name}] Node {node.name} failed: {e}", exc_info=True)
                raise

        logger.info(f"[{self.name}] DAG execution complete")
        return ctx
