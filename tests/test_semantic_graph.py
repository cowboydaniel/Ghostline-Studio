from __future__ import annotations

from pathlib import Path

from ghostline.semantic.graph import GraphEdge, GraphNode, SemanticGraph
from ghostline.semantic.query import NavigationResult, SemanticQueryEngine


def test_cycle_detection_and_fingerprint() -> None:
    graph = SemanticGraph()
    file_path = Path("/tmp/demo.py")
    node_a = GraphNode("A", "function", file_path)
    node_b = GraphNode("B", "function", file_path)
    node_c = GraphNode("C", "function", file_path)

    graph.add_edge(GraphEdge(node_a, node_b, "calls"))
    graph.add_edge(GraphEdge(node_b, node_c, "calls"))
    graph.add_edge(GraphEdge(node_c, node_a, "calls"))

    graph.tag_pattern("hexagonal")
    graph.annotate_runtime(type("Obs", (), {"path": str(file_path), "calls": ["A"]}))

    cycles = graph.find_cycles()
    assert any(len(cycle) == 3 for cycle in cycles)

    fingerprint = graph.pattern_fingerprint()
    assert "Modules:" in fingerprint
    assert "Runtime hotspots" in fingerprint


def test_module_map_churn_and_references() -> None:
    graph = SemanticGraph()
    file_one = Path("/tmp/one.py")
    file_two = Path("/tmp/two.py")

    module_one = GraphNode("one", "module", file_one)
    module_two = GraphNode("two", "module", file_two)
    func = GraphNode("do_work", "function", file_one)

    graph.add_edge(GraphEdge(module_one, module_two, "imports"))
    graph.add_node(func)

    module_map = graph.module_map()
    assert module_map[module_one.file.stem] == {module_two.file.stem}

    churn = graph.module_churn()
    assert churn == {"one": 1}

    assert graph.references("do_work") == {func}


def test_query_engine_finds_related_functions() -> None:
    graph = SemanticGraph()
    file_path = Path("/tmp/app.py")
    function_node = GraphNode("render", "function", file_path)
    class_node = GraphNode("Controller", "class", file_path)
    graph.add_node(function_node)
    graph.add_node(class_node)

    query = SemanticQueryEngine(graph)

    usages = query.find_usages("render")
    assert usages == [function_node]

    related = query.find_related_functions("render")
    assert NavigationResult(f"Function {function_node.name}", function_node) in related

    assert list(query.search_by_kind("class")) == [class_node]
    assert query.architecture_map() == {}
