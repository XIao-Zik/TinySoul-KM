import type { SettingsGroupDef, SettingsPageDef, SettingsPageId } from "./pages";

/**
 * Human-facing page/group labels as English sources; the render sites wrap
 * them with the global `t()` so the zh-CN dictionary localizes them
 * (protocol ids and configuration paths stay unchanged).
 */
const PAGE_LABELS: Record<SettingsPageId, { title: string; description: string }> = {
  overview: { title: "Configuration status", description: "Running values, pending activation, local changes." },
  plans: { title: "Run plans", description: "Named presets captured from configuration." },
  "llm-providers": { title: "LLM Providers", description: "Chat model endpoints, adapters and credential references." },
  "llm-models": { title: "LLM Models", description: "Model capabilities and ordered provider chains." },
  "llm-tasks": { title: "LLM Task Chains", description: "Ordered model chains and task parameters." },
  "dedicated-providers": { title: "Dedicated Providers", description: "Embedding and structured-evaluation endpoints." },
  "dedicated-models": { title: "Dedicated Models & Uses", description: "Embedding/JEV models and the logical uses bound to them." },
  credentials: { title: "Credentials", description: "Project dotenv values referenced by configuration." },
  "image-generation": { title: "Image Generation", description: "Reserved; the backend has no image configuration surface yet." },
  "phase-bindings": { title: "Phase Bindings", description: "The task chains Phase 1 and Phase 2 call." },
  actions: { title: "Actions & Model Uses", description: "Per-action visibility, runtime policy and model-use bindings." },
  "search-policies": { title: "Search Policies", description: "Retrieval sources, operations, context and page budgets." },
  budgets: { title: "Budgets", description: "Turn/reflection cycles and context/session budgets." },
  reflection: { title: "Reflection Schedule", description: "Daily reflection timing and archive location." },
  execution: { title: "Execution & Jobs", description: "Shell/script interpreters, limits and job capacity." },
  web: { title: "Web & Resource Fetching", description: "Web search/discovery/fetch providers and conversion limits." },
  acp: { title: "ACP Subagents", description: "Delegation targets, commands, environments and limits." },
  mcp: { title: "MCP Servers", description: "External tool servers, transports, env/header references." },
  workspace: { title: "Workspace", description: "Daily workspace root, read/write limits and watching." },
  session: { title: "Session", description: "Session root, background budget and inspect limits." },
  home: { title: "Home", description: "Home roots, read/write limits and the embedding use." },
  memory: { title: "Memory", description: "Active/persistent memory limits and the embedding use." },
  system: { title: "Endpoint & Sources", description: "Read-only process items, config sources and observation." },
  interface: { title: "Interface", description: "Theme, typography and density — local, applied immediately." },
};

const GROUP_LABELS: Record<SettingsGroupDef["id"], string> = {
  overview: "Overview & Plans",
  models: "Models & Services",
  behavior: "Behavior & Invocation",
  tools: "Tools & Connections",
  data: "Data & Knowledge",
  system: "System & Diagnostics",
  interface: "Interface",
};

export function settingsTitle(page: SettingsPageDef): string {
  return PAGE_LABELS[page.id]?.title ?? page.title;
}

export function settingsDescription(page: SettingsPageDef): string {
  return PAGE_LABELS[page.id]?.description ?? page.description;
}

export function settingsGroupTitle(group: SettingsGroupDef): string {
  return GROUP_LABELS[group.id] ?? group.title;
}
