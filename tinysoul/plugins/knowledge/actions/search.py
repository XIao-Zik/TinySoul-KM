"""km.search executor: kernel retrieval pipeline over the knowledge corpus."""

from __future__ import annotations

from tinysoul.infra.json import to_json_object
from tinysoul.kernel.action import (
    ActionEngineBuilder,
    ActionExecution,
    ActionExecutionContext,
    ActionExecutor,
    ActionFailureDisposition,
    ActionResult,
    ActionResultStage,
    ActionLocalFailure,
    ActionTraceProjection,
)
from tinysoul.kernel.action.tasks import ActionTaskFactory
from tinysoul.kernel.retrieval.contracts import (
    ModelStep,
    SearchContext,
    SearchFailure,
)
from tinysoul.kernel.retrieval.operations import SelectionInput
from tinysoul.kernel.retrieval.requests import parse_retrieval_request

from ..failures import KnowledgeContractError
from ..runtime_bridge import RuntimeKnowledgeBridge
from ..services import KnowledgeReadService


def register_knowledge_actions(
    builder: ActionEngineBuilder,
    *,
    knowledge: KnowledgeReadService,
    runtime_bridge: RuntimeKnowledgeBridge,
    tasks: ActionTaskFactory | None = None,
) -> ActionEngineBuilder:
    builder.register_executor(
        "km.search", KnowledgeSearchExecutor(knowledge, runtime_bridge, tasks)
    )
    return builder


class KnowledgeSearchExecutor(ActionExecutor):
    def __init__(
        self,
        knowledge: KnowledgeReadService,
        runtime_bridge: RuntimeKnowledgeBridge,
        tasks: ActionTaskFactory | None = None,
    ) -> None:
        self._knowledge, self._runtime_bridge, self._tasks = (
            knowledge,
            runtime_bridge,
            tasks,
        )

    async def execute(
        self, execution: ActionExecution, context: ActionExecutionContext
    ) -> ActionResult:
        knowledge = self._knowledge.using(context.owner_operations)
        try:
            request = parse_retrieval_request(
                execution.call.params, knowledge.retrieval_policies[0]
            )
            inputs = SelectionInput()
            if not isinstance(request, str) and self._tasks is not None:
                use_context = any(
                    isinstance(step, ModelStep)
                    and step.context is SearchContext.CURRENT
                    for step in request.steps
                )
                inputs = await self._tasks.selection_input(
                    execution,
                    include_context=use_context,
                    control=context.control,
                )
            result = await knowledge.search(request, inputs=inputs)
        except SearchFailure as exc:
            return _failed(execution, str(exc), exc.kind.value)
        except KnowledgeContractError as exc:
            return _failed(execution, str(exc), "invalid_search")
        except Exception as exc:
            raise self._runtime_bridge.from_knowledge_error(exc) from exc
        return _success(
            execution,
            result.to_json(),
            trace_projection=ActionTraceProjection(
                origin_refs=tuple(item.ref for item in result.items),
                canonical_payload=result.recollection(),
            ),
        )


def _success(
    execution: ActionExecution,
    payload,
    *,
    trace_projection: ActionTraceProjection | None = None,
) -> ActionResult:
    return ActionResult.success(
        call_id=execution.call.call_id,
        invoke_id=execution.framework.invoke_id,
        batch_id=execution.framework.batch_id,
        action_name=execution.call.action_name,
        sequence=execution.call.sequence,
        domain=execution.framework.domain,
        payload=to_json_object(payload),
        trace_projection=trace_projection,
    )


def _failed(execution: ActionExecution, feedback: str, reason: str) -> ActionResult:
    return ActionResult.failed(
        call_id=execution.call.call_id,
        invoke_id=execution.framework.invoke_id,
        batch_id=execution.framework.batch_id,
        action_name=execution.call.action_name,
        stage=ActionResultStage.EXECUTE,
        sequence=execution.call.sequence,
        domain=execution.framework.domain,
        failure=ActionLocalFailure(
            reason=reason,
            scope="knowledge.action",
            disposition=ActionFailureDisposition.CHANGE_REQUEST,
            feedback=feedback,
        ),
    )
