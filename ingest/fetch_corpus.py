"""Resolve ingest/seeds.md titles to Semantic Scholar paperIds and fetch full
paper details.

    python ingest/fetch_corpus.py

Writes data/raw/papers.json. Prints a resolution coverage report to stdout.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEEDS_PATH = REPO_ROOT / "ingest" / "seeds.md"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "raw" / "papers.json"

S2_BASE = "https://api.semanticscholar.org/graph/v1"
S2_API_KEY = os.environ.get("S2_API_KEY")
SEARCH_FIELDS = "paperId,title,year"
BATCH_FIELDS = (
    "paperId,title,year,venue,abstract,authors,references.paperId,citations.paperId"
)
BATCH_CHUNK_SIZE = 100

MAX_RETRIES = 6
INITIAL_BACKOFF_SECONDS = 1.0
REQUEST_PAUSE_SECONDS = 1.1  # respect the ~1 req/sec limit for keyed requests

SEED_LINE_RE = re.compile(r"^-\s*(?:✅\s*)?(?P<title>.+?)\s+—\s+.+?—\s+(?P<year>\d{4})")


def parse_seeds(path):
    """Extract deduped (title, year) seeds from seeds.md bullet lines."""
    seeds = []
    seen = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("-"):
            continue
        m = SEED_LINE_RE.match(line)
        if not m:
            print(f"WARN: could not parse seed line, skipping: {line}", file=sys.stderr)
            continue
        title = m.group("title").strip()
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        seeds.append({"title": title, "year": int(m.group("year"))})
    return seeds


def normalize_title(title):
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def request_with_backoff(client, method, url, **kwargs):
    backoff = INITIAL_BACKOFF_SECONDS
    for attempt in range(1, MAX_RETRIES + 1):
        response = client.request(method, url, **kwargs)
        if response.status_code != 429:
            return response
        if attempt == MAX_RETRIES:
            return response
        wait = backoff + (response.headers.get("Retry-After") and float(response.headers["Retry-After"]) or 0)
        print(f"  429 rate-limited, backing off {wait:.1f}s (attempt {attempt}/{MAX_RETRIES})", file=sys.stderr)
        time.sleep(wait)
        backoff *= 2
    return response


def resolve_title(client, seed):
    """Search S2 for a seed title, return (paperId, match_quality) or (None, reason)."""
    response = request_with_backoff(
        client,
        "GET",
        f"{S2_BASE}/paper/search",
        params={"query": seed["title"], "fields": SEARCH_FIELDS, "limit": 5},
    )
    time.sleep(REQUEST_PAUSE_SECONDS)

    if response.status_code != 200:
        return None, f"http {response.status_code}"

    results = response.json().get("data", [])
    if not results:
        return None, "no results"

    target_norm = normalize_title(seed["title"])
    for r in results:
        if normalize_title(r.get("title", "")) == target_norm:
            return r["paperId"], "exact"

    top = results[0]
    year_delta = abs((top.get("year") or 0) - seed["year"])
    if year_delta > 2:
        return top["paperId"], f"weak (top hit '{top.get('title')}', year off by {year_delta})"
    return top["paperId"], "fuzzy"


def fetch_batch(client, paper_ids):
    """Fetch full details for paperIds in chunks, return list of paper records."""
    papers = []
    for i in range(0, len(paper_ids), BATCH_CHUNK_SIZE):
        chunk = paper_ids[i : i + BATCH_CHUNK_SIZE]
        response = request_with_backoff(
            client,
            "POST",
            f"{S2_BASE}/paper/batch",
            params={"fields": BATCH_FIELDS},
            json={"ids": chunk},
        )
        time.sleep(REQUEST_PAUSE_SECONDS)
        if response.status_code != 200:
            print(
                f"ERROR: batch fetch failed for chunk {i // BATCH_CHUNK_SIZE} "
                f"(http {response.status_code}): {response.text[:200]}",
                file=sys.stderr,
            )
            continue
        papers.extend(p for p in response.json() if p is not None)
    return papers


def to_record(paper):
    return {
        "paperId": paper.get("paperId"),
        "title": paper.get("title"),
        "year": paper.get("year"),
        "venue": paper.get("venue"),
        "abstract": paper.get("abstract"),
        "authors": [a.get("name") for a in paper.get("authors") or []],
        "references": [r["paperId"] for r in paper.get("references") or [] if r.get("paperId")],
        "citations": [c["paperId"] for c in paper.get("citations") or [] if c.get("paperId")],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    seeds = parse_seeds(args.seeds)
    print(f"Parsed {len(seeds)} deduped seed titles from {args.seeds}")

    headers = {"User-Agent": "ann-kg-ingest/1.0"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY
    else:
        print(
            "WARN: S2_API_KEY not set — falling back to the unauthenticated pool "
            "(much lower rate limit, expect more 429s).",
            file=sys.stderr,
        )

    resolved = []   # [{seed, paperId, quality}]
    failed = []     # [{seed, reason}]

    with httpx.Client(timeout=30.0, headers=headers) as client:
        for i, seed in enumerate(seeds, 1):
            paper_id, info = resolve_title(client, seed)
            if paper_id is None:
                failed.append({"title": seed["title"], "year": seed["year"], "reason": info})
                print(f"[{i}/{len(seeds)}] FAIL   {seed['title']!r} ({info})")
            else:
                resolved.append({"title": seed["title"], "year": seed["year"], "paperId": paper_id, "quality": info})
                print(f"[{i}/{len(seeds)}] OK     {seed['title']!r} -> {paper_id} ({info})")

        unique_ids = sorted({r["paperId"] for r in resolved})
        print(f"\nResolved {len(resolved)}/{len(seeds)} titles -> {len(unique_ids)} unique paperIds")
        print("Fetching full details in batches...")
        papers = fetch_batch(client, unique_ids)

    records = [to_record(p) for p in papers]
    fetched_ids = {r["paperId"] for r in records}
    missing_after_batch = [pid for pid in unique_ids if pid not in fetched_ids]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Coverage report ===")
    print(f"Seeds parsed:            {len(seeds)}")
    print(f"Resolved (search):       {len(resolved)}")
    print(f"Unresolved (search):     {len(failed)}")
    print(f"Unique paperIds:         {len(unique_ids)}")
    print(f"Fetched w/ full details: {len(records)}")
    if missing_after_batch:
        print(f"Resolved but missing from batch response: {len(missing_after_batch)}")
        for pid in missing_after_batch:
            print(f"  - {pid}")
    weak = [r for r in resolved if r["quality"] != "exact" and r["quality"] != "fuzzy"]
    if weak:
        print(f"\nWeak matches (verify manually): {len(weak)}")
        for r in weak:
            print(f"  - {r['title']!r}: {r['quality']}")
    if failed:
        print(f"\nFailed to resolve: {len(failed)}")
        for f in failed:
            print(f"  - {f['title']!r} ({f['year']}): {f['reason']}")
    print(f"\nWrote {len(records)} paper records to {args.output}")


if __name__ == "__main__":
    main()
