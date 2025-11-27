from pathlib import Path

from ghostline.semantic.graph import GraphEdge, GraphNode, SemanticGraph
from ghostline.semantic.index_manager import SemanticIndexManager


def test_get_graph_snapshot_shapes(tmp_path: Path) -> None:
    manager = SemanticIndexManager(lambda: str(tmp_path))
    graph: SemanticGraph = manager.graph

    file_path = tmp_path / "example.py"
    module_node = GraphNode(file_path.stem, "module", file_path)
    func_node = GraphNode("foo", "function", file_path, (10, 15))

    graph.add_node(module_node)
    graph.add_node(func_node)
    graph.add_edge(GraphEdge(module_node, func_node, "calls"))

    snapshot = manager.get_graph_snapshot()

    node_ids = {node["id"] for node in snapshot["nodes"]}
    assert f"file:{file_path.name}" in node_ids
    assert f"module:{file_path.name}" in node_ids
    assert f"func:{file_path.name}:foo" in node_ids

    contains_edges = {(edge["source"], edge["target"]) for edge in snapshot["edges"] if edge["type"] == "contains"}
    assert (f"module:{file_path.name}", f"file:{file_path.name}") in contains_edges
    assert (f"file:{file_path.name}", f"func:{file_path.name}:foo") in contains_edges

    call_edges = {(edge["source"], edge["target"]) for edge in snapshot["edges"] if edge["type"] == "calls"}
    assert (f"module:{file_path.name}", f"func:{file_path.name}:foo") in call_edges
