"""Backfill missing abstracts in data/raw/papers.json from the arXiv API.

For every paper record with abstract null/empty, searches arXiv by title and,
on a confident (normalized exact) title match, fills in arXiv's abstract.
Never overwrites an abstract that already exists. Updates papers.json in place.

    python ingest/backfill_abstracts.py
"""
import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PAPERS_PATH = REPO_ROOT / "data" / "raw" / "papers.json"

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
REQUEST_PAUSE_SECONDS = 3.0  # 1 request per 3 seconds


def normalize_title(title):
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def clean_abstract(text):
    return re.sub(r"\s+", " ", text).strip()


def search_arxiv(client, title):
    """Query arXiv by title, return cleaned abstract on a confident match, else None."""
    response = client.get(
        ARXIV_API,
        params={"search_query": f'ti:"{title}"', "max_results": 5},
    )
    if response.status_code != 200:
        print(f"  ERROR: arXiv http {response.status_code}", file=sys.stderr)
        return None

    root = ET.fromstring(response.text)
    target_norm = normalize_title(title)
    for entry in root.findall("atom:entry", ARXIV_NS):
        entry_title = entry.findtext("atom:title", default="", namespaces=ARXIV_NS)
        if normalize_title(entry_title) == target_norm:
            summary = entry.findtext("atom:summary", default="", namespaces=ARXIV_NS)
            if summary.strip():
                return clean_abstract(summary)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", type=Path, default=DEFAULT_PAPERS_PATH)
    args = parser.parse_args()

    papers = json.loads(args.papers.read_text(encoding="utf-8"))
    missing = [p for p in papers if not p.get("abstract")]
    print(f"Loaded {len(papers)} papers, {len(missing)} missing an abstract")

    recovered = []
    still_missing = []

    with httpx.Client(
        timeout=30.0, headers={"User-Agent": "ann-kg-ingest/1.0"}, follow_redirects=True
    ) as client:
        for i, paper in enumerate(missing, 1):
            title = paper.get("title") or ""
            print(f"[{i}/{len(missing)}] {title!r}", end=" ")
            abstract = search_arxiv(client, title) if title else None
            if abstract:
                paper["abstract"] = abstract
                recovered.append(title)
                print("-> recovered")
            else:
                still_missing.append(title)
                print("-> no confident match")
            time.sleep(REQUEST_PAUSE_SECONDS)

    args.papers.write_text(json.dumps(papers, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Backfill report ===")
    print(f"Recovered:     {len(recovered)}/{len(missing)}")
    for t in recovered:
        print(f"  - {t!r}")
    print(f"Still missing: {len(still_missing)}/{len(missing)}")
    for t in still_missing:
        print(f"  - {t!r}")
    print(f"\nUpdated {args.papers}")


if __name__ == "__main__":
    main()
