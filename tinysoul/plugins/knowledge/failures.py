"""Knowledge module errors and Runtime-facing failure kinds."""

from __future__ import annotations

from enum import StrEnum


class KnowledgeError(Exception):
    """Base class for Knowledge module errors."""


class KnowledgeContractError(KnowledgeError):
    """Raised when a caller violates a Knowledge contract."""


class KnowledgeInvariantError(KnowledgeError):
    """Raised when persisted knowledge state cannot satisfy module invariants."""


class KnowledgeIOError(KnowledgeError):
    """Raised when Knowledge filesystem operations fail."""


class KnowledgeFailureKind(StrEnum):
    """Stable Knowledge failure kinds that can cross into Runtime."""

    CONFIGURATION_FAILED = "knowledge.configuration_failed"
    CONTRACT_VIOLATION = "knowledge.contract_violation"
    IO_FAILED = "knowledge.io_failed"
    INTERNAL_FAILURE = "knowledge.internal_failure"
