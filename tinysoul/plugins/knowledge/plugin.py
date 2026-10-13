"""Generation and profile assembly of the external knowledge owner plugin."""

from dataclasses import dataclass

from tinysoul.infra.concurrency import JoinedOperations
from tinysoul.infra.model_services import ModelServices
from tinysoul.infra.model_services.vectors import EmbeddingIndex
from tinysoul.infra.references import ReferenceResolver
from tinysoul.kernel.action.config import ActionSettings
from tinysoul.kernel.action.models import (
    ModelImplementation,
    ModelOperation,
    ModelUseDescriptor,
    ModelUseRegistry,
)
from tinysoul.kernel.retrieval.contracts import OperationKind, SourceKind
from tinysoul.kernel.retrieval.operations import SearchSession
from tinysoul.kernel.retrieval.policy import SearchCapability
from tinysoul.kernel.retrieval.selection import CandidateSelector
from tinysoul.kernel.registration import (
    GenerationBuildContext,
    PluginConfig,
    PluginGeneration,
    PluginProfileExtension,
    ProfileBuildContext,
    ProfileKind,
    Service,
)

from .actions import register_knowledge_actions
from .actions.card import register_knowledge_card_action
from .config import KnowledgeSettings, parse_knowledge_settings
from .engine import KNOWLEDGE_SEARCH_FILTERS, KnowledgeEngine
from .retrieval import knowledge_search_corpus
from .runtime_bridge import RuntimeKnowledgeBridge
from .services import KnowledgeReadService

KM_SEARCH_SOURCES = (
    SourceKind.QUERY,
    SourceKind.BACKLINKS,
    SourceKind.DIRECTORY,
    SourceKind.REFS,
    SourceKind.RESULT,
)
KM_SEARCH_OPERATIONS = (
    OperationKind.FILTER,
    OperationKind.SELECT,
    OperationKind.RERANK,
)


@dataclass(frozen=True)
class KnowledgePlugin:
    id = "knowledge"
    search_capabilities = (
        SearchCapability(
            "km.search",
            KM_SEARCH_SOURCES,
            KM_SEARCH_OPERATIONS,
            scopes=("all", "obsidian", "chat", "card"),
            filters=KNOWLEDGE_SEARCH_FILTERS,
            document_query=True,
        ),
    )
    model_uses = (
        ModelUseDescriptor(
            "km.search.select",
            "km.search",
            ModelOperation.SELECT,
            (ModelImplementation.LLM_TASK, ModelImplementation.STRUCTURED_DECISION),
        ),
        ModelUseDescriptor(
            "km.search.rerank",
            "km.search",
            ModelOperation.RERANK,
            (
                *(
                    ModelImplementation.LLM_TASK,
                    ModelImplementation.STRUCTURED_DECISION,
                ),
                ModelImplementation.EMBEDDING_SIMILARITY,
            ),
            "km",
        ),
        ModelUseDescriptor(
            "km.generate_card.generate",
            "km.generate_card",
            ModelOperation.GENERATE,
            (ModelImplementation.LLM_TASK,),
        ),
    )
    provides = (KnowledgeEngine,)
    requires = (ModelServices, ReferenceResolver)
    configuration = (
        PluginConfig(
            "knowledge",
            KnowledgeSettings,
            lambda tree, root: parse_knowledge_settings(tree, project_root=root),
            RuntimeKnowledgeBridge().from_config_error,
        ),
    )

    async def build_generation(
        self, context: GenerationBuildContext
    ) -> PluginGeneration:
        settings = context.settings.get(KnowledgeSettings)
        models = context.services.get(ModelServices)
        references = context.services.get(ReferenceResolver)
        use = settings.search.embedding_use
        if use is not None:
            models.embedding_sessions(use)
        embedding = (
            EmbeddingIndex(
                path=settings.root / ".tinysoul_knowledge" / "embeddings",
                services=models,
                use=use,
                max_chars=settings.search.embedding_cache_max_chars,
            )
            if use
            else None
        )
        engine = KnowledgeEngine(settings=settings, embedding=embedding)

        async def invoke(call):
            return await context.llm.invoke(call)

        selector = CandidateSelector(
            models=context.settings.get(ModelUseRegistry),
            invoke=invoke,
            services=models,
        )

        async def source(request):
            operations = JoinedOperations()
            result = await operations.run(
                lambda: knowledge_search_corpus(
                    engine, request, references=references
                )
            )
            operations.check_cancelled()
            return result

        def queries():
            return SearchSession(
                observations=context.observations,
                action_id="km.search",
                retrieval_policies=context.settings.get(
                    ActionSettings
                ).retrieval_policies,
                source=source,
                selector=selector,
                embedding=embedding,
                filters=KNOWLEDGE_SEARCH_FILTERS,
            )

        def extend(
            kind: ProfileKind, profile: ProfileBuildContext
        ) -> PluginProfileExtension:
            service = KnowledgeReadService(engine, queries=queries())

            def register(builder):
                register_knowledge_actions(
                    builder,
                    knowledge=service,
                    runtime_bridge=RuntimeKnowledgeBridge(),
                    tasks=profile.tasks,
                )
                if kind is ProfileKind.MEMORY_REFLECTION:
                    return register_knowledge_card_action(
                        builder,
                        engine=engine,
                        settings=settings,
                        knowledge=service,
                        runtime_bridge=RuntimeKnowledgeBridge(),
                        tasks=profile.tasks,
                        llm=profile.llm,
                        clock=context.clock,
                        day_source=_reflection_target_context(profile),
                    )
                return builder

            return PluginProfileExtension(
                "knowledge",
                services=(Service(KnowledgeReadService, service),),
                actions=register,
            )

        return PluginGeneration(
            self.id,
            services=(Service(KnowledgeEngine, engine),),
            profile_extension_factory=extend,
        )

def _reflection_target_context(profile: ProfileBuildContext):
    """The reflection context whose target day binds during turn preparation."""

    try:
        from tinysoul.plugins.memory.plugin import MemoryProfileSource

        return profile.bindings.get(MemoryProfileSource).target
    except Exception:
        return None
