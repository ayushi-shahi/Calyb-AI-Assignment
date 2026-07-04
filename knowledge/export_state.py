"""Serialize the built graph to knowledge/knowledge_state.json: a flat, human-navigable
snapshot readable without running any code (BUILD_SPEC.md section 5).

    python knowledge/export_state.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from build_graph import (
    FOUNDATIONAL_EXTENDS_INDEGREE_THRESHOLD,
    build_graph,
    compute_foundational,
    load_edges,
    load_entities,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "knowledge" / "knowledge_state.json"
TOPIC = "Approximate Nearest Neighbor (ANN) Search"


def main():
    entities = load_entities()
    edges = load_edges()
    g = build_graph(entities, edges)
    foundational = compute_foundational(g)

    state = {
        "meta": {
            "topic": TOPIC,
            "n_papers": len(entities["papers"]),
            "n_concepts": len(entities["concepts"]),
            "n_problems": len(entities["problems"]),
            "n_edges": len(edges),
            "n_derived_foundational": len(foundational),
            "generated": datetime.now(timezone.utc).isoformat(),
        },
        "papers": entities["papers"],
        "concepts": entities["concepts"],
        "problems": entities["problems"],
        "edges": edges,
        "derived": {
            "foundational_threshold_extends_indegree": FOUNDATIONAL_EXTENDS_INDEGREE_THRESHOLD,
            "foundational": [
                {"paper": d["paper"], "concept": d["concept"], "extends_in_degree": d["extends_in_degree"]}
                for d in foundational
            ],
        },
    }

    OUTPUT_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size:,} bytes)")
    print(f"meta: {json.dumps(state['meta'], indent=2)}")


if __name__ == "__main__":
    main()
