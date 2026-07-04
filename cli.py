"""CLI entry point for the ANN novelty-assessment pipeline.

    python cli.py --abstract "PASTE TEXT"
    python cli.py --file path/to/abstract.txt

Loads knowledge/knowledge_state.json and runs match -> engine -> novelty. No network
call is required at query time (embeddings, if used at all, are optional and cached).
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "reason"))

import novelty  # noqa: E402


def _read_abstract(args):
    if args.file:
        path = Path(args.file)
        if not path.exists():
            return None, f"File not found: {path}"
        text = path.read_text(encoding="utf-8").strip()
    elif args.abstract is not None:
        text = args.abstract.strip()
    else:
        return None, 'No input given. Pass --abstract "..." or --file path/to/abstract.txt.'
    if not text:
        return None, "The abstract text is empty."
    return text, None


def _print_summary(result):
    def header(title):
        print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")

    header("PLACEMENT")
    print("Nearest concepts:")
    for c in result["placement"]["nearest_concepts"]:
        print(f"  - {c['name']} (score={c['score']})")
    print("Addressed problems:")
    for p in result["placement"]["addressed_problems"]:
        print(f"  - {p['name']} (score={p['score']})")

    header("CLOSEST PRIOR WORK")
    if not result["closest_prior_work"]:
        print("(none found)")
    for w in result["closest_prior_work"]:
        print(f"- {w['paper']}")
        print(f"    relation: {w['relation']}")
        if w["overlap"]:
            print(f"    overlap: {', '.join(w['overlap'])}")

    header("NOVELTY ASSESSMENT")
    na = result["novelty_assessment"]
    print("Overlapping claims (shared with closest prior work):")
    for c in na["overlapping_claims"] or ["(none)"]:
        print(f"  - {c}")
    print("Apparently novel (not covered by closest prior work):")
    for c in na["apparently_novel"] or ["(none)"]:
        print(f"  - {c}")

    header("KNOWN OBJECTIONS")
    if not result["known_objections"]:
        print("(none found)")
    for o in result["known_objections"]:
        print(f"- from {o['from_paper']!r} on axis '{o['axis']}':")
        print(f"    {o['objection']}")

    header("SUGGESTED READING PATH")
    print(" -> ".join(result["suggested_reading_path"]) if result["suggested_reading_path"] else "(no path found)")


def main():
    parser = argparse.ArgumentParser(description="Assess a new ANN paper abstract against the knowledge graph.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--abstract", type=str, help="Abstract text, inline.")
    group.add_argument("--file", type=str, help="Path to a file containing the abstract text.")
    args = parser.parse_args()

    abstract, error = _read_abstract(args)
    if error:
        print(f"Error: {error}\n", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    try:
        result = novelty.assemble(abstract)
    except FileNotFoundError as exc:
        print(
            f"Error: {exc}\nHave you run knowledge/build_graph.py and knowledge/export_state.py "
            "to generate knowledge/knowledge_state.json?",
            file=sys.stderr,
        )
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    _print_summary(result)


if __name__ == "__main__":
    main()
