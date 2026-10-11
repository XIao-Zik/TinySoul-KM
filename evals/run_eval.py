"""TinySoul-KM retrieval evaluation harness (lexical baseline; vector when available).

Runs the knowledge corpus through the kernel lexical ranker without any LLM
call, so the harness is deterministic and free. Measures hit@1/5/10 and MRR
against `source_refs` ground truth. Usage:

    python evals/run_eval.py --root my-pkm --vault <vault> --qa evals/qa_set.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from tinysoul.infra.references import ReferenceResolver
from tinysoul.kernel.retrieval.contracts import (
    QuerySource,
    RetrievalRequest,
    TextQuery,
)
from tinysoul.kernel.retrieval.engine import lexical_rank
from tinysoul.plugins.knowledge.config import parse_knowledge_settings
from tinysoul.plugins.knowledge.engine import KnowledgeEngine
from tinysoul.plugins.knowledge.retrieval import knowledge_search_corpus


def _rank(engine: KnowledgeEngine, query: str):
    corpus = knowledge_search_corpus(
        engine,
        RetrievalRequest(source=QuerySource(scope="all", query=TextQuery(query))),
        references=ReferenceResolver(),
    )
    source = QuerySource(scope="all", query=TextQuery(query))
    return lexical_rank(source, query, corpus.candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description="KM retrieval evaluation")
    parser.add_argument("--root", type=Path, required=True, help="project root")
    parser.add_argument("--vault", type=Path, required=True, help="imported vault")
    parser.add_argument("--qa", type=Path, default=Path("evals/qa_set.jsonl"))
    parser.add_argument("--skip-ingest", action="store_true")
    args = parser.parse_args()

    settings = parse_knowledge_settings({}, project_root=args.root.resolve())
    engine = KnowledgeEngine(settings=settings)
    if not args.skip_ingest:
        started = time.perf_counter()
        report = engine.ingest_obsidian(args.vault.resolve())
        print(
            f"ingest: {report.summary()} in {time.perf_counter() - started:.1f}s",
            file=sys.stderr,
        )

    cases = [
        json.loads(line)
        for line in args.qa.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_path = {entry.path: entry for entry in engine.index.live()}
    hits = {1: 0, 5: 0, 10: 0}
    reciprocal = []
    per_kind: dict[str, list[int]] = {}
    for case in cases:
        ranked = _rank(engine, case["question"])
        expected = set(case["source_refs"])
        found_rank = None
        for rank, candidate in enumerate(ranked[:50], 1):
            km_id = candidate.ref.partition(":")[2]
            entry = by_path_of(engine, km_id)
            if entry is not None and entry.path in expected:
                found_rank = rank
                break
        for k in hits:
            if found_rank is not None and found_rank <= k:
                hits[k] += 1
        reciprocal.append(0.0 if found_rank is None else 1.0 / found_rank)
        per_kind.setdefault(case["kind"], []).append(1 if found_rank else 0)
        status = f"rank={found_rank}" if found_rank else "MISS"
        print(f"{case['id']}: {status}", file=sys.stderr)

    total = len(cases)
    print(f"questions={total}")
    for k, count in sorted(hits.items()):
        print(f"hit@{k}: {count / total:.3f}")
    print(f"MRR: {sum(reciprocal) / total:.3f}")
    for kind, flags in sorted(per_kind.items()):
        print(f"{kind}: {sum(flags)}/{len(flags)}")
    return 0


def by_path_of(engine: KnowledgeEngine, km_id: str):
    return engine.index.get_by_km_id(km_id)


if __name__ == "__main__":
    raise SystemExit(main())
