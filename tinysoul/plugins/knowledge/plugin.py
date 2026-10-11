"""Generation assembly of the external knowledge owner plugin."""

from dataclasses import dataclass

from tinysoul.kernel.registration import (
    GenerationBuildContext,
    PluginConfig,
    PluginGeneration,
    PluginProfileExtension,
    ProfileBuildContext,
    ProfileKind,
    Service,
)

from .config import KnowledgeSettings, parse_knowledge_settings
from .engine import KnowledgeEngine
from .runtime_bridge import RuntimeKnowledgeBridge


@dataclass(frozen=True)
class KnowledgePlugin:
    id = "knowledge"
    model_uses = ()
    search_capabilities = ()
    provides = (KnowledgeEngine,)
    requires = ()
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
        engine = KnowledgeEngine(settings=context.settings.get(KnowledgeSettings))

        def extend(
            kind: ProfileKind, profile: ProfileBuildContext
        ) -> PluginProfileExtension | None:
            return None

        return PluginGeneration(
            self.id,
            services=(Service(KnowledgeEngine, engine),),
            profile_extension_factory=extend,
        )
