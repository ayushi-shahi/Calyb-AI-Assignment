# approach.md — ANN Knowledge Graph

> Reviewer-facing. This is read before the code. Every section below is a *decision*
> with a *reason*. Fill the [BRACKETS] in your own voice — keep it tight and specific.

## 1. The subset of data I chose, and why
- Domain B (research papers), topic: **approximate nearest neighbor (ANN) search —
  algorithms and index structures only** (not applications, not embedding models).
- ~55 papers spanning the lineage: LSH -> product quantization -> IVF/IVFADC ->
  NSW -> HNSW -> DiskANN/ScaNN and billion-scale/GPU work.
- Why this scope: [it's a finite, densely inter-citing cluster with unambiguous
  foundational nodes; I understand the engineering tradeoffs firsthand, which lets me
  annotate semantic relationships from real judgment rather than guesswork; depth over
  breadth per the brief].

## 2. Entities and relationships I modeled — and the reasoning
### The core claim
A citation says two papers are *connected*; it does not say *how*. In ANN, the same
citation edge can mean "background," "direct extension," "benchmark baseline," or
"different family with a memory-vs-recall tradeoff." Semantic Scholar gives me the
citation skeleton for free — my contribution is the layer that assigns **meaning** to
those connections, plus a concept/problem layer citations don't capture at all.

### Entities
- Paper, Concept (hand-curated taxonomy, ~[N] concepts, my own definitions),
  Problem (closed set of ~[N] recurring pain points), Author (deliberately thin).
- Why a Concept + Problem layer: [it lets the system reason about *what a paper does*
  and *what it's for*, which is how a researcher actually places new work — not by who
  cites whom].

### Relationships (the part that is mine, not the API's)
- Paper->Paper: EXTENDS, TRADES_OFF_AGAINST (improves/at_cost_of), OUTPERFORMS_ON,
  COMBINES, ALTERNATIVE_TO
- Paper->Concept/Problem: INTRODUCES, APPLIES, ADDRESSES
- Concept->Concept: EVOLVED_FROM
- Derived (computed, not authored): IS_FOUNDATIONAL_FOR
- The signature edge is **TRADES_OFF_AGAINST**: [it encodes the memory/recall/latency
  tradeoffs that define this field and that no citation graph or extraction tool
  produces. Example: HNSW vs PQ is graph-vs-quantization = recall-vs-memory].
- Every edge carries an **evidence** field and a **confidence** (high|medium):
  [evidence shows each edge was a decision, not an artifact; medium-confidence marks my
  domain inference vs verbatim-from-abstract claims — honesty over overclaiming].

## 3. How the representation was built, and the tradeoffs
- Ingestion: S2 API pull -> raw citation skeleton, cached to disk.
- Annotation: **by hand**, using a fixed template (concepts -> introduces -> problems
  -> EXTENDS target -> ALTERNATIVE_TO + paired TRADES_OFF_AGAINST -> optional
  OUTPERFORMS_ON -> evidence). ~3-6 edges/paper.
- On the no-auto-extraction constraint: [state exactly what I did by hand vs where, if
  at all, an LLM was used as a *first-pass suggester that I verified*. If fully manual,
  say so — it's bulletproof. Whatever the choice, disclose it here.]
- Tradeoffs: NetworkX in-memory not Neo4j [reviewer setup friction, zero analytical loss
  at this scale]; abstract-level not full-text [full-text parsing is a time sink and the
  abstract + related-work is enough to place a paper]; 55 dense papers not 100 sparse
  [every criterion rewards relationship density].

## 4. How the system works when a new input arrives
Input: a paper abstract the graph has never seen.
1. Match abstract -> concepts/problems (embedding cosine vs concept definitions + paper
   abstracts; keyword backstop). *Embeddings are used only for similarity matching of
   new input against existing structure — not to extract entities.*
2. Pull the induced subgraph; rank prior work by **edge semantics**: foundational?
   lineage depth via EXTENDS? sitting on a TRADES_OFF edge on an axis this abstract
   claims to improve (= a known objection)?
3. Emit structured novelty assessment: closest prior work + relation, overlapping vs
   novel concepts, tradeoff objections it will face, lineage reading path.
- Why this is reasoning not retrieval: [the placement and ranking come from graph
  structure and edge meaning; the output is derivable with the LLM switched off — an LLM
  only phrases it].

## 5. What I'd build next, and why
- [OUTPERFORMS_ON densification from results tables; author-influence layer; temporal
  trend view; full-text ingestion for finer evidence; a second reasoning flow. Pick 2-3
  and say why each matters and why it was correctly deprioritized for a 4-day build.]

## Appendix: worked example
[Include the HNSW / NSW / PQ annotation as a concrete illustration of the schema —
the EXTENDS chain and the HNSW-vs-PQ ALTERNATIVE_TO + dual TRADES_OFF_AGAINST.]
