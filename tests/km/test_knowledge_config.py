"""Knowledge plugin registration and project-side configuration tests."""

from __future__ import annotations

import pytest

from tinysoul.plugins.knowledge.config import (
    KnowledgeSettings,
    parse_knowledge_settings,
)
from tinysoul.plugins.knowledge.engine import KnowledgeEngine


def test_settings_defaults_and_root(tmp_path) -> None:
    settings = parse_knowledge_settings({}, project_root=tmp_path)
    assert settings.root == tmp_path / "knowledge"
    assert settings.reflection.enabled is False
    assert settings.search.embedding_use is None


def test_settings_reject_unknown_keys(tmp_path) -> None:
    from tinysoul.infra.config import ConfigError

    with pytest.raises(ConfigError):
        parse_knowledge_settings({"unknown": 1}, project_root=tmp_path)


def test_settings_relative_root_must_stay_inside_project(tmp_path) -> None:
    from tinysoul.infra.config import ConfigError

    with pytest.raises(ConfigError):
        parse_knowledge_settings({"root": "../outside"}, project_root=tmp_path)


def test_engine_creates_layout_on_demand(tmp_path) -> None:
    engine = KnowledgeEngine(settings=KnowledgeSettings(root=tmp_path / "knowledge"))
    assert engine.stats() == {
        "documents": 0,
        "live": 0,
        "tombstoned": 0,
    }
