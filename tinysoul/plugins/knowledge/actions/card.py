"""km.generate_card executor: daily knowledge cards from a Reflection Turn."""

from __future__ import annotations

import json

from tinysoul.infra.json import to_json_object
from tinysoul.kernel.action import (
    ActionEngineBuilder,
    ActionExecution,
    ActionExecutionContext,
    ActionExecutor,
    ActionFailureDisposition,
    ActionLocalFailure,
    ActionResult,
    ActionResultStage,
    ActionTraceProjection,
)
from tinysoul.kernel.action.tasks import ActionTaskFactory, ActionTaskOutput, TaskPrompt
from tinysoul.llm.protocol.responses import AnswerFormat
from tinysoul.kernel.context.prompts import PromptBlock
from tinysoul.llm.protocol.messages import TextPart, UserMessage

from ..config import KnowledgeSettings
from ..engine import KnowledgeEngine
from ..runtime_bridge import RuntimeKnowledgeBridge
from ..services import KnowledgeReadService

MAX_DAILY_CANDIDATES = 12
CARD_SCHEMA_KEYS = {"question", "answer", "concept_tags", "source_refs", "confidence"}
ANNOTATION_KEYS = {"ref", "km_type", "km_topics", "km_summary"}
PROMPT_GUIDE = """You are generating daily knowledge cards for a personal knowledge base.
From the supplied candidate documents (imported or changed today), distill 1 to 5 cards.
Each card: {"question": "what problem does this concept solve?", "answer": "3-5 sentences with the key conclusion",
"concept_tags": ["..."], "source_refs": ["km:<id>", ...], "confidence": "high|medium|low"}.
Additionally output "annotations": one entry per candidate document you can confidently
classify: {"ref": "km:<id>", "km_type": "concept|procedure|fact|reference|note",
"km_topics": ["..."], "km_summary": "one-sentence summary of what the document is about"}.
Rules: answer in the source document's language; every source_ref and annotation ref MUST be
copied verbatim from the candidate refs listed in the input; never invent a ref; low-confidence
cards are better omitted; omit "annotations" entirely when nothing can be classified
confidently; return JSON {"cards": [...], "annotations": [...]} only."""


def register_knowledge_card_action(
    builder: ActionEngineBuilder,
    *,
    engine: KnowledgeEngine,
    settings: KnowledgeSettings,
    knowledge: KnowledgeReadService,
    runtime_bridge: RuntimeKnowledgeBridge,
    tasks: ActionTaskFactory | None = None,
    llm=None,
    clock=None,
    day_source=None,
) -> ActionEngineBuilder:
    builder.register_executor(
        "km.generate_card",
        KnowledgeCardExecutor(
            engine,
            settings,
            runtime_bridge,
            tasks,
            llm,
            clock,
            day_source=day_source,
        ),
    )
    return builder


class KnowledgeCardExecutor(ActionExecutor):
    """Stage two of the daily digest: generate and store knowledge cards.

    Runs inside the Memory Reflection Turn. Card ``source_refs`` are validated
    against the live store; a fabricated reference is a typed local failure,
    never a written card.
    """

    def __init__(
        self,
        engine: KnowledgeEngine,
        settings: KnowledgeSettings,
        runtime_bridge: RuntimeKnowledgeBridge,
        tasks: ActionTaskFactory | None,
        llm,
        clock,
        *,
        day_source=None,
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._runtime_bridge = runtime_bridge
        self._tasks = tasks
        self._llm = llm
        self._clock = clock
        # The reflection context binds its target day during turn preparation;
        # resolve it lazily at execute time (activation is too early).
        self._day_source = day_source

    async def execute(
        self, execution: ActionExecution, context: ActionExecutionContext
    ) -> ActionResult:
        return await self._execute(execution, context)

    async def _execute(
        self, execution: ActionExecution, context: ActionExecutionContext
    ) -> ActionResult:
        if not self._settings.reflection.enabled:
            payload = {"cards_written": 0, "skipped": "knowledge.reflection disabled"}
            return _success(
                execution,
                payload,
                trace=ActionTraceProjection(
                    origin_refs=(), canonical_payload=payload
                ),
            )
        if self._tasks is None or self._llm is None:
            return _failed(
                execution, "Card generation requires the LLM task factory", "unavailable"
            )
        # The reflection targets a specific business day: the 00:15 run on the
        # 13th digests documents imported on the 12th. The context binds its
        # target day during turn preparation; clock/local-today are fallbacks.
        day_text = None
        if self._day_source is not None:
            try:
                day_text = self._day_source.memory_target()[0].isoformat()
            except Exception:
                day_text = None
        if day_text is None:
            day = self._clock.today() if self._clock is not None else None
            day_text = day.value.isoformat() if day is not None else None
        if day_text is None:
            from datetime import datetime

            day_text = datetime.now().date().isoformat()
        try:
            # Workspace archive ingestion runs before candidate selection so
            # files archived at the day boundary become same-day candidates
            # (idempotent fallback, decoupled from archive timing); expired
            # already-ingested archives are pruned right after (D-2).
            workspace_report = self._engine.ingest_workspace_archive()
            self._engine.cleanup_expired_archives()
            candidates = self._engine.documents_imported_on(day_text)
            if not candidates:
                payload = {
                    "cards_written": 0,
                    "day": day_text,
                    "skipped": "no new documents",
                    "workspace_ingest": workspace_report.summary(),
                }
                # The catalog declares a foldable result: every success must
                # carry a trace projection.
                return _success(
                    execution,
                    payload,
                    trace=ActionTraceProjection(
                        origin_refs=(), canonical_payload=payload
                    ),
                )
            candidates = candidates[:MAX_DAILY_CANDIDATES]
            listings = []
            titles: dict[str, str] = {}
            for entry in candidates:
                ref = self._engine.ref_for(entry.km_id)
                titles[entry.km_id] = entry.title or entry.path
                excerpt = self._engine.document_excerpt(entry)
                listings.append(f"- {ref} ({entry.source}) {entry.title}\n{excerpt}")
            prompt = TaskPrompt(
                guide_blocks=(
                    PromptBlock(
                        label="km.card.guide",
                        message=UserMessage.from_parts(TextPart(PROMPT_GUIDE)),
                    ),
                ),
                input_blocks=(
                    PromptBlock(
                        label="km.card.candidates",
                        message=UserMessage.from_parts(
                            TextPart(
                                f"Day: {day_text}\nCandidates:\n" + "\n\n".join(listings)
                            )
                        ),
                    ),
                ),
            )
            result = await self._llm.run(
                await self._tasks.create(
                    execution=execution,
                    prompt=prompt,
                    control=context.control,
                    consumer="km.generate_card.generate",
                    answer_format=AnswerFormat.JSON_OBJECT,
                )
            )
            value = ActionTaskOutput.json(
                result, execution, subject="Knowledge card LLM task"
            )
            if isinstance(value, ActionResult):
                return value
            raw_cards = value.get("cards") if isinstance(value, dict) else None
            if not isinstance(raw_cards, list) or not raw_cards:
                return _success(
                    execution,
                    {"cards_written": 0, "day": day_text, "skipped": "model produced no cards"},
                )
            live_ids = {
                entry.km_id for entry in self._engine.index.live()
            }
            validated: list[dict[str, object]] = []
            for raw in raw_cards[: self._settings.reflection.daily_card_limit]:
                if not isinstance(raw, dict) or not CARD_SCHEMA_KEYS.issuperset(raw):
                    return _failed(
                        execution,
                        f"Card schema violation: unexpected keys in {sorted(raw) if isinstance(raw, dict) else raw}",
                        "invalid_card_schema",
                    )
                refs = raw.get("source_refs")
                if not isinstance(refs, list) or not refs or any(
                    not isinstance(item, str) or not item for item in refs
                ):
                    return _failed(
                        execution, "Every card requires non-empty source_refs", "invalid_card_refs"
                    )
                for ref in refs:
                    km_id = ref.partition(":")[2]
                    if not ref.startswith("km:") or km_id not in live_ids:
                        # Fabricated references are rejected, never written.
                        return _failed(
                            execution,
                            f"Card source_ref does not resolve to a live document: {ref}",
                            "fabricated_source_ref",
                        )
                validated.append(raw)
            if not validated:
                payload = {
                    "cards_written": 0,
                    "day": day_text,
                    "skipped": "no valid cards",
                }
                return _success(
                    execution,
                    payload,
                    trace=ActionTraceProjection(
                        origin_refs=(), canonical_payload=payload
                    ),
                )
            write_report = self._engine.write_cards(
                day_text, tuple(validated), source_titles=titles
            )
            annotated = self._apply_annotations(value, live_ids)
            payload = {
                "cards_written": write_report.written,
                "duplicates_skipped": write_report.duplicates,
                "day": day_text,
                "card_ref": write_report.ref,
                "annotated": annotated,
                "workspace_ingest": workspace_report.summary(),
            }
            return _success(
                execution,
                payload,
                trace=ActionTraceProjection(
                    origin_refs=(write_report.ref,), canonical_payload=payload
                ),
            )
        except Exception as exc:
            import traceback

            # Surface the fault as a model-visible local failure: an internal
            # failure hides the traceback from the operator and the model.
            detail = "".join(traceback.format_exception(exc))[-3500:]
            feedback = f"{type(exc).__name__}: {exc}\n{detail}"
            return _failed(execution, feedback, "internal_error")

    def _apply_annotations(self, value: object, live_ids: set[str]) -> int:
        """D-1 write-back: per-document km_type/km_topics/km_summary.

        Best effort by design — an invalid or failing annotation is skipped,
        never fails the turn; unannotated documents may be picked up again by
        a later reflection.
        """

        if not isinstance(value, dict):
            return 0
        raw_annotations = value.get("annotations")
        if not isinstance(raw_annotations, list):
            return 0
        annotated = 0
        for raw in raw_annotations:
            if not isinstance(raw, dict) or not ANNOTATION_KEYS.issuperset(raw):
                continue
            ref = raw.get("ref")
            if not isinstance(ref, str) or not ref.startswith("km:"):
                continue
            km_id = ref.partition(":")[2]
            if km_id not in live_ids:
                continue
            km_type = raw.get("km_type")
            topics = raw.get("km_topics")
            summary = raw.get("km_summary")
            if (
                not isinstance(km_type, str)
                or not km_type.strip()
                or not isinstance(summary, str)
                or not summary.strip()
                or not isinstance(topics, list)
                or any(
                    not isinstance(topic, str) or not topic.strip()
                    for topic in topics
                )
            ):
                continue
            if self._engine.annotate_document(
                km_id,
                km_type=km_type.strip(),
                km_topics=tuple(topic.strip() for topic in topics),
                km_summary=summary.strip(),
            ):
                annotated += 1
        return annotated


def _success(
    execution: ActionExecution,
    payload,
    *,
    trace: ActionTraceProjection | None = None,
) -> ActionResult:
    return ActionResult.success(
        call_id=execution.call.call_id,
        invoke_id=execution.framework.invoke_id,
        batch_id=execution.framework.batch_id,
        action_name=execution.call.action_name,
        sequence=execution.call.sequence,
        domain=execution.framework.domain,
        payload=to_json_object(payload),
        trace_projection=trace,
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
            scope="knowledge.card",
            disposition=ActionFailureDisposition.CHANGE_REQUEST,
            feedback=feedback,
        ),
    )
