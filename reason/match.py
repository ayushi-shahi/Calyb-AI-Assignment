"""Map a new abstract to candidate concepts/problems/papers (BUILD_SPEC.md section 6.1).

Two signals, combined:
  (a) keyword coverage of each concept/problem's own name+definition vocabulary
  (b) cosine similarity via sentence-transformers, if the library/model is available
Embeddings are optional -- if unavailable, everything still works on keyword matching
alone, with nearest_papers falling back to concept-overlap instead of cosine similarity.
Corpus-side embeddings (concept defs, paper abstracts) are cached to data/embeddings.npz,
keyed by a content hash so edits to entities.json invalidate the cache automatically.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTITIES_PATH = REPO_ROOT / "knowledge" / "entities.json"
EMBEDDINGS_CACHE_PATH = REPO_ROOT / "data" / "embeddings.npz"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

DEFAULT_TOP_CONCEPTS = 8
DEFAULT_TOP_PROBLEMS = 5
DEFAULT_K_PAPERS = 5

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "for",
    "from", "has", "have", "in", "into", "is", "it", "its", "of", "on", "or", "our",
    "over", "that", "the", "their", "then", "this", "to", "using", "use", "used",
    "we", "were", "which", "with", "within", "without", "would", "than", "based",
    "such", "each", "these", "also", "not", "any", "both",
}

# Ordered longest-suffix-first so e.g. "ization" is tried before the shorter "s".
# Not a linguistically correct stemmer -- just enough surface-form normalization
# (plurals, -ing/-ed, and the -ize/-ization family) that "neighbor"/"neighbors",
# "graph"/"graphs", "quantize"/"quantization" collapse to the same token for
# matching purposes. Applied identically to query and target text, so it only
# needs to be *consistent*, not grammatically correct.
_STEM_RULES = sorted([
    ("ization", ""), ("isation", ""),
    ("ation", ""), ("ssion", "ss"),
    ("ized", ""), ("ised", ""), ("tion", "t"),
    ("ing", ""), ("ies", "y"), ("ize", ""), ("ise", ""),
    ("es", ""), ("ed", ""), ("s", ""),
], key=lambda rule: -len(rule[0]))


def stem(token):
    for suffix, replacement in _STEM_RULES:
        if token.endswith(suffix) and len(token) > len(suffix):
            stemmed = token[: -len(suffix)] + replacement
            return stemmed if len(stemmed) >= 3 else token
    return token


def _raw_tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3 and t not in STOPWORDS]


def tokenize(text):
    """Stemmed token set, for bag-of-words overlap scoring."""
    return {stem(t) for t in _raw_tokens(text)}


def stem_sequence(text):
    """Stemmed tokens in original order (stopwords dropped), for phrase matching."""
    return [stem(t) for t in _raw_tokens(text)]


def load_entities(path=ENTITIES_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _contains_phrase(sequence, phrase_tokens):
    n = len(phrase_tokens)
    if n == 0 or n > len(sequence):
        return False
    return any(sequence[i:i + n] == phrase_tokens for i in range(len(sequence) - n + 1))


def _split_name(name):
    """'Inverted File Index (IVF)' -> ('Inverted File Index', 'IVF')."""
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", name.strip())
    return (m.group(1).strip(), m.group(2).strip()) if m else (name.strip(), None)


# Name matches count more than incidental definition/description words, and an
# exact multi-word name phrase found in the abstract counts most of all -- these
# three add up to at most 1.0 so a full-signal hit still reads as a clean 1.0.
W_NAME = 0.5
W_DESC = 0.2
W_PHRASE = 0.3


def _lexical_index(item, name_field, desc_field):
    main_name, acronym = _split_name(str(item.get(name_field) or ""))
    return {
        "name_tokens": tokenize(main_name),
        "name_phrase": stem_sequence(main_name),
        "acronym": acronym.lower() if acronym else None,
        "desc_tokens": tokenize(str(item.get(desc_field) or "")),
    }


def _lexical_score(index, abstract_tokens, abstract_raw_tokens, abstract_phrase_seq):
    name_tokens = index["name_tokens"]
    name_overlap = len(abstract_tokens & name_tokens) / len(name_tokens) if name_tokens else 0.0

    desc_tokens = index["desc_tokens"]
    desc_overlap = len(abstract_tokens & desc_tokens) / len(desc_tokens) if desc_tokens else 0.0

    phrase_hit = _contains_phrase(abstract_phrase_seq, index["name_phrase"])
    if not phrase_hit and index["acronym"]:
        phrase_hit = index["acronym"] in abstract_raw_tokens

    score = W_NAME * name_overlap + W_DESC * desc_overlap + W_PHRASE * (1.0 if phrase_hit else 0.0)
    return min(1.0, score)


_model = None
_model_load_attempted = False


def get_embedding_model():
    """Lazily load sentence-transformers; returns None (and warns once) if the
    library isn't installed or the model can't be loaded."""
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print(
            "match.py: sentence-transformers not installed -- falling back to keyword-only matching.",
            file=sys.stderr,
        )
        return None
    try:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception as exc:
        print(
            f"match.py: could not load embedding model ({exc}) -- falling back to keyword-only matching.",
            file=sys.stderr,
        )
        _model = None
    return _model


def _corpus_hash(entities):
    parts = []
    for p in sorted(entities["papers"], key=lambda x: x["id"]):
        if p.get("abstract"):
            parts.append(f"P|{p['id']}|{p['abstract']}")
    for c in sorted(entities["concepts"], key=lambda x: x["id"]):
        parts.append(f"C|{c['id']}|{c['definition']}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def load_or_build_corpus_embeddings(model, entities, cache_path=EMBEDDINGS_CACHE_PATH):
    corpus_hash = _corpus_hash(entities)
    if cache_path.exists():
        cached = np.load(cache_path, allow_pickle=True)
        if str(cached["corpus_hash"]) == corpus_hash:
            return (
                list(cached["paper_ids"]), cached["paper_vectors"],
                list(cached["concept_ids"]), cached["concept_vectors"],
            )

    paper_items = [(p["id"], p["abstract"]) for p in entities["papers"] if p.get("abstract")]
    concept_items = [(c["id"], f"{c['name']}: {c['definition']}") for c in entities["concepts"]]

    dim = model.get_sentence_embedding_dimension()
    paper_ids = [i for i, _ in paper_items]
    paper_vectors = (
        model.encode([t for _, t in paper_items], normalize_embeddings=True)
        if paper_items else np.zeros((0, dim), dtype=np.float32)
    )
    concept_ids = [i for i, _ in concept_items]
    concept_vectors = model.encode([t for _, t in concept_items], normalize_embeddings=True)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        cache_path,
        paper_ids=np.array(paper_ids), paper_vectors=paper_vectors,
        concept_ids=np.array(concept_ids), concept_vectors=concept_vectors,
        corpus_hash=np.array(corpus_hash),
    )
    return paper_ids, paper_vectors, concept_ids, concept_vectors


def _cosine_one_to_many(vec, matrix):
    if matrix.shape[0] == 0:
        return np.zeros(0)
    return matrix @ vec  # rows are already L2-normalized (normalize_embeddings=True)


def match(abstract, entities=None, k=DEFAULT_K_PAPERS, use_embeddings=True,
          top_concepts=DEFAULT_TOP_CONCEPTS, top_problems=DEFAULT_TOP_PROBLEMS):
    entities = entities or load_entities()
    concepts, problems, papers = entities["concepts"], entities["problems"], entities["papers"]

    concept_lex_index = {c["id"]: _lexical_index(c, "name", "definition") for c in concepts}
    problem_lex_index = {p["id"]: _lexical_index(p, "name", "description") for p in problems}

    abstract_tokens = tokenize(abstract)
    abstract_raw_tokens = set(_raw_tokens(abstract))
    abstract_phrase_seq = stem_sequence(abstract)

    keyword_concept_scores = {
        cid: _lexical_score(idx, abstract_tokens, abstract_raw_tokens, abstract_phrase_seq)
        for cid, idx in concept_lex_index.items()
    }
    keyword_problem_scores = {
        pid: _lexical_score(idx, abstract_tokens, abstract_raw_tokens, abstract_phrase_seq)
        for pid, idx in problem_lex_index.items()
    }

    model = get_embedding_model() if use_embeddings else None
    embeddings_used = model is not None

    embed_concept_scores, embed_paper_scores = {}, {}
    if embeddings_used:
        paper_ids, paper_vectors, concept_ids, concept_vectors = load_or_build_corpus_embeddings(model, entities)
        abstract_vec = model.encode([abstract], normalize_embeddings=True)[0]
        if len(concept_ids):
            sims = _cosine_one_to_many(abstract_vec, concept_vectors)
            embed_concept_scores = dict(zip(concept_ids, sims.tolist()))
        if len(paper_ids):
            sims = _cosine_one_to_many(abstract_vec, paper_vectors)
            embed_paper_scores = dict(zip(paper_ids, sims.tolist()))

    def combine(kw, emb):
        if emb is None:
            return kw
        return 0.5 * kw + 0.5 * max(0.0, emb)

    candidate_concepts = []
    for c in concepts:
        kw = keyword_concept_scores.get(c["id"], 0.0)
        emb = embed_concept_scores.get(c["id"])
        score = combine(kw, emb)
        if score > 0:
            candidate_concepts.append({
                "id": c["id"], "name": c["name"],
                "keyword_score": round(kw, 4),
                "embedding_score": round(emb, 4) if emb is not None else None,
                "score": round(score, 4),
            })
    candidate_concepts.sort(key=lambda x: -x["score"])
    candidate_concepts = candidate_concepts[:top_concepts]

    candidate_problems = []
    for p in problems:
        kw = keyword_problem_scores.get(p["id"], 0.0)
        if kw > 0:
            candidate_problems.append({"id": p["id"], "name": p["name"], "keyword_score": round(kw, 4), "score": round(kw, 4)})
    candidate_problems.sort(key=lambda x: -x["score"])
    candidate_problems = candidate_problems[:top_problems]

    nearest_papers = []
    if embeddings_used and embed_paper_scores:
        ranked = sorted(embed_paper_scores.items(), key=lambda x: -x[1])[:k]
        titles = {p["id"]: p["title"] for p in papers}
        for pid, score in ranked:
            nearest_papers.append({"id": pid, "title": titles.get(pid, pid), "score": round(max(0.0, score), 4), "signal": "embedding"})
    else:
        candidate_ids = {c["id"] for c in candidate_concepts}
        scored = []
        for p in papers:
            paper_concepts = set(p.get("concepts") or [])
            overlap = candidate_ids & paper_concepts
            if not overlap:
                continue
            jaccard = len(overlap) / len(candidate_ids | paper_concepts)
            scored.append((p, jaccard))
        scored.sort(key=lambda x: -x[1])
        for p, score in scored[:k]:
            nearest_papers.append({"id": p["id"], "title": p["title"], "score": round(score, 4), "signal": "concept-overlap"})

    return {
        "abstract": abstract,
        "embeddings_used": embeddings_used,
        "candidate_concepts": candidate_concepts,
        "candidate_problems": candidate_problems,
        "nearest_papers": nearest_papers,
    }


if __name__ == "__main__":
    result = match(
        "We propose a graph-based index that reduces memory footprint by storing "
        "compressed neighbor lists while preserving high recall for billion-scale "
        "approximate nearest neighbor search."
    )
    print(json.dumps(result, indent=2))
