# approach.md

## What this is

I built a system that helps you place a new research paper within a field. You give it a paper's abstract — one it has never seen before — and it tells you where that idea fits: which existing papers are closest, how the new idea relates to them, what parts of it are genuinely new versus already well-covered, what objections it's likely to face, and what to read to understand the lineage it belongs to.

The important part: this is not a search engine. A search would just find papers that use similar words. This tells you *where an idea sits in the field and why* — which is what you actually need when you're trying to figure out whether your contribution is new.

I chose the field of **approximate nearest neighbor (ANN) search** — the algorithms behind vector search.

## What data I used, and why

I focused on ANN search algorithms and index structures themselves — not where they get used (like RAG or recommendation systems), just the core methods. The final set is 35 papers covering the main storyline of the field:

- the early methods and why they broke down in high dimensions (KD-trees, LSH),
- the compression family that shrinks vectors to save memory (Product Quantization and its descendants),
- the inverted-file methods that only search part of the data,
- the graph-based family that's dominant today (NSW, HNSW, NSG),
- and the modern billion-scale and GPU work (DiskANN, SPANN, FAISS-GPU, ScaNN).

Why this scope? Three reasons.

These papers actually build on and compete with each other, so there are real relationships to map — not just a pile of unconnected papers. The field also has clear starting points (Product Quantization and NSW each kick off a whole branch), so questions like "what does this build on?" have honest answers. And I've done backend work with vector similarity and embeddings myself, so I could judge *why* two papers relate from real understanding, instead of guessing from citations.

On the number of papers: I aimed for around 55 but ended up with 35 usable ones, mostly because older conference papers were hard to fetch cleanly. I decided that was fine. The assignment rewards depth of relationships over shallow breadth, and 35 papers I actually understand — each with hand-drawn connections — is worth more than 100 I'd have connected carelessly. I treated the smaller set as a choice, not a compromise.

## The entities and relationships I modeled

**The core idea behind the whole thing:** a citation tells you two papers are connected, but not *how*. One paper citing another could mean "this is background," or "we build directly on this," or "we beat this in our benchmarks," or "we disagree with this." Same citation, completely different meanings. Semantic Scholar gives you the raw citations for free. My real work is the layer on top that says what each connection actually *means* — plus a layer of concepts and problems that citations don't capture at all.

**The things in the graph (entities):**

- **Papers** — the main nodes.
- **Concepts** — the techniques and ideas in ANN (proximity graph, product quantization, greedy search, and so on). There are 26, and I wrote every definition myself, grouped into five families (index structures, compression, search strategies, distance metrics, hardware tricks). This is exactly the part no tool can hand you.
- **Problems** — the recurring pains these papers try to solve (accuracy, speed, memory, build time, and so on). There are 8. I split them into two kinds on purpose: the resource *tradeoffs* you're always balancing (accuracy vs. speed vs. memory), and the bigger *situations* driving the work (high dimensions, billion-scale data). The tradeoff ones matter because my most important relationship type is built from them.
- **Authors** — kept minimal on purpose. Modeling who-influences-whom is a whole project of its own and doesn't help the main task, so I skipped it.

**The connections (relationships)** — this is the layer that's mine, not the API's:

- **EXTENDS** — builds directly on an earlier method (HNSW extends NSW).
- **TRADES_OFF_AGAINST** — my most important one. Says a paper improves one thing at the cost of another, compared to a specific rival (HNSW gets better accuracy than Product Quantization, but uses more memory). It captures the single biggest truth in this field — that graph methods vs. compression methods is really a *memory vs. accuracy* choice — which raw citations completely miss.
- **ALTERNATIVE_TO** — solves the same problem a different way.
- **COMBINES** — merges two earlier ideas.
- **INTRODUCES / APPLIES / ADDRESSES** — link papers to the concepts they invented or used, and the problems they tackle.

Every connection carries a short note explaining *why* I drew it, plus a confidence level — "high" when it's a plain fact from the paper, "medium" when it's my own judgment about a tradeoff. I did that on purpose: it lets anyone reading see which relationships are solid facts and which are my inference, instead of pretending everything is equally certain.

There's also one relationship the system works out on its own rather than me drawing it: **IS_FOUNDATIONAL_FOR** — a paper counts as foundational if it introduced a concept and lots of later papers build on it. On my set, that correctly surfaces Product Quantization and NSW, the two papers everything else grows out of. Interestingly, HNSW does *not* show up as foundational — because my corpus has HNSW's ancestors and its rivals, but not many of its direct descendants. I think that's the right behavior: the graph should report what it actually contains, not what's famous in general.

## How I built it, and the tradeoffs I made

I pulled paper details from the Semantic Scholar API (falling back to arXiv when abstracts were missing), then connected everything by hand using my own schema. No automatic extraction tools — every concept definition and every connection is mine. I used AI help for writing the plumbing code, not for any of the modeling decisions.

The main tradeoffs:

- **Structure first, embeddings second.** Only 20 of the 35 papers even have abstracts available (older ones often don't, anywhere). So instead of relying on abstract text, I built the matching to run mainly on the concept tags I assigned to *every* paper by hand, with abstract similarity as an optional extra. This turned out better anyway — it leans on the hand-built structure, which is the whole point, and it still works fine for a paper with no abstract.
- **Simple in-memory graph, not a database.** For 35 papers, a heavy graph database would just add setup pain for whoever runs this, with no real benefit.
- **Abstracts, not full papers.** Parsing full PDFs is a big time sink, and the abstract plus my own tags is enough to place a paper.
- **One readable file for the knowledge.** The whole graph exports to a single JSON file you can open and read directly — every paper, concept, problem, and connection — without running any code.

## What happens when you give it a new paper

Three steps:

1. **Match** — it reads the new abstract and figures out which concepts and problems it's about, using keyword and phrase matching (with a little normalization so "neighbor" and "neighbors" count as the same word). Common, generic concepts are weighted down so distinctive ones matter more. If the embeddings library is installed it uses that too, but it works fine without it.
2. **Rank** — this is where the actual reasoning happens, using the *graph* rather than word similarity. Each candidate paper is scored on whether it's foundational for a concept the new paper strongly cares about, how close it sits to a foundational paper in the "builds on" chain, and how much it overlaps in concepts. The key detail: a paper only gets credit for being foundational on the topics the new paper is *actually about* — not for being important in some unrelated corner.
3. **Assemble** — it packages the result: where the paper fits, the closest prior work and how each one relates, what's overlapping vs. new, the objections it'll likely face (pulled straight from the tradeoff connections), and a reading path along the "builds on" chain.

Everything in that output comes from the graph. An AI could rewrite it into nicer prose, but it makes none of the decisions — the placement and ranking are pure graph logic.

I tested this on papers that aren't in the corpus at all. A 2023 GPU graph paper (CAGRA) correctly surfaces the graph/disk family — NSW, HNSW, DiskANN — and traces a NSW → NSG → DiskANN reading path. A 2024 graph-routing paper lands on DiskANN and the graph family. Both end up in the right neighborhood, which is the real test.

**Getting the ranking right took several honest rounds.** My first version had four separate problems, and I fixed them one at a time: word endings weren't being matched; a "foundational" bonus was too blunt and let unrelated famous papers win; a cutoff was silently dropping relevant papers; and generic filler concepts were counting as much as meaningful ones. Each fix was a real, named technique — not just fiddling with numbers — and each one exposed the next. That back-and-forth is the honest story of building a ranking system on a small, hand-made graph.

## Where it falls short (honestly)

- **Keyword matching has a ceiling.** On a small corpus, the exact #1 result can shift based on surface wording. It reliably finds the right *family* of papers, but the precise top spot can wobble. Real embeddings are the clean fix, and the first thing I'd add.
- **"Foundational" reflects my corpus, not the whole field.** HNSW doesn't register as foundational only because I didn't include its descendants — a scoping choice, not a bug, but worth being upfront about.
- **Only 20 of 35 papers have abstracts,** which limits the optional embedding path until the rest are filled in.
- **A few taxonomy gaps I noticed while annotating.** Hand-labeling surfaced three spots where my concept list was a bit too coarse: LSH papers fold into a generic "hash bucket" concept instead of having their own; ScaNN's special quantization gets mapped to nearby concepts rather than its own; and "GPU acceleration" briefly straddled being a concept and a problem before I settled it as a concept. None of these broke anything — they're just the obvious next things a second pass would tidy up.

## What I'd build next

1. **Real embeddings for matching** — the biggest single upgrade. It would catch a paper that says "compact codes" when my concept is called "quantization," which keyword matching misses today.
2. **Add HNSW's descendants to the corpus** — so the "foundational" signal reflects HNSW's real importance, and the graph family gets deeper.
3. **Fill in more "beats this in benchmarks" connections** — I kept these sparse for time; more of them would make the objections output sharper.
4. **A second mode focused on reading paths** for someone new to the field — nearly free to add, since the graph is already there.
