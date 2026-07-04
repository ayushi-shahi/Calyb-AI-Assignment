"""Assemble the structured novelty assessment. Every field is derived from
match.py + engine.py, i.e. from the graph -- an LLM may later rephrase this JSON
into prose, but nothing here is an LLM decision.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine
import match

DEFAULT_TOP_PRIOR_WORK = 5


def _relation_for(candidate, candidate_concepts_by_id):
    if candidate["is_foundational_for"]:
        names = [candidate_concepts_by_id[cid]["name"] for cid in candidate["is_foundational_for"]]
        return f"foundational for {', '.join(names)} -- your idea likely EXTENDS this lineage"
    if candidate["trades_off_matches"]:
        axes = sorted({e.get("improves") for e in candidate["trades_off_matches"] if e.get("improves")})
        return f"already trades off on {', '.join(axes)} -- your idea may TRADES_OFF_AGAINST or ALTERNATIVE_TO this"
    if candidate["shared_concepts"]:
        return "shares concepts with your idea -- related prior work"
    return "similar by abstract content"


def assemble(abstract, knowledge_state=None, entities=None, top_k=DEFAULT_TOP_PRIOR_WORK):
    ks = knowledge_state or engine.load_knowledge_state()
    match_result = match.match(abstract, entities=entities)
    ranked = engine.rank(match_result, knowledge_state=ks)

    candidate_concepts_by_id = {c["id"]: c for c in match_result["candidate_concepts"]}
    concepts_by_id = {c["id"]: c for c in ks["concepts"]}
    papers_by_id = {p["id"]: p for p in ks["papers"]}

    placement = {
        "nearest_concepts": [
            {"id": c["id"], "name": c["name"], "score": c["score"]} for c in match_result["candidate_concepts"]
        ],
        "addressed_problems": [
            {"id": p["id"], "name": p["name"], "score": p["score"]} for p in match_result["candidate_problems"]
        ],
    }

    top_candidates = ranked["candidates"][:top_k]

    closest_prior_work = []
    for cand in top_candidates:
        overlap_names = [concepts_by_id[cid]["name"] for cid in cand["shared_concepts"] if cid in concepts_by_id]
        closest_prior_work.append({
            "paper": cand["title"],
            "paper_id": cand["paper"],
            "relation": _relation_for(cand, candidate_concepts_by_id),
            "overlap": overlap_names,
        })

    covered_concept_ids = set()
    for cand in top_candidates:
        covered_concept_ids |= set(cand["shared_concepts"])
    candidate_concept_ids = set(candidate_concepts_by_id)
    novelty_assessment = {
        "overlapping_claims": [
            candidate_concepts_by_id[cid]["name"] for cid in sorted(candidate_concept_ids & covered_concept_ids)
        ],
        "apparently_novel": [
            candidate_concepts_by_id[cid]["name"] for cid in sorted(candidate_concept_ids - covered_concept_ids)
        ],
    }

    known_objections = []
    seen = set()
    for cand in top_candidates:
        for e in cand["trades_off_matches"]:
            key = (e["src"], e["dst"], e.get("improves"))
            if key in seen:
                continue
            seen.add(key)
            src_title = papers_by_id.get(e["src"], {}).get("title", e["src"])
            known_objections.append({
                "from_paper": src_title,
                "axis": e.get("improves"),
                "objection": e.get("evidence", ""),
            })

    suggested_reading_path = []
    if top_candidates:
        chain_ids = engine.lineage_chain(top_candidates[0]["paper"], knowledge_state=ks)
        suggested_reading_path = [papers_by_id[pid]["title"] for pid in chain_ids if pid in papers_by_id]

    return {
        "placement": placement,
        "closest_prior_work": closest_prior_work,
        "novelty_assessment": novelty_assessment,
        "known_objections": known_objections,
        "suggested_reading_path": suggested_reading_path,
    }


if __name__ == "__main__":
    TEST_ABSTRACT = (
        "We introduce a disk-resident graph index for billion-scale approximate "
        "nearest neighbor search that halves memory footprint compared to existing "
        "in-memory graph methods, while keeping query latency competitive by "
        "prefetching neighbor blocks from SSD. Our approach targets deployments "
        "where the full dataset cannot fit in RAM."
    )
    print(json.dumps(assemble(TEST_ABSTRACT), indent=2))
