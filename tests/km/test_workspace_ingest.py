"""Workspace archive ingestion (工作区归档收编): ingest, cleanup, annotation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from tinysoul.infra.config import ConfigError
from tinysoul.infra.references import ReferenceResolver
from tinysoul.kernel.retrieval.contracts import (
    QuerySource,
    RetrievalRequest,
    TextQuery,
)
from tinysoul.llm.protocol.responses import JsonAnswer
from tinysoul.plugins.knowledge.actions.card import KnowledgeCardExecutor
from tinysoul.plugins.knowledge.config import (
    KnowledgeArchiveSettings,
    KnowledgeReflectionSettings,
    KnowledgeSettings,
    parse_knowledge_settings,
)
from tinysoul.plugins.knowledge.engine import KnowledgeEngine
from tinysoul.plugins.knowledge.retrieval import knowledge_search_corpus


def _settings(tmp_path: Path, *, retention_days: int = 30) -> KnowledgeSettings:
    return KnowledgeSettings(
        root=tmp_path / "knowledge",
        archive=KnowledgeArchiveSettings(
            archive_root=tmp_path / "archive", retention_days=retention_days
        ),
    )


def _engine(tmp_path: Path, *, retention_days: int = 30) -> KnowledgeEngine:
    return KnowledgeEngine(settings=_settings(tmp_path, retention_days=retention_days))


def _archive(tmp_path: Path, name: str, relative: str, text: str) -> Path:
    workspace = tmp_path / "archive" / name / "workspace"
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    return path


def _expired_name(days: int) -> str:
    return f"{(date.today() - timedelta(days=days)).strftime('%Y%m%d')}T000000.000000+0800"


# -- ingestion --------------------------------------------------------------


def test_ingest_marks_archive_day_and_source(tmp_path: Path) -> None:
    _archive(
        tmp_path,
        "20261013T092229.435331+0800",
        "2026-09-07-如何让大模型为你所用.md",
        "---\ntitle: 如何让大模型为你所用\ntags: [ai, prompting]\n---\n提示词是杠杆。\n",
    )
    engine = _engine(tmp_path)

    report = engine.ingest_workspace_archive()
    assert report.added == ("2026-10-13/2026-09-07-如何让大模型为你所用.md",)
    assert not report.failures and not report.updated

    entry = engine.index.get("2026-10-13/2026-09-07-如何让大模型为你所用.md")
    assert entry is not None
    assert entry.source == "workspace"
    assert entry.imported_on == "2026-10-13"
    assert entry.tags == ("ai", "prompting")
    assert entry.title == "如何让大模型为你所用"

    stored = engine.store.read_document(entry.path, source="workspace")
    assert "km_source: workspace" in stored
    assert "提示词是杠杆" in stored
    assert (
        engine.store.workspace_root
        / "2026-10-13"
        / "2026-09-07-如何让大模型为你所用.md"
    ).is_file()


def test_ingest_prefers_transition_from_day_over_directory_name(tmp_path: Path) -> None:
    # Archive created 00:15 on the 13th holds the workspace of business day
    # 10-12: transition.json from_day wins over the directory timestamp.
    archive = tmp_path / "archive" / "20261013T001500.000000+0800"
    (archive / "workspace").mkdir(parents=True)
    (archive / "transition.json").write_text(
        '{"from_day": "2026-10-12", "to_day": "2026-10-13"}', "utf-8"
    )
    (archive / "workspace" / "dragged.md").write_text("---\ntitle: D\n---\nD\n", "utf-8")
    engine = _engine(tmp_path)

    report = engine.ingest_workspace_archive()
    assert report.added == ("2026-10-12/dragged.md",)
    assert engine.index.get("2026-10-12/dragged.md").imported_on == "2026-10-12"


def test_ingest_survives_corrupt_transition_json(tmp_path: Path) -> None:
    archive = tmp_path / "archive" / "20261013T001500.000000+0800"
    (archive / "workspace").mkdir(parents=True)
    (archive / "transition.json").write_text("not json{", "utf-8")
    (archive / "workspace" / "d.md").write_text("D\n", "utf-8")
    engine = _engine(tmp_path)

    report = engine.ingest_workspace_archive()
    # falls back to the directory name's leading date digits
    assert report.added == ("2026-10-13/d.md",)
    assert not report.failures


def test_ingest_mirrors_subdirectories_and_skips_non_markdown(tmp_path: Path) -> None:
    workspace = tmp_path / "archive" / "20261013T000000.000000+0800" / "workspace"
    (workspace / "docs").mkdir(parents=True)
    (workspace / "docs" / "deep.md").write_text("deep note\n", "utf-8")
    (workspace / "paper.pdf").write_bytes(b"%PDF-1.4 fake")
    (workspace / ".tinysoul").mkdir()
    (workspace / ".tinysoul" / "hidden.md").write_text("hidden\n", "utf-8")
    engine = _engine(tmp_path)

    report = engine.ingest_workspace_archive()
    assert report.added == ("2026-10-13/docs/deep.md",)
    assert engine.index.get("2026-10-13/paper.pdf") is None
    assert engine.index.get("2026-10-13/.tinysoul/hidden.md") is None


def test_reingest_is_idempotent(tmp_path: Path) -> None:
    _archive(tmp_path, "20261012T000347.429483+0800", "a.md", "---\ntitle: A\n---\nA\n")
    engine = _engine(tmp_path)
    first = engine.ingest_workspace_archive()
    stored_before = engine.store.read_document(first.added[0], source="workspace")
    version_before = engine.index.version

    second = engine.ingest_workspace_archive()
    assert second.added == () and second.updated == ()
    assert second.unchanged == 1 and not second.failures
    # 重复收编 0 写入：store 文本与索引版本都未动
    assert engine.store.read_document(first.added[0], source="workspace") == stored_before
    assert engine.index.version == version_before


def test_unparsable_archive_name_falls_back_to_today(tmp_path: Path) -> None:
    _archive(tmp_path, "manual-backup", "n.md", "N\n")
    engine = _engine(tmp_path)

    report = engine.ingest_workspace_archive()
    assert report.added == (f"{datetime.now().date().isoformat()}/n.md",)
    assert any("archive day is unparsable" in message for _, message in report.failures)


def test_changed_archive_file_is_reingested(tmp_path: Path) -> None:
    path = _archive(tmp_path, "20261012T000000.000000+0800", "a.md", "one\n")
    engine = _engine(tmp_path)
    engine.ingest_workspace_archive()
    path.write_text("one changed\n", "utf-8")

    report = engine.ingest_workspace_archive()
    assert report.updated == ("2026-10-12/a.md",)


# -- cleanup ----------------------------------------------------------------


def test_cleanup_deletes_only_ingested_expired_files(tmp_path: Path) -> None:
    workspace = tmp_path / "archive" / _expired_name(40) / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "a.md").write_text("---\ntitle: A\n---\ningested\n", "utf-8")
    engine = _engine(tmp_path)
    report = engine.ingest_workspace_archive()
    assert report.added == (f"{(date.today() - timedelta(days=40)).isoformat()}/a.md",)
    # A file dropped into the archive after ingestion was never ingested.
    (workspace / "late.md").write_text("never ingested\n", "utf-8")

    counts = engine.cleanup_expired_archives()
    assert counts == {"deleted": 1, "kept_uningested": 1}
    assert not (workspace / "a.md").exists()
    assert (workspace / "late.md").exists()
    # 知识库副本不随归档清理消失（过档即定稿）
    assert engine.index.get(
        f"{(date.today() - timedelta(days=40)).isoformat()}/a.md"
    ) is not None
    assert engine.store.read_document(
        f"{(date.today() - timedelta(days=40)).isoformat()}/a.md", source="workspace"
    )


def test_cleanup_keeps_recent_archives(tmp_path: Path) -> None:
    workspace = tmp_path / "archive" / _expired_name(5) / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "a.md").write_text("A\n", "utf-8")
    engine = _engine(tmp_path)
    engine.ingest_workspace_archive()

    counts = engine.cleanup_expired_archives()
    assert counts == {"deleted": 0, "kept_uningested": 0}
    assert (workspace / "a.md").exists()


def test_cleanup_disabled_with_zero_retention(tmp_path: Path) -> None:
    workspace = tmp_path / "archive" / _expired_name(400) / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "a.md").write_text("A\n", "utf-8")
    engine = _engine(tmp_path, retention_days=0)
    engine.ingest_workspace_archive()

    counts = engine.cleanup_expired_archives()
    assert counts == {"deleted": 0, "kept_uningested": 0, "disabled": 1}
    assert (workspace / "a.md").exists()


def test_cleanup_never_touches_session_or_memory_snapshots(tmp_path: Path) -> None:
    archive = tmp_path / "archive" / _expired_name(40)
    workspace = archive / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "a.md").write_text("A\n", "utf-8")
    session = archive / "session"
    session.mkdir()
    (session / "Memory.md").write_text("memory snapshot\n", "utf-8")
    memory = archive / "memory"
    memory.mkdir()
    (memory / "daily.md").write_text("daily snapshot\n", "utf-8")
    engine = _engine(tmp_path)
    engine.ingest_workspace_archive()

    counts = engine.cleanup_expired_archives()
    assert counts == {"deleted": 1, "kept_uningested": 0}
    assert (session / "Memory.md").is_file()
    assert (memory / "daily.md").is_file()
    # workspace/ 被回收，但 session/memory 仍在，归档目录本身保留
    assert archive.is_dir()
    assert not (archive / "workspace").exists()


# -- annotation write-back (D-1) ---------------------------------------------


def test_annotation_writeback_survives_reingest(tmp_path: Path) -> None:
    _archive(tmp_path, "20261013T000000.000000+0800", "a.md", "---\ntitle: A\n---\nA\n")
    engine = _engine(tmp_path)
    report = engine.ingest_workspace_archive()
    entry = engine.index.get(report.added[0])

    assert engine.annotate_document(
        entry.km_id,
        km_type="concept",
        km_topics=("rag", "prompting"),
        km_summary="一句话摘要",
    )

    stored = engine.store.read_document(report.added[0], source="workspace")
    frontmatter = yaml.safe_load(stored.split("---\n")[1])
    assert frontmatter["km_type"] == "concept"
    assert frontmatter["km_topics"] == ["rag", "prompting"]
    assert frontmatter["km_summary"] == "一句话摘要"

    # 重收编幂等：标注不会被归档收编覆盖丢失
    second = engine.ingest_workspace_archive()
    assert second.unchanged == 1 and not second.added
    stored_again = engine.store.read_document(report.added[0], source="workspace")
    assert "km_type: concept" in stored_again


def test_annotate_unknown_ref_returns_false(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    assert (
        engine.annotate_document(
            "k-missing", km_type="concept", km_topics=("t",), km_summary="s"
        )
        is False
    )


def test_workspace_documents_filter_by_source_in_search(tmp_path: Path) -> None:
    _archive(tmp_path, "20261013T000000.000000+0800", "a.md", "retrieval quality note\n")
    engine = _engine(tmp_path)
    report = engine.ingest_workspace_archive()
    assert report.added
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "b.md").write_text("another retrieval quality note\n", "utf-8")
    engine.ingest_obsidian(vault)

    corpus = knowledge_search_corpus(
        engine,
        RetrievalRequest(
            source=QuerySource(
                scope="all",
                query=TextQuery("retrieval quality"),
                where={"source": "workspace"},
            )
        ),
        references=ReferenceResolver(),
    )
    assert len(corpus.candidates) == 1
    assert corpus.candidates[0].attributes["source"] == "workspace"


# -- config -------------------------------------------------------------------


def test_parse_archive_defaults(tmp_path: Path) -> None:
    settings = parse_knowledge_settings({}, project_root=tmp_path)
    assert settings.archive.retention_days == 30
    assert settings.archive.archive_root == Path("archive")


def test_parse_archive_custom_values(tmp_path: Path) -> None:
    settings = parse_knowledge_settings(
        {"archive": {"archive_root": "arc", "retention_days": 0}},
        project_root=tmp_path,
    )
    assert settings.archive.archive_root == tmp_path / "arc"
    assert settings.archive.retention_days == 0


def test_parse_archive_rejects_invalid_values(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        parse_knowledge_settings({"archive": {"retention_days": -1}}, project_root=tmp_path)
    with pytest.raises(ConfigError):
        parse_knowledge_settings({"archive": {"retention_days": True}}, project_root=tmp_path)
    with pytest.raises(ConfigError):
        parse_knowledge_settings({"archive": {"unknown": 1}}, project_root=tmp_path)
    with pytest.raises(ConfigError):
        parse_knowledge_settings({"archive": {"archive_root": ""}}, project_root=tmp_path)


def test_default_archive_root_hangs_off_project_root(tmp_path: Path) -> None:
    engine = KnowledgeEngine(settings=KnowledgeSettings(root=tmp_path / "knowledge"))
    assert engine.archive_root == tmp_path / "archive"


# -- reflection executor wiring (T4) ------------------------------------------


@dataclass
class _FakeLLM:
    answers: list[Any]
    calls: list[Any] = field(default_factory=list)

    async def run(self, task_call):
        self.calls.append(task_call)
        answer = self.answers.pop(0)

        @dataclass
        class _Result:
            answer: Any
            status: str = "success"
            failure: Any = None

        return _Result(answer=JsonAnswer(value=answer))


class _FakeTasks:
    async def create(self, *, execution, prompt, control=None, consumer=None,
                     answer_format=None, **kwargs):
        assert consumer == "km.generate_card.generate"
        return object()


def _execute(executor):
    @dataclass
    class _Call:
        call_id: str = "c1"
        action_name: str = "km.generate_card"
        sequence: int = 1
        params: dict = field(default_factory=dict)

    @dataclass
    class _Framework:
        invoke_id: str = "i1"
        batch_id: str = "b1"
        domain: str = "km"

    @dataclass
    class _Execution:
        call: Any = field(default_factory=_Call)
        framework: Any = field(default_factory=_Framework)

    @dataclass
    class _Context:
        owner_operations: Any = None
        control: Any = None

    import asyncio

    return asyncio.run(executor.execute(_Execution(), _Context()))


def _valid_card(ref: str) -> dict[str, object]:
    return {
        "question": "这篇文档讲什么？",
        "answer": "检索质量笔记。",
        "concept_tags": ["retrieval"],
        "source_refs": [ref],
        "confidence": "high",
    }


def _workspace_engine(tmp_path: Path) -> tuple[KnowledgeEngine, str, str]:
    """Archive + engine with a pre-ingested workspace document.

    Returns (engine, stable km ref, store-relative path). The executor under
    test re-ingests idempotently and must still treat the file as a same-day
    candidate.
    """

    workspace = (
        tmp_path
        / "archive"
        / f"{datetime.now().date().strftime('%Y%m%d')}T120000.000000+0800"
        / "workspace"
    )
    workspace.mkdir(parents=True)
    (workspace / "dragged.md").write_text(
        "---\ntitle: 拖进来的文档\ntags: [rag]\n---\n关于检索质量的笔记。\n",
        "utf-8",
    )
    engine = KnowledgeEngine(
        settings=KnowledgeSettings(
            root=tmp_path / "knowledge",
            reflection=KnowledgeReflectionSettings(enabled=True),
            archive=KnowledgeArchiveSettings(
                archive_root=tmp_path / "archive", retention_days=30
            ),
        )
    )
    report = engine.ingest_workspace_archive()
    assert report.added
    entry = engine.index.get(report.added[0])
    return engine, engine.ref_for(entry.km_id), report.added[0]


def _executor(engine: KnowledgeEngine, answer: dict[str, Any]) -> KnowledgeCardExecutor:
    return KnowledgeCardExecutor(
        engine=engine,
        settings=engine.settings,
        runtime_bridge=None,
        tasks=_FakeTasks(),
        llm=_FakeLLM([answer]),
        clock=None,
    )


def test_reflection_ingests_workspace_and_annotates(tmp_path: Path) -> None:
    engine, ref, store_path = _workspace_engine(tmp_path)
    answer = {
        "cards": [_valid_card(ref)],
        "annotations": [
            {
                "ref": ref,
                "km_type": "concept",
                "km_topics": ["rag"],
                "km_summary": "检索质量笔记",
            }
        ],
    }
    result = _execute(_executor(engine, answer))
    assert result.payload["cards_written"] == 1
    assert result.payload["annotated"] == 1
    assert result.payload["workspace_ingest"].startswith("workspace import")
    stored = engine.store.read_document(store_path, source="workspace")
    assert "km_type: concept" in stored
    assert "km_summary" in stored


def test_reflection_skips_fabricated_annotations(tmp_path: Path) -> None:
    engine, ref, store_path = _workspace_engine(tmp_path)
    answer = {
        "cards": [_valid_card(ref)],
        "annotations": [
            {
                "ref": "km:does-not-exist",
                "km_type": "concept",
                "km_topics": ["rag"],
                "km_summary": "fabricated",
            }
        ],
    }
    result = _execute(_executor(engine, answer))
    assert result.payload["cards_written"] == 1
    assert result.payload["annotated"] == 0
    stored = engine.store.read_document(store_path, source="workspace")
    assert "km_type" not in stored


def test_reflection_works_without_annotations(tmp_path: Path) -> None:
    engine, ref, _path = _workspace_engine(tmp_path)
    result = _execute(_executor(engine, {"cards": [_valid_card(ref)]}))
    assert result.payload["cards_written"] == 1
    assert result.payload["annotated"] == 0
