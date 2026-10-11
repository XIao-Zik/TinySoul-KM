"""Knowledge-to-runtime semantic bridge."""

from __future__ import annotations

from dataclasses import dataclass

from tinysoul.infra.config import ConfigError
from tinysoul.infra.config.errors import config_error_payload
from tinysoul.infra.json import JsonObject
from tinysoul.runtime.control.exception import (
    RUNTIME_STARTUP_FAILED,
    RUNTIME_TURN_END,
    RuntimeException,
)
from tinysoul.runtime.failures import exception_payload, runtime_exception

from .failures import (
    KnowledgeContractError,
    KnowledgeFailureKind,
    KnowledgeIOError,
    KnowledgeInvariantError,
)

KNOWLEDGE_RUNTIME_REASON_MAP: dict[KnowledgeFailureKind, str] = {
    KnowledgeFailureKind.CONFIGURATION_FAILED: RUNTIME_STARTUP_FAILED,
    KnowledgeFailureKind.CONTRACT_VIOLATION: RUNTIME_TURN_END,
    KnowledgeFailureKind.IO_FAILED: RUNTIME_TURN_END,
    KnowledgeFailureKind.INTERNAL_FAILURE: RUNTIME_TURN_END,
}

KNOWLEDGE_FAILURE_MESSAGES: dict[KnowledgeFailureKind, str] = {
    KnowledgeFailureKind.CONFIGURATION_FAILED: "Knowledge configuration is invalid.",
    KnowledgeFailureKind.CONTRACT_VIOLATION: "Knowledge call violated its contract.",
    KnowledgeFailureKind.IO_FAILED: "Knowledge storage operation failed.",
    KnowledgeFailureKind.INTERNAL_FAILURE: "Knowledge operation failed internally.",
}


@dataclass(frozen=True)
class RuntimeKnowledgeBridge:
    def from_failure(
        self,
        kind: KnowledgeFailureKind,
        *,
        message: str,
        payload: JsonObject | None = None,
    ) -> RuntimeException:
        return runtime_exception(
            module="knowledge",
            kind=kind,
            reason=KNOWLEDGE_RUNTIME_REASON_MAP[kind],
            message=message,
            payload=payload,
        )

    def from_knowledge_error(
        self,
        error: Exception,
        *,
        payload: JsonObject | None = None,
    ) -> RuntimeException:
        kind = KnowledgeFailureKind.INTERNAL_FAILURE
        if isinstance(error, KnowledgeContractError):
            kind = KnowledgeFailureKind.CONTRACT_VIOLATION
        elif isinstance(error, KnowledgeIOError):
            kind = KnowledgeFailureKind.IO_FAILED
        elif isinstance(error, KnowledgeInvariantError):
            kind = KnowledgeFailureKind.INTERNAL_FAILURE
        return self.from_failure(
            kind,
            message=KNOWLEDGE_FAILURE_MESSAGES[kind],
            payload=exception_payload(error, payload),
        )

    def startup_failure(
        self,
        *,
        message: str,
        payload: JsonObject | None = None,
    ) -> RuntimeException:
        return self.from_failure(
            KnowledgeFailureKind.CONFIGURATION_FAILED,
            message=message,
            payload=payload,
        )

    def from_config_error(self, error: ConfigError) -> RuntimeException:
        return self.from_failure(
            KnowledgeFailureKind.CONFIGURATION_FAILED,
            message=KNOWLEDGE_FAILURE_MESSAGES[
                KnowledgeFailureKind.CONFIGURATION_FAILED
            ],
            payload=config_error_payload(error),
        )
