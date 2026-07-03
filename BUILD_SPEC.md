# BUILD_SPEC.md — ANN Knowledge Graph (Calyb assignment, Domain B)

> Handoff spec for Claude Code CLI. This defines the **plumbing only**.
> The taxonomy, edge annotations, and evidence fields are authored by hand
> (Ayushi) — CLI must NOT auto-generate concepts, edges, or their evidence.
> The "no automated entity/relationship extraction" constraint applies to code too.

## 0. Project one-liner
Ingest ~55 papers on approximate nearest neighbor (ANN) search, model them as a
hand-annotated knowledge graph with *semantic* relationships (not raw citations),
and — given a new paper abstract never seen before — return a structured novelty
assessment: closest prior work + nature of relation, overlapping vs novel concepts,
tradeoff objections it will face, and a lineage-based reading path.

## 1. Repo layout
```
ann-kg/
  ingest/
    fetch_corpus.py        # S2 API -> data/raw/papers.json
    build_embeddings.py    # abstract embeddings -> data/embeddings.npz (cached, committed)
  knowledge/
    schema.py              # dataclasses / TypedDicts for entities + edges (validation)
    entities.json          # HAND-AUTHORED: papers, concepts, problems
    edges.json             # HAND-AUTHORED: semantic edges w/ evidence
    build_graph.py         # loads json -> NetworkX, computes derived edges
    knowledge_state.json   # SERIALIZED SNAPSHOT (the inspectable deliverable)
    export_state.py        # graph -> knowledge_state.json (flat, navigable)
  reason/
    match.py               # new abstract -> concepts/problems (embedding + keyword)
    engine.py              # subgraph pull + ranking by edge semantics
    novelty.py             # assembles the structured novelty output
    reading_path.py        # derived bonus flow
  cli.py                   # `python cli.py --abstract "..."` or --file path
  data/
    raw/papers.json        # cached API pull (committed so reviewer needs no key)
    embeddings.npz         # cached embeddings (committed)
  README.md
  approach.md
  requirements.txt
```

## 2. Dependencies (keep minimal)
`httpx`, `networkx`, `numpy`, `sentence-transformers` (local, no API key needed for reviewer)
OR `google-genai` if using Gemini embeddings — but if so, **cache embeddings to disk and
commit them** so the reviewer can run reasoning without any key. No FastAPI, no Neo4j.

## 3. Ingestion spec (`ingest/fetch_corpus.py`)
- Source: Semantic Scholar Graph API, base `https://api.semanticscholar.org/graph/v1/`
- No API key required at this scale (shared unauth pool is ample); implement
  **exponential backoff** on HTTP 429 (S2 requires it).
- Endpoint: `/paper/batch` (POST) for details, fields:
  `paperId,title,year,venue,abstract,authors,references.paperId,citations.paperId`
- Input: a seed list of ~55 paperIds/arXiv IDs (Ayushi curates the seed list from the
  ANN lineage: LSH, PQ, OPQ, IVF, IVFADC, NSW, HNSW, DiskANN, ScaNN, FAISS-GPU, etc.).
- Output: `data/raw/papers.json` — one record per paper with the fields above.
- The raw `references`/`citations` are the **citation skeleton only** — NOT written into
  edges.json. edges.json is authored separately by hand.

## 4. Knowledge schema (`knowledge/schema.py`)
Entities:
- `Paper`: id, title, year, venue, authors[], abstract, concepts[], introduces[],
  addresses[], s2_citations[]
- `Concept`: id, name, definition (own words), category
  (index-structure|compression|search-strategy|distance-metric|hardware-optimization),
  introduced_by (paperId|null)
- `Problem`: id, name, description
- `Author`: id, name  (thin, deliberate)

Edges (edges.json), every edge carries `evidence` (str) and `confidence` (high|medium):
- Paper->Paper: `EXTENDS`, `TRADES_OFF_AGAINST` (+improves,+at_cost_of),
  `OUTPERFORMS_ON` (+metric,+dataset; optional/sparse), `COMBINES` (target paper|concept),
  `ALTERNATIVE_TO`
- Paper->Concept: `INTRODUCES`, `APPLIES`
- Paper->Problem: `ADDRESSES`
- Concept->Concept: `EVOLVED_FROM`
- Derived (computed in build_graph, NOT authored): `IS_FOUNDATIONAL_FOR(concept)` =
  paper INTRODUCES concept AND has high in-degree of EXTENDS edges.

`schema.py` provides a `validate(entities, edges)` that checks: every edge endpoint
exists, every concept.introduced_by resolves, no edge missing evidence, confidence in
{high,medium}. Run in CI/precommit-style before export.

## 5. Knowledge state export (`export_state.py` -> knowledge_state.json)
Flat, human-navigable JSON. Must be understandable WITHOUT running code:
```json
{
  "meta": {"topic": "...", "n_papers": 55, "n_edges": 210, "generated": "ISO8601"},
  "papers":   [ {full Paper record} ],
  "concepts": [ {full Concept record} ],
  "problems": [ {full Problem record} ],
  "edges":    [ {src, rel, dst, evidence, confidence, ...extras} ],
  "derived":  {"foundational": [{"paper": "...", "concept": "..."}]}
}
```

## 6. Reasoning pipeline (the graded core — reasoning lives in graph, not the LLM)
Input: a new abstract (string).
1. `match.py`: embed the abstract; cosine-compare against (a) concept definitions and
   (b) existing paper abstracts. Keyword pass over concept names as a backstop.
   -> candidate concepts, candidate problems, k nearest existing papers.
2. `engine.py`: pull the subgraph induced by candidate concepts + nearest papers.
   Rank prior work using EDGE SEMANTICS:
     - is neighbor foundational? (IS_FOUNDATIONAL_FOR)
     - lineage depth via EXTENDS chains
     - does neighbor sit on a TRADES_OFF_AGAINST edge on an axis the new abstract
       claims to improve? -> that's a "known objection"
3. `novelty.py`: assemble output (below). Every field must be derivable from the graph.
   An LLM may PHRASE the output but must not DECIDE it.

Output schema:
```json
{
  "placement": {"nearest_concepts": [...], "addressed_problems": [...]},
  "closest_prior_work": [
    {"paper": "...", "relation": "your idea EXTENDS this", "overlap": "..."}
  ],
  "novelty_assessment": {"overlapping_claims": [...], "apparently_novel": [...]},
  "known_objections": [
    {"from_paper": "...", "axis": "memory-footprint", "objection": "..."}
  ],
  "suggested_reading_path": ["foundational -> ... -> closest neighbor"]
}
```

## 7. CLI (`cli.py`)
- `python cli.py --abstract "PASTE TEXT"`  -> prints structured JSON + optional pretty view
- `python cli.py --file some_abstract.txt`
- `python cli.py --reading-path --from <paperId> --to <paperId>`  (bonus flow)
- Loads knowledge_state.json (or builds graph from entities/edges). No network needed
  at query time (embeddings cached).

## 8. Demo material (Day 3)
3-4 recent arXiv ANN abstracts deliberately NOT in the corpus, saved under
`examples/`, each with its produced output committed as `examples/*.out.json`.
This is the clearest proof the system operates on genuinely new input.

## 9. What CLI must NOT do (constraint guardrails)
- Do not populate entities.json/edges.json programmatically from paper text.
- Do not use spaCy/NER/any auto-KG library.
- Do not let the reasoning decision logic be "ask an LLM what's related" — the LLM
  is a phraser at most; ranking/placement is graph traversal.
