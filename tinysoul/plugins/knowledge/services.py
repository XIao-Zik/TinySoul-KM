"""Knowledge capabilities selected by the consumer's execution scenario."""

from typing import Self

from tinysoul.infra.services import ScopedService, ServiceScope
from tinysoul.kernel.retrieval.contracts import (
    RetrievalRequest,
    SearchFailure,
    SearchFailureKind,
    SearchPage,
)
from tinysoul.kernel.retrieval.operations import SearchSession, SelectionInput

from .engine import KnowledgeEngine


class KnowledgeReadService(ScopedService[KnowledgeEngine]):
    """Knowledge discovery without persistence changes."""

    def __init__(
        self,
        owner: KnowledgeEngine,
        scope: ServiceScope = ServiceScope(),
        *,
        queries: SearchSession | None = None,
    ) -> None:
        super().__init__(owner, scope)
        self._queries = queries
        self.retrieval_policies = queries.retrieval_policies if queries else ()
        self.search = scope.remote(self._search)

    def _bind(self, scope: ServiceScope) -> Self:
        return type(self)(self._owner, scope, queries=self._queries)

    async def _search(
        self,
        request: RetrievalRequest | str,
        *,
        inputs: SelectionInput = SelectionInput(),
    ) -> SearchPage:
        if self._queries is None:
            raise SearchFailure(
                SearchFailureKind.INVALID_REQUEST,
                "Knowledge search has not been assembled for this service",
            )
        return await self._queries.search(request, inputs=inputs)
