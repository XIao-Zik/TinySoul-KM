/**
 * zh-CN segment: the runtime feature. Keys are the collapsed English source
 * strings; untranslated entries fall back to English.
 */
export const runtimeText: Record<string, string> = {
  // RuntimePage (tab labels; "ACP"/"MCP" stay as protocol names)
  "Execution": "执行",
  "Jobs": "后台任务",
  "Environment": "环境",

  // overview.tsx (overview strip)
  "Agent": "智能体",
  "no status": "无状态",
  "ready": "就绪",
  "starting": "启动中",
  "Day": "天数",
  "Turn": "回合",
  "none running": "无运行中的回合",
  "Copy turn id": "复制回合 ID",
  "conversation": "对话",
  "Queue": "队列",
  "waiting for your input": "等待你的输入",
  "waiting for a budget grant": "等待预算授予",
  "waiting for an event": "等待事件",
  "waiting on a timer": "等待定时器",

  // shared.tsx
  "Reading…": "读取中…",
  "The read failed ({message}).": "读取失败（{message}）。",
  "Retry": "重试",

  // executionTab.tsx
  "Reading the active turn…": "正在读取活动回合…",
  "No turn is running": "当前没有正在运行的回合",
  "New turns start from the conversation; queued turns appear below.":
    "新回合从对话中发起；排队的回合显示在下方。",
  "the turn projection is unavailable": "回合投影不可用",
  "{kind} turn": "{kind} 回合",
  "cancel requested": "已请求取消",
  "Open in conversation": "在对话中打开",
  "The latest refresh failed ({error}); the previous snapshot stays on screen.":
    "最近一次刷新失败（{error}）；先前的快照仍保留在屏幕上。",
  "cycle {cycle} needs a grant": "周期 {cycle} 需要预算授予",
  "1 background job in this turn": "本回合有 1 个后台任务",
  "{count} background jobs in this turn": "本回合有 {count} 个后台任务",
  "open Jobs": "打开后台任务",
  "Result": "结果",
  "Execution failure": "执行失败",
  "failed": "失败",
  "Output": "输出",
  "Completion": "完成结果",
  "Finish and cleanup diagnostics": "完成与清理诊断",
  "Raised while finishing or cleaning up — separate from the Turn's own result above.":
    "在完成或清理阶段产生——与上方回合自身的结果相互独立。",
  "Queued turns — cancelling one never affects the running turn.":
    "排队中的回合——取消其中一个不会影响正在运行的回合。",
  "queued": "排队中",
  "Cancel": "取消",

  // jobsTab.tsx
  "No active turn": "没有活动回合",
  "Jobs belong to the turn that started them — none is running right now.":
    "后台任务属于启动它们的回合——当前没有正在运行的回合。",
  "Jobs of turn": "回合的后台任务",
  "Reading the job list…": "正在读取任务列表…",
  "No background jobs in this turn yet.": "此回合暂无后台任务。",
  "pending request": "待处理的请求",
  "select": "选择",
  "This turn has finished — its jobs were reclaimed. The last read stays below, frozen; artifacts remain available through their links.":
    "该回合已结束——其任务已被回收。下方保留最后一次读取（已冻结）；产物仍可通过其链接访问。",
  "Turn process": "回合过程",
  "Copy job id": "复制任务 ID",
  "Stop job": "停止任务",
  "Reading the job…": "正在读取任务…",
  "the job read failed": "任务读取失败",
  "Failed to stop the job: {error}": "停止任务失败：{error}",
  "The agent has a pending request for this job — answer it in the conversation.":
    "智能体有关于此任务的待处理请求——请在对话中回复。",
  "Artifacts": "产物",
  "Details": "详情",
  "(reading…)": "（读取中…）",
  "This job produced no captured output.": "该任务没有产生任何捕获的输出。",
  "No output captured yet.": "尚未捕获到输出。",
  "Bounded read — more output is available and reading continues; this never means output was lost.":
    "有界读取——还有更多输出可用，读取将继续；这绝不意味着输出丢失。",
  "The bounded read reached its limit — the remaining output is available through the job's actual artifacts:":
    "有界读取已达上限——剩余输出可通过该任务的实际产物获取：",

  // mcpTab.tsx
  "Reading the server directory…": "正在读取服务器目录…",
  "No MCP servers configured": "未配置 MCP 服务器",
  "Servers are configuration facts — configure one in settings before its directory can be discovered.":
    "服务器是配置事实——请先在设置中配置，才能发现其目录。",
  "Configure servers": "配置服务器",
  "Filter by name or description…": "按名称或描述筛选…",
  "Filtering never connects — only the explicit refresh does.":
    "筛选不会建立连接——只有显式刷新才会。",
  "More servers": "更多服务器",
  "refresh answered \"{status}\" — the known directory stays":
    "刷新返回“{status}”——已知目录保持不变",
  "enabled": "已启用",
  "disabled": "已停用",
  "connected": "已连接",
  "not connected": "未连接",
  "discovered · {count} tools": "已发现 · {count} 个工具",
  "not discovered": "未发现",
  "stale": "已过期",
  "error": "错误",
  "Refresh this server's directory": "刷新该服务器的目录",
  "Enable the server in settings before refreshing":
    "请先在设置中启用该服务器，再进行刷新",
  "Refresh directory": "刷新目录",
  "Refresh failed ({note}); the previous directory stays.":
    "刷新失败（{note}）；先前的目录保持不变。",
  "Reading the discovered tools…": "正在读取已发现的工具…",
  "Tools of {server}": "{server} 的工具",
  "This server's directory was never discovered — use its explicit refresh to read the tools.":
    "该服务器的目录从未被发现——请使用其显式刷新来读取工具。",
  "The discovered directory has no tools.": "已发现的目录中没有工具。",
  "callable": "可调用",
  "unavailable": "不可用",
  "More tools": "更多工具",
  "Reading the tool…": "正在读取工具…",
  "Configuration selection": "配置选择",
  "selected": "已选择",
  "not selected": "未选择",
  "by {basis}": "依据 {basis}",
  "Edit configuration": "编辑配置",
  "Use in conversation": "在对话中使用",
  "Definition": "定义",
  "Please use the MCP tool {tool} of server {server}{description}:":
    "请使用服务器 {server} 的 MCP 工具 {tool}{description}：",

  // acpTab.tsx
  "Reading the subagent directory…": "正在读取子代理目录…",
  "Reading this page never connects to a subagent — connections are established by delegations.":
    "浏览此页面不会连接到子代理——连接仅由委托建立。",
  "Re-read": "重新读取",
  "No subagent targets configured": "未配置子代理目标",
  "Targets are configuration facts — add one in settings before a delegation can use it.":
    "目标是配置事实——请先在设置中添加，委托才能使用。",
  "Open ACP settings": "打开 ACP 设置",
  "Configured targets": "已配置的目标",
  "Delegate in conversation": "在对话中委托",
  "Connections": "连接",
  "No live connections. A connection appears when a delegation starts and an idle one can be reused across turns.":
    "暂无活动连接。委托开始时会出现连接，空闲的连接可跨回合复用。",
  "Connections — this generation's runtime facts": "连接——本世代的运行时事实",
  "Copy connection id": "复制连接 ID",
  "turn {turn}": "回合 {turn}",
  "idle — reusable across turns": "空闲——可跨回合复用",
  "Job {job}": "任务 {job}",
  "Please delegate a task to the {agent} subagent:":
    "请将任务委托给子代理 {agent}：",

  // environmentTab.tsx
  "Sources — owner projections": "来源——所有者投影",
  "A source failed — only live watching is affected; formal Workspace operations stay available.":
    "有来源失败——仅影响实时监视；正式的 Workspace 操作仍然可用。",
  "No environment sources are bound to this generation.":
    "此世代未绑定任何环境来源。",
  "topics: {topics}": "主题：{topics}",
  "Recorded environment events": "已记录的环境事件",
  "source": "来源",
  "topic": "主题",
  "turn": "回合",
  "all": "全部",
  "Reading the retained observation…": "正在读取保留的观测记录…",
  "No environment events in the retained window": "保留窗口内没有环境事件",
  "match these filters": "匹配这些筛选条件",
  ". Only what was actually recorded is shown.": "。仅显示实际记录的内容。",

  // runtimeModel.ts
  "This view belongs to a previous connection — reopen it.":
    "此视图属于之前的连接——请重新打开。",
};
