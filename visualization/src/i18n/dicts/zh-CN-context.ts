/**
 * zh-CN segment: the context feature. Keys are the collapsed English source
 * strings; untranslated entries fall back to English.
 */
export const contextText: Record<string, string> = {
  // entries.tsx (drawer titles/subtitles)
  Context: "上下文",
  "Session map / Loaded background": "会话地图 / 已加载背景",
  // "Turn" is kept as a domain term in zh-CN prose (see zh-CN-shell).
  "Turn {turnId}": "Turn {turnId}",
  "owner {owner}": "归属 {owner}",
  "Owner's current content": "Owner 的当前内容",

  // ContextInspectorPanel.tsx
  "Current Context": "当前上下文",
  "Session map": "会话地图",
  "Loaded Home": "已加载人设",
  "Loaded Memory": "已加载记忆",
  "No context is currently running": "当前没有运行中的语境",
  "The Home and Memory sub-tabs keep the latest loaded content from the session.":
    "Home 和 Memory 子页保留最近会话已加载的正文。",
  "Reflection source: {day}": "整理来源：{day}",
  "No active day": "暂无业务日",
  "The Session map is available after the Agent establishes a calendar day.":
    "Agent 建立业务日后，会话地图才可用。",
  "No session background yet": "暂无会话背景",

  // BackgroundPanel.tsx
  "Organizing finished; only this panel's recently read content is kept.":
    "整理已结束；仅保留此面板最近读取的内容",
  "Background snapshot of the completed session": "已完成会话的背景快照",
  "Loaded in this turn": "本轮已加载",
  "No organize background was read": "没有读取到整理背景",
  "See the Context of the actual model calls in Details.":
    "可从 Details 中查看实际模型调用的 Context。",
  "This turn saved no background content": "这轮会话没有保存背景正文",
  "No {owner} content loaded": "未加载{owner}内容",
  Home: "人设",
  Memory: "记忆",
  Default: "默认",
  Auto: "自动",
  "On demand": "按需",
  "{chars} chars": "{chars} 字",

  // OverviewPanel.tsx
  "Reading the installed context…": "正在读取已安装的语境…",
  Retry: "重试",
  "This turn's context is closed": "本轮语境已关闭",
  "The turn ended before its context was read. Browse the day history for its committed record.":
    "Turn 在语境被读取前已结束。可浏览业务日历史查看其提交记录。",
  "Browse history": "浏览历史",
  "Open current context": "打开当前语境",
  Captured: "捕获于",
  "Day {day}": "业务日 {day}",
  "Usage in characters": "用量（按字符计）",
  "No segments installed": "未安装任何语境分段",
  "This turn has not installed any context segments yet.":
    "本轮尚未安装任何语境分段。",
  empty: "空",

  // ContextInspectPanel.tsx
  Locate: "定位",
  "in this scope": "于当前范围内",
  "Locate in this scope…": "在当前范围内定位…",
  Content: "内容",
  Relations: "关系",
  Evidence: "证据",
  "Nothing disclosed here": "此处没有已展开的内容",
  "This ref currently expands to no readable items.":
    "此 ref 当前没有可读取的展开项。",

  // SegmentPanel.tsx
  "Installed body": "已安装正文",
  "Closed before this segment was read": "分段未及读取即已关闭",
  "The turn ended before this body was captured; the day history holds the committed record.":
    "Turn 在此正文被捕获前已结束；业务日历史中保存着已提交的记录。",
  "Empty segment": "空分段",
  "This segment installed no body content.": "本分段未安装任何正文内容。",
  "Declared resources": "声明的资源",
  installed: "已安装",
  available: "可用",
  "Installed in this turn's context; opening reads the owner's current content.":
    "已安装至本轮语境；打开将读取 Owner 的当前内容。",
  "Declared but not loaded into this turn's context; opening reads the owner's current content.":
    "已声明但未载入本轮语境；打开将读取 Owner 的当前内容。",
  "No resources declared.": "未声明任何资源。",
  "Opening a resource reads the owner's current content — it does not load it into this turn's context.":
    "打开资源将读取 Owner 的当前内容——不会将其载入本轮语境。",
  "Entry points": "入口",
  "Read the live disclosure of this ref.": "读取此 ref 的实时展开内容。",
  "This segment declares no inspect route.": "本分段未声明 inspect 读取路由。",
  "Browse day history": "浏览业务日历史",
  Details: "详情",
  "segment id": "分段 ID",
  owner: "归属",
  slot: "槽位",
  shape: "形态",
  order: "顺序",
  usage: "用量",
  capabilities: "能力",
  "root refs": "根引用",
  "protected refs": "受保护引用",
  "read only": "只读",
  none: "无",
  "Open the Workspace page": "打开工作区页面",
  "Open Runtime observation": "打开运行时观察",

  // OwnerResourcePanel.tsx
  "Resolving {reference}…": "正在解析 {reference}…",
  "Could not resolve this reference": "无法解析此引用",
  "This reference needs its original binding": "此引用需要其原始绑定",
  "“{reference}” is a dynamic reference whose original day/turn binding is no longer available. The current owner content is not substituted for it.":
    "“{reference}”是动态引用，其原始的业务日/Turn 绑定已不可用。不会以 Owner 当前内容替代。",
  "This reference opens in its owner page": "此引用将在其 Owner 页面打开",
  "The context drawer reads Home and Memory resources in place; other owners have their own pages.":
    "Context 抽屉就地读取 Home 与 Memory 资源；其他 Owner 有各自的页面。",
  "The owner's current content ({view} view) — not the snapshot installed in this turn.":
    "Owner 的当前内容（{view} 视图）——不是本轮安装的快照。",
  "The owner's current content — not the snapshot installed in this turn.":
    "Owner 的当前内容——不是本轮安装的快照。",
  "Empty document": "空文档",
  "The owner reports no content for this resource.":
    "Owner 报告此资源没有内容。",
  "Referenced from here": "此处引用的资源",
  "Resolution chain": "解析链",
  "step {step}": "步骤 {step}",

  // panelShared.tsx
  "This view belongs to a previous connection — reopen it.":
    "此视图属于先前的连接——请重新打开。",
  "The installed context changed — refresh to see the latest view.":
    "已安装的语境已变化——刷新以查看最新视图。",
  Refresh: "刷新",
  "This turn has ended — what you see is the last captured view.":
    "本轮已结束——当前显示的是最后捕获的视图。",
  "Loading…": "加载中…",
  "Show more": "显示更多",

  // segments.ts (slot/shape labels, usage and status lines)
  Background: "背景",
  Trace: "轨迹",
  Working: "工作",
  State: "状态",
  Heap: "堆",
  Stack: "栈",
  Map: "地图",
  "{bytes} of images": "{bytes} 图片",
  "{installed} installed · {available} available":
    "{installed} 已安装 · {available} 可用",
  "{count} root ref": "{count} 个根引用",
  "{count} root refs": "{count} 个根引用",
};
