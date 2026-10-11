/**
 * zh-CN segment: the resources feature (ResourceRouter, search, references,
 * reflection, media). Keys are the collapsed English source strings;
 * untranslated entries fall back to English.
 */
export const resourcesText: Record<string, string> = {
  // ReferencesPanel
  References: "引用",
  "Close references": "关闭引用",
  "Direct references": "直接引用",
  "It references": "引用的内容",
  "No outgoing references.": "没有向外的引用。",
  "Copy reference": "复制引用",
  "Quote in conversation": "在对话中引用",
  Backlinks: "反向引用",
  "Referenced by": "被引用",
  "Reading search capabilities…": "正在读取搜索能力…",
  "Backlink search is not declared for this owner.":
    "此属主未声明反向引用搜索。",
  "Find documents that reference this one": "查找引用此文档的文档",
  "Nothing references this document yet.": "还没有内容引用此文档。",
  "Show more": "显示更多",
  // ReflectionDialog
  "Not connected to a backend.": "未连接到后端。",
  "Organize Home": "整理 Home",
  "Organize Memory": "整理 Memory",
  Home: "人设",
  Memory: "记忆",
  "Other root work is active or queued — this reflection queues behind it and runs when the queue reaches it.":
    "其他根任务正在进行或已排队——本次整理将排在其后，队列轮到时运行。",
  "Reading what can be organized…": "正在读取可整理的内容…",
  "1 overlay change pending review. A Home reflection decides what becomes the accepted baseline — the page itself never accepts or rejects.":
    "1 项覆盖层变更待审核。Home 整理会决定哪些内容成为已接受的基线——页面本身从不接受或拒绝。",
  "{count} overlay changes pending review. A Home reflection decides what becomes the accepted baseline — the page itself never accepts or rejects.":
    "{count} 项覆盖层变更待审核。Home 整理会决定哪些内容成为已接受的基线——页面本身从不接受或拒绝。",
  "No Home changes are pending review; the reflection skips model execution and cleans up run copies that have no changes.":
    "没有待审核的 Home 差异；整理会跳过模型执行，并清理没有变更的运行副本。",
  "{count} Skill memory entries pending organization.":
    "{count} 项 Skill memory 待整理。",
  "Target day": "目标日",
  "No source days were suggested from the scanned days.":
    "扫描的业务日中没有建议的来源日。",
  "This day has no persistent daily document yet — a clue, not an authorization":
    "此业务日尚无持久化的 daily 文档——这只是线索，不是授权",
  "no daily yet": "尚无 daily",
  "Look further back (before {day})": "继续向前查看（早于 {day}）",
  "Or pick a day:": "或选择日期：",
  "Custom target day": "自定义目标日",
  Instructions: "整理指示",
  "This run's instructions": "本次运行的指示",
  "What to focus on while reviewing Home…": "审核 Home 时重点关注什么…",
  "What this day should settle into persistent knowledge…":
    "这一天应沉淀为哪些持久知识…",
  "Reflection instructions": "整理指示",
  Cancel: "取消",
  "Start Home reflection": "开始 Home 整理",
  "Start Memory reflection": "开始 Memory 整理",
  "The root queue is full right now — your request was not queued. The instructions are kept; try again in a moment.":
    "根队列当前已满——你的请求未入队。指示内容已保留，请稍后重试。",
  // SearchPanel
  "Close search": "关闭搜索",
  "Search is not declared for this owner in the current generation.":
    "当前世代未为此属主声明搜索。",
  "Search query": "搜索查询",
  "Search scope": "搜索范围",
  Search: "搜索",
  Conditions: "条件",
  "· literal/regex": "· 字面/正则",
  Literal: "字面",
  Regex: "正则",
  "Case sensitive": "区分大小写",
  any: "任意",
  Exclude: "排除",
  "refs, space separated": "引用，以空格分隔",
  "Find documents related to {label}": "查找与 {label} 相关的文档",
  "Re-search": "重新搜索",
  "The page context changed — these results are frozen.":
    "页面上下文已变化——结果已冻结。",
  "Steps:": "步骤：",
  "No results — nothing matched, or the steps excluded everything.":
    "没有结果——没有匹配项，或步骤排除了全部内容。",
  "Content coverage: {coverage}": "内容覆盖：{coverage}",
  "Refine criterion…": "细化条件…",
  "Refine criterion": "细化条件",
  "Filter by meaning": "按语义筛选",
  "Re-rank": "重新排序",
  "Apply attribute filter to results": "对结果应用属性筛选",
  "1 result": "1 条结果",
  "{count} results": "{count} 条结果",
  "{count} shown": "显示 {count} 条",
  "scanned {count}": "已扫描 {count}",
  "{count} omitted by budget": "{count} 条因预算被省略",
  "source not fully scanned": "来源未完全扫描",
  // links
  "Open {ref}": "打开 {ref}",
  "Loading image…": "正在加载图片…",
  "The image reference is empty.": "图片引用为空。",
  "The image could not be loaded.": "图片无法加载。",
  "A relative image needs the resource it was read from.":
    "相对图片引用需要其来源资源。",
  "This image reference is not readable.": "此图片引用不可读取。",
  "not embeddable": "无法内嵌",
  "Open resource": "打开资源",
  Copied: "已复制",
  Image: "图片",
  // ChunkedMarkdown
  "Referenced resource": "引用的资源",
  // router
  "This text is not a resource reference.": "此文本不是资源引用。",
  "A relative reference needs the resource it was read from.":
    "相对引用需要其来源资源。",
  "This reference cannot be routed.": "此引用无法路由。",
  "This dynamic reference has no recorded binding, so its target cannot be known from here.":
    "此动态引用没有已记录的绑定，无法从此处确定其目标。",
  "The resolved locator has no reference.": "解析得到的定位器缺少引用。",
  "This Session reference has no recorded day binding.":
    "此 Session 引用没有已记录的业务日绑定。",
  'The resolved owner of "{ref}" is not routable.':
    "“{ref}”解析出的属主不可路由。",
  "This trace reference is no longer available — its Turn context has closed.":
    "此 trace 引用已不可用——其 Turn 上下文已关闭。",
  "Reference copied.": "引用已复制。",
  "Copy failed.": "复制失败。",
  "Please refer to {ref}.": "请参考 {ref}。",
  "Please refer to {ref} ({source}).": "请参考 {ref}（{source}）。",
  "from today's workspace": "来自今天的工作区",
  "from the archived workspace of {day}": "来自 {day} 的已归档工作区",
  "from Home, {view} view": "来自 Home，{view} 视图",
  "bound to {ref}, {day}": "绑定到 {ref}，{day}",
  "bound to {ref}": "绑定到 {ref}",
  "from {day}": "来自 {day}",
  "from the conversation record of {day}": "来自 {day} 的对话记录",
  "from the run of {day}": "来自 {day} 的运行",
  // searchModel
  "This query needs a narrower scope — pick a directory or add attribute conditions.":
    "此查询需要更窄的范围——请选择目录或添加属性条件。",
  "The frozen result view expired on the backend. Run the search again.":
    "冻结的结果视图已在后端过期。请重新运行搜索。",
  "The search source is unavailable right now.": "搜索来源当前不可用。",
  "A search step failed: {detail}": "搜索步骤失败：{detail}",
};
