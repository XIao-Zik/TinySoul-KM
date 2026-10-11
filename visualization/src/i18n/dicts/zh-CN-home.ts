/**
 * zh-CN segment: the home feature. Keys are the collapsed English source
 * strings; untranslated entries fall back to English. The feature name
 * "Home" is kept as-is (a proper concept, like TinySoul).
 */
export const homeText: Record<string, string> = {
  // HomePage
  "All of Home": "整个 Home",
  "Agent space": "Agent 空间",
  "Skills": "技能",
  "Not connected to a backend.": "未连接到后端。",
  "Content search reads effective Home — switched to the effective view.":
    "内容搜索仅读取生效 Home —— 已切换到生效视图。",
  "Effective": "生效",
  "Actual": "实际",
  "What the next run uses": "下一次运行所使用的内容",
  "The accepted baseline": "已接受的基线",
  "Changes": "变更",
  "Search content": "搜索内容",
  "Organize Home": "整理 Home",
  "The identity, preferences, skills and guidance the next run uses. Pick an entry from the directory.":
    "下一次运行所使用的身份、偏好、技能与指引。请从目录中选择一个条目。",
  "The accepted baseline. Switch back to effective to see the content runs actually use.":
    "已接受的基线。切换回生效视图可查看运行实际使用的内容。",
  "{view} view": "{view} 视图",
  "Search Home": "搜索 Home",
  "Search effective Home…": "搜索生效 Home…",

  // HomeDirectory
  "Filter directory…": "筛选目录…",
  "Filter Home directory": "筛选 Home 目录",
  "Reading the Home directory…": "正在读取 Home 目录…",
  "The directory could not be read": "无法读取目录",
  "Retry": "重试",
  "Nothing in this view": "此视图中暂无内容",
  "No matches": "无匹配结果",
  "The accepted baseline has no entries here.": "已接受的基线在此处没有条目。",
  "Effective Home has no entries here.": "生效 Home 在此处没有条目。",
  "No Home entries match \"{query}\".": "没有匹配“{query}”的 Home 条目。",
  "Top content": "顶层内容",
  "General skills": "通用技能",
  "Resources": "资源",
  "Guidance": "指引",
  "Show more": "显示更多",
  "skill": "技能",
  "top entry": "顶层条目",

  // HomeChanges
  "Overlay changes proposed by runs, waiting for a Home reflection's review. Read-only here.":
    "运行提出的覆盖变更，等待 Home 反思审核。此处为只读。",
  "Reading overlay changes…": "正在读取覆盖变更…",
  "The changes could not be read": "无法读取变更",
  "No overlay changes": "没有覆盖变更",
  "Effective Home currently matches the accepted baseline.":
    "生效 Home 当前与已接受的基线一致。",
  "The actual baseline changed since this overlay change was recorded":
    "记录此覆盖变更后，实际基线已发生变化",
  "diverged": "已偏离",

  // HomeContentView
  "References and backlinks": "引用与反向链接",
  "Copy reference": "复制引用",
  "Quote in conversation": "在对话中引用",
  "Reading the document…": "正在读取文档…",
  "Not readable as text": "无法作为文本读取",
  "is not a UTF-8 text resource, so the page cannot preview it. You can still copy its reference or quote it in the conversation.":
    "不是 UTF-8 文本资源，页面无法预览。你仍可以复制其引用或在对话中引用它。",
  "Not in the {view} view": "不在{view}视图中",
  "does not exist in the {view} Home": "不存在于{view} Home 中",
  ". It may exist only as an overlay change — check the effective view.":
    "。它可能仅作为覆盖变更存在——请查看生效视图。",
  "The document could not be read": "无法读取文档",
  "This document is empty": "此文档为空",
  "exists in the {view} Home but has no content.":
    "存在于{view} Home 中，但没有内容。",

  // HomeDiffView
  "Back to changes": "返回变更列表",
  "actual → effective": "实际 → 生效",
  "Unified": "统一视图",
  "Side by side": "并排视图",
  "The accepted baseline changed after this overlay change was recorded, so this diff is against an older baseline. Re-read the effective content, or start a Home reflection to settle it.":
    "已接受的基线在此覆盖变更记录后发生了变化，因此该差异基于旧基线。请重新读取生效内容，或启动一次 Home 反思来解决。",
  "actual {actual} chars · effective {effective} chars":
    "实际 {actual} 字符 · 生效 {effective} 字符",
  "Reading the diff…": "正在读取差异…",
  "The diff could not be read": "无法读取差异",
  "No difference": "没有差异",
  "The effective content matches the accepted baseline for this entry.":
    "此条目的生效内容与已接受的基线一致。",
};
