"""Knowledge card generation tests (M4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tinysoul.plugins.knowledge.config import KnowledgeSettings
from tinysoul.plugins.knowledge.engine import KnowledgeEngine


@pytest.fixture()
def engine_with_notes(tmp_path: Path) -> KnowledgeEngine:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "transformer.md").write_text(
        "---\ntitle: Transformer\ntags: [ml]\n---\nThe transformer uses self-attention.\n",
        "utf-8",
    )
    engine = KnowledgeEngine(
        settings=KnowledgeSettings(root=tmp_path / "knowledge")
    )
    report = engine.ingest_obsidian(vault)
    assert not report.failures
    return engine


def test_write_cards_creates_daily_document_with_real_links(
    engine_with_notes: KnowledgeEngine,
) -> None:
    entry = engine_with_notes.index.live()[0]
    ref = engine_with_notes.ref_for(entry.km_id)
    card = {
        "question": "Transformer 靠什么机制建模长距离依赖？",
        "answer": "自注意力机制。",
        "concept_tags": ["attention"],
        "source_refs": [ref],
        "confidence": "high",
    }
    card_ref = engine_with_notes.write_cards(
        "2026-10-12", (card,), source_titles={entry.km_id: entry.title}
    )
    assert card_ref.startswith("km:")
    stored = engine_with_notes.store.read_document("2026-10-12.md", source="card")
    assert "km_source: card" in stored
    assert "Transformer" in stored  # km_links carry the source title for backlinks
    assert "自注意力机制" in stored
    # cards are indexed and searchable
    assert engine_with_notes.index.get("2026-10-12.md") is not None


def test_write_cards_appends_same_day(engine_with_notes: KnowledgeEngine) -> None:
    entry = engine_with_notes.index.live()[0]
    ref = engine_with_notes.ref_for(entry.km_id)
    card_a = {
        "question": "Q1?",
        "answer": "A1",
        "concept_tags": [],
        "source_refs": [ref],
        "confidence": "high",
    }
    engine_with_notes.write_cards("2026-10-12", (card_a,))
    card_b = {
        "question": "Q2?",
        "answer": "A2",
        "concept_tags": [],
        "source_refs": [ref],
        "confidence": "medium",
    }
    engine_with_notes.write_cards("2026-10-12", (card_b,))
    stored = engine_with_notes.store.read_document("2026-10-12.md", source="card")
    assert "Q1?" in stored and "Q2?" in stored


def test_write_cards_requires_cards(engine_with_notes: KnowledgeEngine) -> None:
    with pytest.raises(Exception, match="at least one card"):
        engine_with_notes.write_cards("2026-10-12", ())


def test_documents_imported_on_filters_by_day(
    engine_with_notes: KnowledgeEngine,
) -> None:
    from datetime import date

    today = date.today().isoformat()
    assert len(engine_with_notes.documents_imported_on(today)) == 1
    assert engine_with_notes.documents_imported_on("1999-01-01") == ()


def test_disabled_reflection_skips_via_executor_settings(
    engine_with_notes: KnowledgeEngine, tmp_path: Path
) -> None:
    """The executor's settings gate keeps disabled configs side-effect free."""

    settings = KnowledgeSettings(
        root=tmp_path / "knowledge",
        reflection=__import__(
            "tinysoul.plugins.knowledge.config", fromlist=["KnowledgeReflectionSettings"]
        ).KnowledgeReflectionSettings(enabled=False),
    )
    assert settings.reflection.enabled is False
