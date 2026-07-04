"""Load knowledge/entities.json + edges.json into a NetworkX graph and compute
the derived IS_FOUNDATIONAL_FOR relationship (BUILD_SPEC.md sections 4/6).

    python knowledge/build_graph.py

Prints basic graph stats. Intended to be imported by export_state.py.
"""
import json
from pathlib import Path

import networkx as nx

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTITIES_PATH = REPO_ROOT / "knowledge" / "entities.json"
EDGES_PATH = REPO_ROOT / "knowledge" / "edges.json"

# A paper is IS_FOUNDATIONAL_FOR a concept it introduces only if at least this many
# other papers EXTEND it directly -- one extender isn't a strong enough signal that
# the field converged on this paper as a base; two or more independent extensions is.
FOUNDATIONAL_EXTENDS_INDEGREE_THRESHOLD = 2


def load_entities(path=ENTITIES_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_edges(path=EDGES_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))["edges"]


def build_graph(entities, edges):
    """Build a MultiDiGraph: nodes are papers/concepts/problems (typed via 'kind'),
    edges carry rel/evidence/confidence (+ improves/at_cost_of where present)."""
    g = nx.MultiDiGraph()

    for paper in entities["papers"]:
        g.add_node(paper["id"], kind="paper", **{k: v for k, v in paper.items() if k != "id"})
    for concept in entities["concepts"]:
        g.add_node(concept["id"], kind="concept", **{k: v for k, v in concept.items() if k != "id"})
    for problem in entities["problems"]:
        g.add_node(problem["id"], kind="problem", **{k: v for k, v in problem.items() if k != "id"})

    unresolved = []
    for e in edges:
        if e["src"] not in g or e["dst"] not in g:
            unresolved.append(e)
            continue
        attrs = {k: v for k, v in e.items() if k not in ("src", "dst")}
        g.add_edge(e["src"], e["dst"], **attrs)

    if unresolved:
        raise ValueError(f"{len(unresolved)} edge(s) reference a missing node: {unresolved}")

    return g


def compute_foundational(g, threshold=FOUNDATIONAL_EXTENDS_INDEGREE_THRESHOLD):
    """Derived (not authored): paper IS_FOUNDATIONAL_FOR concept if the paper
    INTRODUCES it and has an EXTENDS in-degree >= threshold."""
    derived = []
    for node, data in g.nodes(data=True):
        if data.get("kind") != "paper":
            continue
        extends_in_degree = sum(
            1 for _, _, edata in g.in_edges(node, data=True) if edata.get("rel") == "EXTENDS"
        )
        if extends_in_degree < threshold:
            continue
        for concept_id in data.get("introduces", []):
            derived.append({
                "paper": node,
                "concept": concept_id,
                "extends_in_degree": extends_in_degree,
            })
    return derived


def main():
    entities = load_entities()
    edges = load_edges()
    g = build_graph(entities, edges)
    foundational = compute_foundational(g)

    n_papers = sum(1 for _, d in g.nodes(data=True) if d.get("kind") == "paper")
    n_concepts = sum(1 for _, d in g.nodes(data=True) if d.get("kind") == "concept")
    n_problems = sum(1 for _, d in g.nodes(data=True) if d.get("kind") == "problem")

    print(f"Nodes: {g.number_of_nodes()} (papers={n_papers}, concepts={n_concepts}, problems={n_problems})")
    print(f"Edges: {g.number_of_edges()}")
    print(f"Derived IS_FOUNDATIONAL_FOR (threshold={FOUNDATIONAL_EXTENDS_INDEGREE_THRESHOLD}): {len(foundational)}")
    for d in foundational:
        paper_title = g.nodes[d["paper"]]["title"]
        print(f"  {paper_title!r} -> {d['concept']} (EXTENDS in-degree={d['extends_in_degree']})")


if __name__ == "__main__":
    main()
