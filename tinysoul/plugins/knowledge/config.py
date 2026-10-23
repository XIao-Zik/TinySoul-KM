"""Knowledge module configuration parsing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tinysoul.infra.config import ConfigError, reject_unknown_keys

_KNOWN_KEYS = frozenset({"root", "inspect", "search", "reflection", "archive"})


@dataclass(frozen=True)
class KnowledgeInspectSettings:
    page_max_chars: int = 8_000

    def __post_init__(self) -> None:
        _positive(self.page_max_chars, "knowledge.inspect.page_max_chars")


@dataclass(frozen=True)
class KnowledgeSearchSettings:
    embedding_use: str | None = None
    embedding_cache_max_chars: int = 16_000_000
    vector_weight: float = 0.6

    def __post_init__(self) -> None:
        _positive(
            self.embedding_cache_max_chars,
            "knowledge.search.embedding_cache_max_chars",
        )
        if isinstance(self.vector_weight, bool) or not 0.0 <= self.vector_weight <= 1.0:
            raise ConfigError(
                "Knowledge vector_weight must be between 0 and 1",
                key="knowledge.search.vector_weight",
            )


@dataclass(frozen=True)
class KnowledgeReflectionSettings:
    enabled: bool = False
    daily_card_limit: int = 5

    def __post_init__(self) -> None:
        _positive(self.daily_card_limit, "knowledge.reflection.daily_card_limit")


@dataclass(frozen=True)
class KnowledgeArchiveSettings:
    """Workspace archive ingestion: where daily archives live and when to prune."""

    archive_root: Path = Path("archive")
    retention_days: int = 30

    def __post_init__(self) -> None:
        if not isinstance(self.archive_root, Path):
            raise ConfigError(
                "Knowledge archive root must be a path",
                key="knowledge.archive.archive_root",
            )
        if (
            isinstance(self.retention_days, bool)
            or not isinstance(self.retention_days, int)
            or self.retention_days < 0
        ):
            raise ConfigError(
                "Knowledge archive retention_days must be zero or a positive integer "
                "(0 disables cleanup)",
                key="knowledge.archive.retention_days",
            )


@dataclass(frozen=True)
class KnowledgeSettings:
    root: Path
    inspect: KnowledgeInspectSettings = field(default_factory=KnowledgeInspectSettings)
    search: KnowledgeSearchSettings = field(default_factory=KnowledgeSearchSettings)
    reflection: KnowledgeReflectionSettings = field(
        default_factory=KnowledgeReflectionSettings
    )
    archive: KnowledgeArchiveSettings = field(
        default_factory=KnowledgeArchiveSettings
    )

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise ConfigError("Knowledge root must be a path", key="knowledge.root")
        if not isinstance(self.inspect, KnowledgeInspectSettings):
            raise ConfigError(
                "Knowledge inspect settings are invalid", key="knowledge.inspect"
            )
        if not isinstance(self.search, KnowledgeSearchSettings):
            raise ConfigError(
                "Knowledge search settings are invalid", key="knowledge.search"
            )
        if not isinstance(self.reflection, KnowledgeReflectionSettings):
            raise ConfigError(
                "Knowledge reflection settings are invalid", key="knowledge.reflection"
            )
        if not isinstance(self.archive, KnowledgeArchiveSettings):
            raise ConfigError(
                "Knowledge archive settings are invalid", key="knowledge.archive"
            )


def parse_knowledge_settings(
    tree: Mapping[str, object],
    *,
    project_root: Path,
) -> KnowledgeSettings:
    reject_unknown_keys(tree, _KNOWN_KEYS, key="knowledge")
    return KnowledgeSettings(
        root=_path(tree.get("root"), project_root=project_root),
        inspect=_parse_inspect(tree.get("inspect")),
        search=_parse_search(tree.get("search")),
        reflection=_parse_reflection(tree.get("reflection")),
        archive=_parse_archive(tree.get("archive"), project_root=project_root),
    )


def _parse_inspect(value: object) -> KnowledgeInspectSettings:
    tree = _table(value, "knowledge.inspect")
    reject_unknown_keys(tree, {"page_max_chars"}, key="knowledge.inspect")
    return KnowledgeInspectSettings(
        _int(tree, "page_max_chars", 8_000, "knowledge.inspect")
    )


def _parse_search(value: object) -> KnowledgeSearchSettings:
    tree = _table(value, "knowledge.search")
    reject_unknown_keys(
        tree,
        {"embedding_cache_max_chars", "embedding_use", "vector_weight"},
        key="knowledge.search",
    )
    defaults = KnowledgeSearchSettings()
    use = tree.get("embedding_use")
    if use is not None and (not isinstance(use, str) or not use.strip()):
        raise ConfigError(
            "Knowledge embedding_use must name a logical use",
            key="knowledge.search.embedding_use",
        )
    weight = tree.get("vector_weight", defaults.vector_weight)
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise ConfigError(
            "Knowledge vector_weight must be a number",
            key="knowledge.search.vector_weight",
        )
    return KnowledgeSearchSettings(
        embedding_use=use,
        embedding_cache_max_chars=_int(
            tree,
            "embedding_cache_max_chars",
            defaults.embedding_cache_max_chars,
            "knowledge.search",
        ),
        vector_weight=float(weight),
    )


def _parse_reflection(value: object) -> KnowledgeReflectionSettings:
    tree = _table(value, "knowledge.reflection")
    reject_unknown_keys(
        tree,
        {"enabled", "daily_card_limit"},
        key="knowledge.reflection",
    )
    enabled = tree.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError(
            "Knowledge reflection enabled must be a boolean",
            key="knowledge.reflection.enabled",
        )
    return KnowledgeReflectionSettings(
        enabled=enabled,
        daily_card_limit=_int(
            tree, "daily_card_limit", 5, "knowledge.reflection"
        ),
    )


def _parse_archive(
    value: object, *, project_root: Path
) -> KnowledgeArchiveSettings:
    tree = _table(value, "knowledge.archive")
    reject_unknown_keys(
        tree,
        {"archive_root", "retention_days"},
        key="knowledge.archive",
    )
    defaults = KnowledgeArchiveSettings()
    root_value = tree.get("archive_root", defaults.archive_root)
    if isinstance(root_value, Path):
        archive_root = root_value
    else:
        if not isinstance(root_value, str) or not root_value:
            raise ConfigError(
                "Knowledge archive root must be a non-empty path string",
                key="knowledge.archive.archive_root",
            )
        archive_root = Path(root_value)
        if not archive_root.is_absolute():
            archive_root = project_root / archive_root
    retention = tree.get("retention_days", defaults.retention_days)
    if (
        isinstance(retention, bool)
        or not isinstance(retention, int)
        or retention < 0
    ):
        raise ConfigError(
            "Knowledge archive retention_days must be zero or a positive integer "
            "(0 disables cleanup)",
            key="knowledge.archive.retention_days",
        )
    return KnowledgeArchiveSettings(
        archive_root=archive_root,
        retention_days=retention,
    )


def _table(value: object, key: str) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError("Knowledge configuration value must be a table", key=key)
    return cast(Mapping[str, object], value)


def _path(value: object, *, project_root: Path) -> Path:
    if value is None:
        return project_root / "knowledge"
    if not isinstance(value, str) or not value:
        raise ConfigError("Knowledge root must be non-empty text", key="knowledge.root")
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = (project_root / path).resolve()
    root = project_root.resolve()
    if candidate == root or root not in candidate.parents:
        raise ConfigError(
            "Relative Knowledge root must stay inside the project root",
            key="knowledge.root",
        )
    return candidate


def _int(tree: Mapping[str, object], name: str, default: int, prefix: str) -> int:
    value = tree.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            "Knowledge configuration value must be an integer",
            key=f"{prefix}.{name}",
        )
    return value


def _positive(value: object, key: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError("Knowledge setting must be positive", key=key)
