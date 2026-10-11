"""Incremental ingestion tests: add/modify/delete(rename)/repeat and dry-run."""

from __future__ import annotations

from pathlib import Path

import pytest

from tinysoul.plugins.knowledge.config import KnowledgeSettings
from tinysoul.plugins.knowledge.engine import KnowledgeEngine


def _engine(root: Path) -> KnowledgeEngine:
    return KnowledgeEngine(settings=KnowledgeSettings(root=root / "knowledge"))


def _vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "sub").mkdir(parents=True, exist_ok=True)
    return vault


def test_full_cycle_add_modify_delete_rename(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "a.md").write_text("---\ntitle: A\n---\nA body with [[b]] #tag1\n", "utf-8")
    (vault / "sub" / "b.md").write_text("B body\n", "utf-8")
    engine = _engine(tmp_path)

    first = engine.ingest_obsidian(vault)
    assert sorted(first.added) == ["a.md", "sub/b.md"]
    assert first.tombstoned == () and not first.failures
    index = engine.index
    a_id = index.get("a.md").km_id
    assert index.get("a.md").links == ("b",)
    assert index.get("a.md").tags == ("tag1",)

    # repeat import with no change: nothing happens
    second = engine.ingest_obsidian(vault)
    assert second.added == () and second.updated == () and second.tombstoned == ()
    assert second.unchanged == 2

    # modify a.md
    (vault / "a.md").write_text("---\ntitle: A2\n---\nnew body\n", "utf-8")
    third = engine.ingest_obsidian(vault)
    assert third.updated == ("a.md",)
    assert engine.index.get("a.md").km_id == a_id  # stable identity per path
    assert engine.index.get("a.md").links == ()

    # delete sub/b.md -> tombstone, store file kept
    (vault / "sub" / "b.md").unlink()
    fourth = engine.ingest_obsidian(vault)
    assert fourth.tombstoned == ("sub/b.md",)
    assert engine.index.get("sub/b.md").tombstoned is True
    store_note = engine.store.root / "notes" / "sub" / "b.md"
    assert store_note.is_file(), "tombstone must not hard-delete the store file"
    tombstones = (engine.store.root / "tombstones.jsonl").read_text("utf-8")
    assert "vanished" in tombstones and "sub/b.md" in tombstones

    # rename: new file with the same content revives the old identity
    (vault / "renamed.md").write_text("B body\n", "utf-8")
    fifth = engine.ingest_obsidian(vault)
    assert fifth.added == ("renamed.md",)
    entry = engine.index.get("renamed.md")
    # identity merge via checksum revival: same km_id as the tombstoned note
    assert entry.tombstoned is False
    assert entry.km_id == engine.index.get("sub/b.md").km_id


def test_tombstoned_note_revives_on_restore(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "a.md").write_text("A\n", "utf-8")
    engine = _engine(tmp_path)
    engine.ingest_obsidian(vault)
    (vault / "a.md").unlink()
    engine.ingest_obsidian(vault)
    assert engine.index.get("a.md").tombstoned is True

    (vault / "a.md").write_text("A\n", "utf-8")
    report = engine.ingest_obsidian(vault)
    assert report.tombstoned == ()
    assert engine.index.get("a.md").tombstoned is False


def test_dry_run_matches_actual_execution(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "a.md").write_text("one\n", "utf-8")
    (vault / "b.md").write_text("two\n", "utf-8")
    engine = _engine(tmp_path)
    engine.ingest_obsidian(vault)
    (vault / "c.md").write_text("three\n", "utf-8")
    (vault / "a.md").write_text("one changed\n", "utf-8")
    (vault / "b.md").unlink()

    dry = engine.ingest_obsidian(vault, dry_run=True)
    assert dry.dry_run is True
    assert dry.added == ("c.md",)
    assert dry.updated == ("a.md",)
    assert dry.tombstoned == ("b.md",)
    # dry run wrote nothing
    assert engine.index.get("c.md") is None
    assert engine.index.get("b.md").tombstoned is False

    real = engine.ingest_obsidian(vault)
    assert (real.added, real.updated, real.tombstoned) == (
        dry.added,
        dry.updated,
        dry.tombstoned,
    )
    assert engine.index.get("c.md") is not None


def test_full_rescan_rehashes_everything(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (vault / "a.md").write_text("A\n", "utf-8")
    engine = _engine(tmp_path)
    engine.ingest_obsidian(vault)
    # tamper with the index mtime so a stale mtime would otherwise hide a change
    entry = engine.index.get("a.md")
    from tinysoul.plugins.knowledge.storage.index import KnowledgeIndexEntry
    from dataclasses import replace

    engine.index.put(replace(entry, mtime=entry.mtime + 5.0))
    (vault / "a.md").write_text("A2\n", "utf-8")
    report = engine.ingest_obsidian(vault, full=True)
    assert report.updated == ("a.md",)


def test_missing_vault_is_a_contract_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with pytest.raises(Exception, match="does not exist"):
        engine.ingest_obsidian(tmp_path / "nowhere")
