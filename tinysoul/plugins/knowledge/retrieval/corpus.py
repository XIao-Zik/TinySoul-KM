"""Knowledge corpus: query/backlinks/directory sources over the store.

Mirrors the Memory owner corpus contract: the caller receives every candidate
that satisfies scope and ``where`` constraints; lexical and embedding ranking,
fusion, model steps, snapshots, and pagination all belong to the kernel
retrieval pipeline. Backlinks come only from real ``km_links`` edges.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tinysoul.infra.concurrency import JoinedOperations
from tinysoul.infra.json import JsonObject
from tinysoul.infra.references import ReferenceError, ReferenceResolver
from tinysoul.kernel.retrieval.contracts import (
    BacklinksSource,
    DocumentQuery,
    EvidenceKind,
    QuerySource,
    RefsSource,
    RetrievalRequest,
    SearchCandidate,
    SearchEvidence,
    SearchFailure,
    SearchFailureKind,
)
from tinysoul.kernel.retrieval.operations import SearchCorpus
from tinysoul.kernel.retrieval.disclosure import (
    content_units,
    fragment_range,
    range_evidence,
)

from ..engine import KNOWLEDGE_SEARCH_FILTERS, KnowledgeEngine
from ..failures import KnowledgeContractError


def _attributes(entry, text: str) -> JsonObject:
    return {
        "source": entry.source,
        "tag": list(entry.tags),
        "updated_on": datetime.fromtimestamp(
            entry.mtime, tz=timezone.utc
        ).date().isoformat(),
        "chars": len(text),
    }


def knowledge_search_corpus(
    engine: KnowledgeEngine,
    request: RetrievalRequest,
    *,
    references: ReferenceResolver,
) -> SearchCorpus:
    source = request.source
    predicates = KNOWLEDGE_SEARCH_FILTERS.parse(getattr(source, "where", {}))

    def identity(ref: str) -> tuple[str, str]:
        resource, _, fragment = ref.partition("#")
        try:
            if resource.startswith("km:"):
                target = engine.canonical_reference(resource)
            else:
                target = references.resolve(resource)
        except Exception as exc:  # contract error -> reference error boundary
            raise ReferenceError(str(exc)) from exc
        return target.resource, fragment

    excluded = {identity(ref) for ref in request.exclude_refs}

    seeds: dict[str, list[tuple[str, str]]] = {}
    seed_order: dict[str, int] = {}
    if isinstance(source, RefsSource):
        for ref in source.refs:
            canonical, fragment = identity(ref)
            if (canonical, fragment) in excluded:
                continue
            selected_ref = canonical + ("#" + fragment if fragment else "")
            seed_order.setdefault(selected_ref, len(seed_order))
            pair = (selected_ref, fragment)
            if pair not in seeds.setdefault(canonical, []):
                seeds[canonical].append(pair)

    query = ""
    if isinstance(source, QuerySource):
        if isinstance(source.query, DocumentQuery):
            resource, _, fragment = source.query.document_ref.partition("#")
            if resource.startswith("km:"):
                target = engine.canonical_reference(resource)
            else:
                target = references.resolve(resource)
            query = engine.store.read_note(_path_for(engine, target.resource))
        else:
            query = source.query.text

    anchor_ids: tuple[str, ...] = ()
    if isinstance(source, BacklinksSource):
        resource, _, _ = source.anchor_ref.partition("#")
        if resource.startswith("km:"):
            target = engine.canonical_reference(resource)
        else:
            target = references.resolve(resource)
        anchor_ids = (target.resource.partition(":")[2],)

    candidates: list[SearchCandidate] = []
    scanned = 0
    for entry, text, units in engine.corpus_candidates():
        ref = engine.ref_for(entry.km_id)
        attributes = _attributes(entry, "")
        if not all(predicate.matches(attributes) for predicate in predicates):
            continue
        if isinstance(source, RefsSource) and ref not in seeds:
            continue
        if (ref, "") in excluded:
            continue
        attributes = _attributes(entry, text)
        scanned += 1
        if isinstance(source, RefsSource):
            for selected_ref, fragment in seeds[ref]:
                first, last = fragment_range(text, fragment)
                selected_text = "".join(
                    text.splitlines(keepends=True)[first - 1 : last]
                )
                candidates.append(
                    SearchCandidate(
                        selected_ref,
                        _display(entry),
                        content_units(ref, selected_text, first_line=first),
                        attributes,
                    )
                )
            continue
        evidence: list[SearchEvidence] = []
        if isinstance(source, BacklinksSource):
            # Real edges only: this document links to the anchor document.
            outgoing = {target_id for link in entry.links for target_id in engine.resolve_link_target(link)}
            if not (outgoing & set(anchor_ids)):
                continue
            for link in entry.links:
                for linked in engine.resolve_link_target(link):
                    if linked in anchor_ids:
                        position = text.find(link)
                        evidence.extend(
                            range_evidence(
                                units,
                                max(0, position),
                                position + len(link) if position >= 0 else len(text),
                                kind=EvidenceKind.REFERENCE,
                                relation="km_link",
                            )
                        )
        candidates.append(
            SearchCandidate(
                ref,
                _display(entry),
                units,
                attributes,
                tuple(dict.fromkeys(evidence)),
            )
        )

    if isinstance(source, RefsSource):
        candidates.sort(key=lambda item: seed_order[item.ref])
    return SearchCorpus(tuple(candidates), query, scanned)


def _display(entry) -> str:
    return entry.title or entry.path.removesuffix(".md").rsplit("/", 1)[-1]


def _path_for(engine: KnowledgeEngine, resource: str) -> str:
    """Store-relative path for one canonical ``km:<id>`` resource."""

    entry = engine.index.get_by_km_id(resource.partition(":")[2])
    if entry is None:
        raise KnowledgeContractError(
            f"Knowledge document does not exist: {resource}"
        )
    return entry.path
