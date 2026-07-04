# ANN Knowledge Graph

A hand-annotated knowledge graph over ~35 papers on approximate nearest neighbor
(ANN) search. Given a new paper abstract the graph has never seen, it returns a
structured novelty assessment — closest prior work and how the new idea relates to
it, overlapping vs. apparently novel concepts, known tradeoff objections, and a
lineage-based reading path — derived entirely from graph traversal, not an LLM.

See `approach.md` for the design writeup (what was built and why). This file is
operational only: how to install, regenerate the knowledge state, and run queries.

## Repo structure

```
BUILD_SPEC.md             plumbing spec this project was built against
approach.md                design writeup (reviewer-facing)
requirements.txt

ingest/
  seeds.md                 hand-curated seed paper list, by family
  fetch_corpus.py          seeds.md -> data/raw/papers.json (Semantic Scholar)
  backfill_abstracts.py    fills missing abstracts from arXiv where a title matches

knowledge/
  entities.json             HAND-AUTHORED: papers, concepts, problems
  edges.json                HAND-AUTHORED: semantic edges with evidence
  build_graph.py           entities/edges -> NetworkX, computes IS_FOUNDATIONAL_FOR
  export_state.py          graph -> knowledge_state.json
  knowledge_state.json      flat, human-readable snapshot (the inspectable deliverable)

reason/
  match.py                 abstract -> candidate concepts/problems/papers
  engine.py                ranks prior work by edge semantics (foundational, lineage, tradeoffs)
  novelty.py               assembles the final structured novelty output

cli.py                      query entry point
data/raw/papers.json         cached Semantic Scholar pull
examples/                    held-out abstracts (not in the corpus) + their CLI output
```

## Setup

```
pip install -r requirements.txt
```

Only `httpx`, `networkx`, and `numpy` are required. `sentence-transformers` is
optional (see Config below) and is not in requirements.txt since the system runs
without it.

## Regenerating the knowledge state

`knowledge_state.json` is already committed, so this step isn't required to run
queries. Regenerate it after editing `knowledge/entities.json` or `knowledge/edges.json`:

```
python knowledge/build_graph.py     # sanity-check: prints node/edge counts + derived edges
python knowledge/export_state.py    # writes knowledge/knowledge_state.json
```

## Running a query

```
python cli.py --abstract "paste an abstract here"
python cli.py --file examples/cagra.txt
```

Either prints the full structured JSON followed by a pretty-printed summary
(placement, closest prior work, novelty assessment, known objections, reading path).

`examples/` has two held-out abstracts (CAGRA, and "Probabilistic Routing for
Graph-Based ANN Search") with their corresponding `*.out.txt` — use these as sample
input/output if you want to see the shape of a result before writing your own.

## Config (both optional)

- `S2_API_KEY` — only needed to re-run `ingest/fetch_corpus.py` against the Semantic
  Scholar API at a higher rate limit. Not required to run queries.
- `sentence-transformers` — if installed, `reason/match.py` uses it for cosine-similarity
  matching (cached to `data/embeddings.npz`) instead of keyword-only matching. Not
  installed by default; the system works fully without it.

Because `knowledge/knowledge_state.json` and `data/raw/papers.json` are committed,
**a reviewer can run `cli.py` immediately with no API key and no network call.**
