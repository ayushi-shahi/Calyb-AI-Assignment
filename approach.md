# approach.md

## What I built

A system that reasons over the approximate nearest neighbor (ANN) search literature. It takes a paper abstract it has never seen, places it within a hand-built knowledge graph of the field, and returns a structured novelty assessment: the closest prior work and *how* the new idea relates to it, which of its concepts are already well-covered versus apparently novel, which known tradeoff objections it will face, and a suggested reading path through the lineage it belongs to.

The point isn't retrieval. A search engine over these papers would tell you which ones mention similar words. This tells you where a new idea *sits* in the field and why — which is what someone actually needs when they're trying to figure out if their contribution is new.

## What subset of data I chose, and why

I picked Domain B and scoped it tightly: **ANN search algorithms and index structures themselves**, not their downstream applications like RAG or recommendation. The corpus is 35 papers covering the field's core lineage — early exact methods and the dimensionality wall (KD-trees, LSH), the quantization/compression family (Product Quantization, OPQ, additive quantization), inverted-file methods (IVF, the inverted multi-index), the graph-based family (NSW, HNSW, NSG), and the modern disk/GPU/billion-scale work (DiskANN, SPANN, FAISS-GPU, ScaNN).

Three reasons for this scope. It's a finite, densely interconnected cluster — these papers genuinely build on and compete with each other, which is what makes a relationship graph worth building instead of a pile of disconnected nodes. It has clear foundational anchors: PQ and NSW each root an entire sub-family, so questions like "what does this build on" and "what should I read first" have real answers. And I've done backend work with vector similarity and embedding-based retrieval, so I could annotate *why* two papers relate from actual understanding of the tradeoffs, not just guess from citations.

On corpus size: I targeted around 55 papers but landed 35 usable ones after data-source constraints (rate limits and missing metadata on older conference papers). I decided that was fine and leaned into it. The assignment rewards relationship density over shallow coverage, and 35 papers I understand well, each with hand-annotated edges, is worth more than 100 I'd have annotated thinly or mechanically. Depth was the right trade here, not a consolation.

## What entities and relationships I modeled, and the reasoning

**The core idea:** a citation tells you two papers are connected but not *how*. The same citation edge could mean "background," "direct extension," "benchmark baseline," or "competing approach." Semantic Scholar hands you the citation skeleton for free. My contribution is the layer that assigns *meaning* to those connections, plus a concept and problem layer that citations don't capture at all.

**Entities:**
- **Paper** — the primary node (title, year, venue, abstract, and its concept/problem tags).
- **Concept** — a technique or primitive in ANN (proximity graph, product quantization, greedy traversal, and so on). 26 of them, hand-curated with my own definitions and grouped into five categories (index-structure, compression, search-strategy, distance-metric, hardware-optimization). This taxonomy is the part no citation graph or extraction tool gives you.
- **Problem** — the recurring pain points papers try to solve (search accuracy, query latency, memory footprint, index build time, and so on). 8 of them. I deliberately separated these into two kinds: fundamental resource *axes* (accuracy, latency, memory, build time, update cost) and motivating *scenarios* (curse of dimensionality, billion-scale, disk-vs-RAM). The axes matter because they're what my tradeoff edges are built from.
- **Author** — kept deliberately thin. Modeling author influence is a rabbit hole that doesn't serve the novelty-check task, so I chose not to build it.

**Relationships** — this is the layer that's mine, not the API's:
- `EXTENDS` — builds directly on a prior method's mechanism (HNSW extends NSW).
- `TRADES_OFF_AGAINST` — my signature edge. Improves one axis at the cost of another versus a named baseline (HNSW trades memory for accuracy against PQ). It carries explicit `improves` and `at_cost_of` fields drawn from the problem axes. This edge encodes the single most important thing about this field — that graph-vs-quantization is fundamentally a recall-vs-memory decision — which a raw citation graph flattens completely.
- `ALTERNATIVE_TO` — solves the same problem via a different family.
- `COMBINES` — fuses two prior approaches (IVFADC combines IVF and PQ).
- `INTRODUCES` / `APPLIES` / `ADDRESSES` — link papers to the concepts they originate or use and the problems they target.

Every edge carries an **evidence** field (a short justification, ideally grounded in the paper) and a **confidence** level (`high` for textbook facts, `medium` for tradeoff judgments I'm inferring rather than quoting). The confidence field is deliberate honesty: it lets a reader see which relationships are asserted from the source and which are my domain inference, instead of pretending everything is equally certain.

There's also one **derived** relationship I compute rather than annotate: `IS_FOUNDATIONAL_FOR`, where a paper introduces a concept and has a high in-degree of EXTENDS edges pointing at it. On this corpus that surfaces PQ and NSW — correctly, since those are the two papers everything downstream builds on. Notably HNSW does *not* come out as foundational here, because my scoped corpus includes its ancestors and its alternatives but few of its direct descendants. That's a faithful reflection of the authored edges rather than the paper's general reputation, and I think it's the right behavior — the graph should report what it actually contains.

## How the representation was built, and the tradeoffs

I fetched paper metadata from the Semantic Scholar API (with an arXiv fallback for abstracts that were missing), then annotated everything by hand against my own schema. No automated entity or relationship extraction — the concept definitions, the edge types, and every individual edge are mine. LLM assistance was used for scaffolding and code, not for deciding the modeling.

Key tradeoffs I made:

- **Structure-first, embeddings-second.** Only 20 of the 35 papers have abstracts available (older conference papers often have none in any open source). Rather than let that break the system, I built matching to run primarily on the concept tags I hand-assigned to *every* paper, with abstract similarity as an optional bonus. This turned out to be the better design anyway — it leans on the hand-built structure the assignment cares about instead of on embeddings, and it degrades gracefully. A paper with no abstract still participates fully through its concepts and edges.
- **NetworkX in-memory, not a graph database.** At 35 papers, Neo4j would add setup friction for a reviewer and buy nothing analytically.
- **Abstract-level, not full-text.** Full-text parsing is a time sink, and the abstract plus my annotations is enough to place a paper.
- **The knowledge state is a single flat JSON file**, readable and navigable without running any code — you can open `knowledge/knowledge_state.json` and see every paper, concept, problem, and edge directly.

## How the system works when a new input arrives

A new abstract goes through three stages:

1. **Match** (`reason/match.py`) — the abstract is scored against every concept and problem using keyword/phrase matching over concept names and definitions (with light stemming so "neighbor"/"neighbors" collapse, and phrase matching so multi-word concept names count as units). Concepts are weighted by an IDF-style factor so that generic concepts appearing across most papers count for less than distinctive ones. Embedding similarity is layered on if `sentence-transformers` is available, but the system works fully without it.
2. **Rank** (`reason/engine.py`) — this is where the reasoning happens, over graph structure rather than similarity. Each candidate paper is scored on three graph-derived signals: whether it's foundational for a strongly-matched concept, how close it sits (in EXTENDS hops) to a foundational paper for those concepts, and its own concept overlap with the abstract. Crucially, the foundational and lineage bonuses are weighted *per concept by how strongly the abstract matched that specific concept* — so a paper doesn't get credit for being foundational on an axis the new abstract isn't even about.
3. **Assemble** (`reason/novelty.py`) — the structured output: placement, closest prior work with the nature of each relation, overlapping-vs-novel concepts, known objections (surfaced from TRADES_OFF_AGAINST edges on the axis the abstract claims to improve), and a reading path traced through EXTENDS chains.

Everything in the output is derivable from the graph. An LLM could rephrase the result into prose, but it makes none of the decisions — the placement and ranking are graph traversal and edge semantics, not generation.

I validated this on held-out papers not in the corpus. A GPU graph-index paper (CAGRA, 2023) surfaces the graph/disk lineage — NSW, HNSW, DiskANN, BANG — at the top, with a NSW->NSG->DiskANN reading path. A graph-routing paper (Probabilistic Routing, 2024) surfaces DiskANN and the graph family. Both land in the right neighborhood, which is the real test.

**Getting the ranking right was iterative, and worth being honest about.** The first version had four distinct failures I diagnosed and fixed in turn: naive tokenization missed plural/suffix variants; a flat foundational bonus let an incidental weak match outrank a strong central one; a top-k truncation silently zeroed the score of relevant papers just below a cutoff; and generic boilerplate concepts were weighted like distinctive ones, which IDF fixed — until IDF over-rewarded singleton concepts (a concept tagged on exactly one paper), which I floored. Each fix was a principled method, not a magic-number tweak, and each revealed the next. That progression is itself the honest picture of building a ranking function over a small hand-curated graph.

## The limits, honestly

- **Keyword matching has a ceiling.** On a 35-paper corpus with many singleton concepts, the exact #1 ranking is sensitive to surface-form overlap. The system reliably surfaces the right *family*, but the precise top position can wobble. Embedding-based matching is the clean fix and is the first thing I'd add.
- **The foundational signal reflects the corpus, not the field.** HNSW doesn't register as foundational here because I didn't include its descendants — a scoping consequence, not a bug, but worth naming.
- **Abstract coverage is partial** (20/35), which limits the embedding signal until those are backfilled.
- **Taxonomy gaps I noticed while annotating.** While hand-annotating, I hit three spots where my taxonomy was slightly too coarse: LSH papers currently fold into a generic "hash-bucket-index" concept rather than having "locality-sensitive-hashing" as a first-class concept; ScaNN's anisotropic quantization maps onto product-quantization + inner-product rather than its own concept; and "gpu-acceleration" ended up straddling the concept and problem layers before I settled it as a concept. None broke the graph, but they're the natural next refinements to the schema and a sign of where a second annotation pass would tighten things.

## What I'd build next, and why

1. **Embeddings for matching.** This closes the bag-of-words ceiling directly — semantic similarity would catch a quantization paper that says "compact codes" instead of "quantization," which keyword matching misses. Biggest single improvement for the effort.
2. **Extend the corpus with HNSW's direct descendants.** This would let the foundational signal reflect HNSW's real central role, and generally deepen the graph-family lineage.
3. **Densify the OUTPERFORMS_ON edges** from results tables, which I kept sparse for time — these would make the "known objections" output sharper by grounding it in actual benchmark head-to-heads.
4. **A second reasoning flow** (reading-path-first, for onboarding) reusing the same graph — nearly free once the structure exists.
