# Held-out examples

These abstracts are **not** in the corpus (`data/raw/papers.json` / `knowledge/entities.json`).
They exist to demonstrate the reasoning pipeline (`match.py` -> `engine.py` -> `novelty.py`,
driven via `cli.py`) operating on genuinely new input the graph has never seen.

- `cagra.txt` — CAGRA: Highly Parallel Graph Construction and Approximate Nearest
  Neighbor Search for GPUs.
- `probabilistic-routing.txt` — Probabilistic Routing for Graph-Based Approximate
  Nearest Neighbor Search (arXiv:2402.11354).

Each `<name>.txt` has the paper's real title on the first line, a blank line, then its
real abstract (fetched from the arXiv API, not paraphrased).

Each `<name>.out.txt` is the corresponding `cli.py --file examples/<name>.txt` output:
the full structured JSON followed by the pretty-printed summary — regenerate with:

```
python cli.py --file examples/cagra.txt > examples/cagra.out.txt
python cli.py --file examples/probabilistic-routing.txt > examples/probabilistic-routing.out.txt
```
