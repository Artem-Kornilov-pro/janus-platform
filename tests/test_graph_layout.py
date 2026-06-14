import math

from frontend.graph_layout import build_graph_elements, circular_layout, describe_node_connections


def test_build_graph_elements_creates_nodes_and_edges():
    relationships = [
        {
            "source_labels": ["Party"],
            "source": {"name": "ООО Альфа"},
            "relationship": "OBLIGATES",
            "target_labels": ["Obligation"],
            "target": {"id": "doc-1:clause:0:obligation:0", "description": "поставить оборудование"},
        }
    ]

    nodes, edges = build_graph_elements(relationships)

    assert set(nodes.keys()) == {"Party:ООО Альфа", "Obligation:doc-1:clause:0:obligation:0"}
    assert nodes["Party:ООО Альфа"]["label"] == "Party"
    assert nodes["Party:ООО Альфа"]["color"] == "#ffb84d"
    assert "ООО Альфа" in nodes["Party:ООО Альфа"]["display"]

    assert edges == [
        {
            "source": "Party:ООО Альфа",
            "target": "Obligation:doc-1:clause:0:obligation:0",
            "label": "OBLIGATES",
        }
    ]


def test_build_graph_elements_deduplicates_shared_nodes():
    relationships = [
        {
            "source_labels": ["Document"], "source": {"id": "doc-1"},
            "relationship": "INVOLVES",
            "target_labels": ["Party"], "target": {"name": "Acme"},
        },
        {
            "source_labels": ["Party"], "source": {"name": "Acme"},
            "relationship": "OBLIGATES",
            "target_labels": ["Obligation"], "target": {"id": "obl-1"},
        },
    ]

    nodes, edges = build_graph_elements(relationships)

    assert len(nodes) == 3
    assert len(edges) == 2


def test_build_graph_elements_unknown_label_uses_default_color():
    relationships = [
        {
            "source_labels": ["Mystery"], "source": {"id": "x"},
            "relationship": "RELATES_TO",
            "target_labels": ["Mystery"], "target": {"id": "y"},
        }
    ]

    nodes, _ = build_graph_elements(relationships)

    assert nodes["Mystery:x"]["color"] == "#8a8d99"


def test_build_graph_elements_empty_input():
    nodes, edges = build_graph_elements([])

    assert nodes == {}
    assert edges == []


def test_describe_node_connections_lists_edges():
    relationships = [
        {
            "source_labels": ["Party"], "source": {"name": "ООО Альфа"},
            "relationship": "OBLIGATES",
            "target_labels": ["Obligation"], "target": {"id": "obl-1", "description": "поставить"},
        },
        {
            "source_labels": ["Document"], "source": {"id": "doc-1"},
            "relationship": "INVOLVES",
            "target_labels": ["Party"], "target": {"name": "ООО Альфа"},
        },
    ]

    nodes, edges = build_graph_elements(relationships)

    description = describe_node_connections("Party:ООО Альфа", nodes, edges)

    assert "ООО Альфа" in description
    assert "Связи (2):" in description
    assert "-> OBLIGATES ->" in description
    assert "<- INVOLVES <-" in description


def test_describe_node_connections_no_edges():
    nodes = {"Party:Acme": {"label": "Party", "display": "Acme\n(Party)", "color": "#ffb84d"}}

    description = describe_node_connections("Party:Acme", nodes, [])

    assert "Связей не найдено" in description


def test_describe_node_connections_unknown_key():
    assert describe_node_connections("Missing:x", {}, []) == "Узел не найден"


def test_circular_layout_empty():
    assert circular_layout([]) == {}


def test_circular_layout_single_node_at_origin():
    positions = circular_layout(["a"])

    assert positions == {"a": (0.0, 0.0)}


def test_circular_layout_distributes_nodes_evenly_on_circle():
    positions = circular_layout(["a", "b", "c", "d"], radius=100.0)

    assert set(positions.keys()) == {"a", "b", "c", "d"}
    for x, y in positions.values():
        distance = math.hypot(x, y)
        assert math.isclose(distance, 100.0, rel_tol=1e-9)
