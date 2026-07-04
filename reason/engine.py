"""Rank prior work by EDGE SEMANTICS, not raw similarity.

Given match.py's output, pulls the subgraph induced by the candidate concepts
(papers whose own concepts[] overlap) unioned with match.py's nearest_papers, then
scores each candidate paper on IS_FOUNDATIONAL_FOR status, EXTENDS-lineage distance
to a foundational paper, and match.py's own similarity/overlap signal -- each scaled
by that concept's match strength. Also flags candidates on a TRADES_OFF_AGAINST edge
whose "improves" axis matches a candidate problem, as a known objection.
"""
import json
from pathlib import Path

import networkx as nx

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_STATE_PATH = REPO_ROOT / "knowledge" / "knowledge_state.json"

# Ranking weights are explicit and fixed, not learned -- easy to justify in review.
W_FOUNDATIONAL = 0.4
W_LINEAGE = 0.3
W_MATCH = 0.3


def load_knowledge_state(path=KNOWLEDGE_STATE_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_extends_graph(edges):
    g = nx.DiGraph()
    for e in edges:
        if e["rel"] == "EXTENDS":
            g.add_edge(e["src"], e["dst"])
    return g


def _shortest_distance(extends_graph, paper_id, targets):
    """Shortest EXTENDS-hop distance from paper_id to any node in targets, or None."""
    if paper_id not in extends_graph:
        return None
    best = None
    for target in targets:
        if target not in extends_graph:
            continue
        try:
            d = nx.shortest_path_length(extends_graph, source=paper_id, target=target)
        except nx.NetworkXNoPath:
            continue
        if best is None or d < best:
            best = d
    return best


def _lineage_chain_to_root(extends_graph, paper_id):
    """Follow EXTENDS edges from paper_id toward its ultimate root (a paper with no
    outgoing EXTENDS edge), returning [root, ..., paper_id]."""
    chain = [paper_id]
    seen = {paper_id}
    current = paper_id
    while extends_graph.has_node(current) and extends_graph.out_degree(current) > 0:
        nxt = next(iter(extends_graph.successors(current)))
        if nxt in seen:
            break
        chain.append(nxt)
        seen.add(nxt)
        current = nxt
    return list(reversed(chain))


def lineage_chain(paper_id, knowledge_state=None):
    ks = knowledge_state or load_knowledge_state()
    extends_graph = _build_extends_graph(ks["edges"])
    return _lineage_chain_to_root(extends_graph, paper_id)


def rank(match_result, knowledge_state=None):
    ks = knowledge_state or load_knowledge_state()
    papers_by_id = {p["id"]: p for p in ks["papers"]}
    edges = ks["edges"]
    extends_graph = _build_extends_graph(edges)

    concept_score_by_id = {c["id"]: c["score"] for c in match_result["candidate_concepts"]}
    candidate_concept_ids = set(concept_score_by_id)

    foundational_by_concept = {}
    for d in ks["derived"]["foundational"]:
        foundational_by_concept.setdefault(d["concept"], set()).add(d["paper"])

    claimed_axes = {p["id"] for p in match_result["candidate_problems"]}
    trades_off_by_paper = {}
    for e in edges:
        if e["rel"] == "TRADES_OFF_AGAINST" and e.get("improves") in claimed_axes:
            trades_off_by_paper.setdefault(e["src"], []).append(e)
            trades_off_by_paper.setdefault(e["dst"], []).append(e)

    # nearest_papers still seeds pool membership (it's how a future embedding signal
    # would surface papers with no annotated concept overlap at all), but its scores
    # are NOT reused for ranking -- every pool member gets its match_score computed
    # directly below, so nothing is silently zeroed just for missing that top-k cut.
    pool_ids = {np_["id"] for np_ in match_result["nearest_papers"]}
    for p in ks["papers"]:
        if candidate_concept_ids & set(p.get("concepts") or []):
            pool_ids.add(p["id"])

    total_concept_weight = sum(concept_score_by_id.values())

    candidates = []
    for pid in pool_ids:
        paper = papers_by_id.get(pid)
        if paper is None:
            continue

        is_foundational_for = []
        foundational_component = 0.0
        lineage_component = 0.0
        lineage_detail = []

        for cid, s_c in concept_score_by_id.items():
            anchors = foundational_by_concept.get(cid)
            if not anchors:
                continue
            if pid in anchors:
                foundational_component += s_c
                is_foundational_for.append(cid)
                continue
            distance = _shortest_distance(extends_graph, pid, anchors)
            if distance is not None:
                contribution = s_c / (1 + distance)
                lineage_component += contribution
                lineage_detail.append({
                    "concept": cid, "concept_score": s_c, "distance": distance,
                    "contribution": round(contribution, 4),
                })

        foundational_component = min(1.0, foundational_component)
        lineage_component = min(1.0, lineage_component)

        # Direct concept-overlap match score: fraction of the abstract's total
        # candidate-concept weight this paper's own concepts[] covers. Concepts
        # already credited via foundational_component are excluded here so the
        # same signal isn't paid out twice under two different weights.
        shared_concepts = candidate_concept_ids & set(paper.get("concepts") or [])
        overlap_concepts = shared_concepts - set(is_foundational_for)
        match_score = (
            sum(concept_score_by_id[c] for c in overlap_concepts) / total_concept_weight
            if total_concept_weight > 0 else 0.0
        )

        rank_score = W_FOUNDATIONAL * foundational_component + W_LINEAGE * lineage_component + W_MATCH * match_score

        candidates.append({
            "paper": pid,
            "title": paper["title"],
            "year": paper["year"],
            "shared_concepts": sorted(shared_concepts),
            "is_foundational_for": sorted(is_foundational_for),
            "foundational_component": round(foundational_component, 4),
            "lineage_component": round(lineage_component, 4),
            "lineage_detail": lineage_detail,
            "match_score": round(match_score, 4),
            "rank_score": round(rank_score, 4),
            "trades_off_matches": trades_off_by_paper.get(pid, []),
        })

    candidates.sort(key=lambda c: -c["rank_score"])

    return {
        "claimed_axes": sorted(claimed_axes),
        "candidates": candidates,
    }


if __name__ == "__main__":
    import match as match_module

    mr = match_module.match(
        "We propose a graph-based index that reduces memory footprint by storing "
        "compressed neighbor lists while preserving high recall for billion-scale "
        "approximate nearest neighbor search."
    )
    print(json.dumps(rank(mr), indent=2))
