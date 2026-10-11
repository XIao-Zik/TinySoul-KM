"""Knowledge corpus tests over a temporary store (query/backlinks/refs/where)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tinysoul.infra.references import ReferenceResolver
from tinysoul.kernel.retrieval.contracts import (
    BacklinksSource,
    DirectorySource,
    DocumentQuery,
    QuerySource,
    RefsSource,
    RetrievalRequest,
    SearchFailure,
    TextQuery,
)
from tinysoul.plugins.knowledge.config import KnowledgeSettings
from tinysoul.plugins.knowledge.engine import KnowledgeEngine
from tinysoul.plugins.knowledge.retrieval import knowledge_search_corpus


@pytest.fixture()
def store(tmp_path: Path) -> KnowledgeEngine:
    vault = tmp_path / "vault"
    (vault / "ml").mkdir(parents=True)
    (vault / "ml" / "transformer.md").write_text(
        "---\ntitle: Transformer\ntags: [ml, attention]\n---\n"
        "The transformer architecture uses self-attention.\n"
        "See [[KV cache]] for inference speedups.\n",
        "utf-8",
    )
    (vault / "ml" / "KV cache.md").write_text(
        "---\ntags: [inference]\n---\nKV cache stores per-layer keys and values.\n",
        "utf-8",
    )
    (vault / "daily.md").write_text("Plain note about retrieval quality.\n", "utf-8")
    engine = KnowledgeEngine(settings=KnowledgeSettings(root=tmp_path / "knowledge"))
    report = engine.ingest_obsidian(vault)
    assert not report.failures
    return engine


def test_query_source_returns_candidates_for_pipeline_ranking(
    store: KnowledgeEngine,
) -> None:
    # The corpus returns every candidate; the kernel pipeline ranks.
    request = RetrievalRequest(
        source=QuerySource(scope="all", query=TextQuery("self-attention"))
    )
    corpus = knowledge_search_corpus(store, request, references=ReferenceResolver())
    assert corpus.query == "self-attention"
    assert len(corpus.candidates) == 3
    transformer = next(
        item
        for item in corpus.candidates
        if item.ref == f"km:{store.index.get('ml/transformer.md').km_id}"
    )
    assert transformer.title == "Transformer"
    assert transformer.attributes["tag"] == ["ml", "attention"]


def test_directory_source_enumerates_all(store: KnowledgeEngine) -> None:
    corpus = knowledge_search_corpus(
        store, RetrievalRequest(source=DirectorySource(scope="all")),
        references=ReferenceResolver(),
    )
    assert len(corpus.candidates) == 3
    assert corpus.scanned == 3


def test_where_filter_by_tag(store: KnowledgeEngine) -> None:
    corpus = knowledge_search_corpus(
        store,
        RetrievalRequest(source=DirectorySource(scope="all", where={"tag": "inference"})),
        references=ReferenceResolver(),
    )
    assert len(corpus.candidates) == 1
    assert corpus.candidates[0].title == "KV cache"


def test_backlinks_use_real_km_links_edges_only(store: KnowledgeEngine) -> None:
    # transformer.md links to KV cache -> backlinks of kv-cache == transformer
    kv_id = store.index.get("ml/KV cache.md").km_id
    request = RetrievalRequest(
        source=BacklinksSource(scope="all", anchor_ref=f"km:{kv_id}")
    )
    corpus = knowledge_search_corpus(store, request, references=ReferenceResolver())
    assert [item.ref for item in corpus.candidates] == [
        f"km:{store.index.get('ml/transformer.md').km_id}"
    ]
    # daily.md has no links -> no backlinks
    daily_id = store.index.get("daily.md").km_id
    empty = knowledge_search_corpus(
        store,
        RetrievalRequest(source=BacklinksSource(scope="all", anchor_ref=f"km:{daily_id}")),
        references=ReferenceResolver(),
    )
    assert empty.candidates == ()


def test_refs_source_returns_exact_documents_with_fragments(
    store: KnowledgeEngine,
) -> None:
    transformer_id = store.index.get("ml/transformer.md").km_id
    stored = store.store.read_note("ml/transformer.md")
    line = next(
        number
        for number, text in enumerate(stored.splitlines(), 1)
        if "KV cache" in text
    )
    request = RetrievalRequest(
        source=RefsSource(refs=(f"km:{transformer_id}#L{line}",))
    )
    corpus = knowledge_search_corpus(store, request, references=ReferenceResolver())
    assert len(corpus.candidates) == 1
    text = "".join(unit.text for unit in corpus.candidates[0].content_units)
    assert "KV cache" in text
    assert "self-attention" not in text


def test_unknown_ref_is_a_reference_error(store: KnowledgeEngine) -> None:
    request = RetrievalRequest(source=RefsSource(refs=("km:does-not-exist",)))
    with pytest.raises(Exception, match="does not resolve"):
        knowledge_search_corpus(store, request, references=ReferenceResolver())


def test_document_query_resolves_to_document_text(store: KnowledgeEngine) -> None:
    kv_id = store.index.get("ml/KV cache.md").km_id
    request = RetrievalRequest(
        source=QuerySource(
            scope="all", query=DocumentQuery(document_ref=f"km:{kv_id}")
        )
    )
    corpus = knowledge_search_corpus(store, request, references=ReferenceResolver())
    assert "KV cache stores per-layer keys" in corpus.query
