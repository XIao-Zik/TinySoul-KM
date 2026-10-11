"""km.generate_card executor tests with a scripted LLM (no network)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from tinysoul.llm.protocol.responses import JsonAnswer
from tinysoul.plugins.knowledge.actions.card import KnowledgeCardExecutor
from tinysoul.plugins.knowledge.config import (
    KnowledgeReflectionSettings,
    KnowledgeSettings,
)
from tinysoul.plugins.knowledge.engine import KnowledgeEngine


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


def _make(tmp_path: Path, *, enabled: bool, answer):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    (vault / "transformer.md").write_text(
        "---\ntitle: Transformer\ntags: [ml]\n---\nSelf-attention content.\n",
        "utf-8",
    )
    engine = KnowledgeEngine(
        settings=KnowledgeSettings(
            root=tmp_path / "knowledge",
            reflection=KnowledgeReflectionSettings(enabled=enabled),
        )
    )
    report = engine.ingest_obsidian(vault)
    assert not report.failures
    llm = _FakeLLM([answer] if answer is not None else [])
    executor = KnowledgeCardExecutor(
        engine=engine,
        settings=engine.settings,
        runtime_bridge=None,
        tasks=_FakeTasks(),
        llm=llm,
        clock=None,
    )
    return engine, executor


def _valid_card(ref: str) -> dict[str, object]:
    return {
        "question": "Transformer 靠什么建模依赖？",
        "answer": "自注意力。",
        "concept_tags": ["attention"],
        "source_refs": [ref],
        "confidence": "high",
    }


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


def _utc_today() -> str:
    # local date: engine stamps imported_on with the local calendar day
    return datetime.now().date().isoformat()


def test_executor_writes_cards_with_valid_refs(tmp_path: Path) -> None:
    engine, executor = _make(
        tmp_path, enabled=True, answer={"cards": None}
    )
    entry = engine.index.live()[0]
    ref = engine.ref_for(entry.km_id)
    engine, executor = _make(
        tmp_path, enabled=True, answer={"cards": [_valid_card(ref)]}
    )
    result = _execute(executor)
    assert result.payload["cards_written"] == 1
    stored = engine.store.read_document(f"{_utc_today()}.md", source="card")
    assert "自注意力。" in stored
    assert engine.index.get(f"{_utc_today()}.md") is not None


def test_executor_rejects_fabricated_refs(tmp_path: Path) -> None:
    engine, executor = _make(
        tmp_path,
        enabled=True,
        answer={"cards": [_valid_card("km:does-not-exist")]},
    )
    result = _execute(executor)
    assert result.failure.reason == "fabricated_source_ref"


def test_executor_disabled_is_inert(tmp_path: Path) -> None:
    engine, executor = _make(tmp_path, enabled=False, answer=None)
    result = _execute(executor)
    assert result.payload["skipped"] == "knowledge.reflection disabled"
    assert result.payload["cards_written"] == 0


def test_executor_empty_cards_is_clean_skip(tmp_path: Path) -> None:
    engine, executor = _make(tmp_path, enabled=True, answer={"cards": []})
    result = _execute(executor)
    assert result.payload["cards_written"] == 0
    assert result.payload["skipped"] == "model produced no cards"


def test_executor_no_candidates_skips(tmp_path: Path) -> None:
    engine, executor = _make(tmp_path, enabled=True, answer={"cards": []})
    # pretend nothing was imported today
    from dataclasses import replace

    entries = engine.documents_imported_on(_utc_today())
    assert entries
    stale_day = "1999-01-01"
    for entry in entries:
        engine.index.put(replace(entry, imported_on=stale_day))
    result = _execute(executor)
    assert result.payload["skipped"] == "no new documents"


def test_executor_rejects_unknown_schema_keys(tmp_path: Path) -> None:
    engine, executor = _make(
        tmp_path,
        enabled=True,
        answer={"cards": [{"question": "q", "answer": "a", "source_refs": ["km:x"],
                            "concept_tags": [], "confidence": "high", "extra": 1}]},
    )
    result = _execute(executor)
    assert result.failure.reason == "invalid_card_schema"
