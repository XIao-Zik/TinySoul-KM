/**
 * zh-CN segment: the memory feature. Keys are the collapsed English source
 * strings; untranslated entries fall back to English. Document names such as
 * Memory.md are kept as-is (backend identity).
 */
export const memoryText: Record<string, string> = {
  // MemoryPage
  "All knowledge": "全部知识",
  "Daily": "每日",
  "Entities": "实体",
  "Concepts": "概念",
  "Facts": "事实",
  "Notes": "笔记",
  "Not connected to a backend.": "未连接到后端。",
  "Active memory": "活动记忆",
  "Knowledge": "知识",
  "What the agent is recording this day": "智能体当天正在记录的内容",
  "Organized persistent knowledge": "已整理的持久知识",
  "Search knowledge": "搜索知识",
  "Organize Memory": "整理记忆",
  "Persistent daily, entity, concept, fact and note documents. Pick one from the list, or search the knowledge base.":
    "每日、实体、概念、事实与笔记的持久文档。请从列表中选择，或搜索知识库。",
  "Search Memory": "搜索记忆",
  "Search persistent knowledge…": "搜索持久知识…",

  // MemoryNav
  "All": "全部",
  "Memory day": "记忆日期",
  "Active day": "活动日",
  "Active · {day}": "活动 · {day}",
  "{day} (archived)": "{day}（已归档）",
  "The day binds only this Memory.md reading — persistent knowledge below is not reinterpreted as that day's version.":
    "该日期仅绑定本次 Memory.md 阅读 —— 下方的持久知识不会被重新解释为当天的版本。",
  "Filter knowledge…": "筛选知识…",
  "Filter knowledge": "筛选知识",
  "Reading the knowledge catalog…": "正在读取知识目录…",
  "The catalog could not be read": "无法读取目录",
  "Retry": "重试",
  "No persistent knowledge yet": "暂无持久知识",
  "Knowledge settles when a Memory reflection organizes a day. You can also just keep talking — the active memory records as you go.":
    "知识会在记忆反思整理某一天时沉淀。你也可以继续对话 —— 活动记忆会随对话自动记录。",
  "Start a conversation": "开始对话",
  "No matches": "无匹配结果",
  "No knowledge documents match this filter.": "没有符合此筛选条件的知识文档。",
  "Redirects to {ref}": "重定向至 {ref}",
  "redirect": "重定向",
  "Show more": "显示更多",

  // ActiveMemoryView
  "active · {day}": "活动 · {day}",
  "active day": "活动日",
  "What the agent is recording this day — read-only here.":
    "智能体当天正在记录的内容 —— 此处只读。",
  "Copy reference": "复制引用",
  "Quote in conversation": "在对话中引用",
  "Reading the active memory…": "正在读取活动记忆…",
  "No archived memory for this day": "此日没有归档记忆",
  "{day} has no archived Memory.md. Days without one are simply not archived — pick another day.":
    "{day} 没有归档的 Memory.md。没有记忆的日子不会归档 —— 请选择其他日期。",
  "The active day has no Memory.md binding.": "活动日没有绑定 Memory.md。",
  "The active memory is unavailable": "活动记忆不可用",
  "The active memory could not be read": "无法读取活动记忆",
  "Nothing recorded yet": "尚未记录任何内容",
  "The active Memory.md exists but has no content for this day.":
    "活动 Memory.md 存在，但这一天没有内容。",

  // MemoryDocumentView
  "References and backlinks": "引用与反向链接",
  "This document redirects to": "此文档重定向至",
  ". The original content below is kept as recorded.": "。以下内容保留原始记录。",
  "Open target": "打开目标",
  "Reading the document…": "正在读取文档…",
  "This document is missing": "此文档缺失",
  "is not in persistent Memory. It may have been merged into another document.":
    "不在持久记忆中。它可能已合并到另一个文档。",
  "The document could not be read": "无法读取文档",
  "This document is empty": "此文档为空",
  "exists in persistent Memory but has no content.":
    "存在于持久记忆中，但没有内容。",
};
