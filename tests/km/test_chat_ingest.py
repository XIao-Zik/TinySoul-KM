"""Chat export adapter and ingestion tests (M3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tinysoul.plugins.knowledge.config import KnowledgeSettings
from tinysoul.plugins.knowledge.engine import KnowledgeEngine
from tinysoul.plugins.knowledge.ingest.chat_export import (
    chat_slug,
    parse_chat_file,
    render_chat_markdown,
    split_session,
)


def _json_export(path: Path, conversations) -> Path:
    path.write_text(json.dumps(conversations, ensure_ascii=False), "utf-8")
    return path


def test_json_export_parses_sessions_and_turns(tmp_path: Path) -> None:
    source = _json_export(
        tmp_path / "deepseek.json",
        [
            {
                "title": "混合检索讨论",
                "date": "2026-10-02 21:04",
                "url": "https://chat.deepseek.com/share/abc",
                "messages": [
                    {"role": "user", "content": "什么是混合检索？"},
                    {"role": "assistant", "content": "混合检索结合 BM25 与向量召回。"},
                    {"role": "system", "content": "ignored"},
                    {"role": "user", "content": ""},
                ],
            },
            {"title": "空会话", "messages": []},
        ],
    )
    parsed = parse_chat_file(source, platform="deepseek")
    assert len(parsed.sessions) == 1
    session = parsed.sessions[0]
    assert session.title == "混合检索讨论"
    assert session.day.isoformat() == "2026-10-02"
    assert session.url == "https://chat.deepseek.com/share/abc"
    assert [(t.role, t.text) for t in session.turns] == [
        ("user", "什么是混合检索？"),
        ("assistant", "混合检索结合 BM25 与向量召回。"),
    ]
    assert any("no usable turns" in w for w in parsed.warnings)


def test_markdown_export_splits_by_heading(tmp_path: Path) -> None:
    source = tmp_path / "export.md"
    source.write_text(
        "# 会话一\n\n用户: 问题A\n\n助手: 回答A\n\n# 会话二\n\n用户: 问题B\n\n助手: 回答B\n",
        "utf-8",
    )
    parsed = parse_chat_file(source, platform="deepseek")
    assert [s.title for s in parsed.sessions] == ["会话一", "会话二"]
    assert parsed.sessions[0].turns[0].text == "问题A"


def test_split_session_chunks_long_conversations() -> None:
    from tinysoul.plugins.knowledge.ingest.chat_export import ChatSession, ChatTurn

    turns = tuple(
        ChatTurn("user" if i % 2 == 0 else "assistant", f"t{i}") for i in range(45)
    )
    session = ChatSession(title="long", turns=turns, platform="deepseek")
    chunks = split_session(session)
    assert len(chunks) == 3
    assert sum(len(c.turns) for c in chunks) == 45
    assert chunks[0].title == "long (part 1)"


def test_chat_slug_keeps_cjk_and_collapses_noise() -> None:
    assert chat_slug("混合检索 讨论?") == "混合检索-讨论"
    assert chat_slug("///") == "chat"


def test_ingest_chat_writes_store_and_index(tmp_path: Path) -> None:
    source = _json_export(
        tmp_path / "chats.json",
        [
            {
                "title": "检索问答",
                "date": "2026-10-05",
                "messages": [
                    {"role": "user", "content": "RRF 融合是怎么算的？"},
                    {"role": "assistant", "content": "按倒数排名融合两路结果。"},
                ],
            }
        ],
    )
    engine = KnowledgeEngine(settings=KnowledgeSettings(root=tmp_path / "knowledge"))
    report = engine.ingest_chat(source, platform="deepseek")
    assert report.added and not report.failures
    relative = report.added[0]
    assert relative.startswith("2026-10/deepseek/")
    stored = engine.store.read_document(relative, source="chat")
    assert "km_source: chat" in stored
    assert "km_platform: deepseek" in stored
    assert "## 问题" in stored and "## 回答" in stored
    # repeat import is a no-op
    again = engine.ingest_chat(source, platform="deepseek")
    assert again.added == () and again.unchanged == 1
    # dry run reports nothing new
    dry = engine.ingest_chat(source, platform="deepseek", dry_run=True)
    assert dry.added == () and dry.dry_run
    # chat entries are searchable through the corpus
    from tinysoul.kernel.retrieval.contracts import (
        QuerySource,
        RetrievalRequest,
        TextQuery,
    )
    from tinysoul.plugins.knowledge.retrieval import knowledge_search_corpus
    from tinysoul.infra.references import ReferenceResolver

    corpus = knowledge_search_corpus(
        engine,
        RetrievalRequest(source=QuerySource(scope="all", query=TextQuery("RRF 融合"))),
        references=ReferenceResolver(),
    )
    assert corpus.candidates, "chat content must be searchable"
    assert corpus.candidates[0].attributes["source"] == "chat"


def test_ingest_chat_missing_file_is_contract_error(tmp_path: Path) -> None:
    engine = KnowledgeEngine(settings=KnowledgeSettings(root=tmp_path / "knowledge"))
    with pytest.raises(Exception, match="does not exist"):
        engine.ingest_chat(tmp_path / "nowhere.json")
