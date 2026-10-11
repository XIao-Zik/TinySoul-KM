/**
 * zh-CN segment: the history feature. Keys are the collapsed English source
 * strings; untranslated entries fall back to English.
 */
export const historyText: Record<string, string> = {
  // DayListPanel
  "No recorded days yet": "还没有已记录的业务日",
  "Finished conversations are committed to the Session record of their day.":
    "已结束的对话会提交到所属业务日的 Session 记录中。",
  active: "进行中",
  "Session map of this day": "当日的 Session 地图",
  // DayTurnsPanel
  "No conversations on {day} yet": "{day} 还没有任何对话",
  "Finished turns appear here once they are committed.":
    "已结束的对话轮提交后会显示在这里。",
  "This archived day has no committed conversations.":
    "此已归档业务日没有已提交的对话。",
  "This day": "当天",
  "Archived · read-only": "已归档 · 只读",
  "Session map": "Session 地图",
  "In progress": "进行中",
  live: "实时",
  "Return to the running conversation": "返回进行中的对话",
  Queued: "排队中",
  "starts after the current work": "将在当前工作结束后开始",
  Completed: "已完成",
  "(no input)": "（无输入）",
  "1 question": "1 个问题",
  "{count} questions": "{count} 个问题",
  // SessionMapPanel
  "No topics yet — ask TinySoul in a conversation to organize this day.":
    "还没有主题——请在对话中让 TinySoul 整理这一天的内容。",
  "Every committed conversation is covered by a topic.":
    "每个已提交的对话都已归入主题。",
  "No committed conversations.": "没有已提交的对话。",
  "No interpretations yet.": "还没有解读。",
  "Nothing recorded here.": "此处没有记录。",
  "Locate in this day…": "在本业务日内定位…",
  Locate: "定位",
  "Loading the session map…": "正在加载 Session 地图…",
  "No completed conversations on {day}": "{day} 没有已完成的对话",
  "Once a turn finishes, its facts are committed here and the Agent can organize them into topics.":
    "对话轮结束后，其事实会提交到这里，Agent 可将其整理为主题。",
  // SessionRefPanel
  "Open conversation": "打开对话",
  "Locate within this scope…": "在该范围内定位…",
  "Locate: {query}": "定位：{query}",
  Clear: "清除",
  Relations: "关系",
  Located: "定位结果",
  Contents: "内容",
  Evidence: "证据",
  "Nothing in this scope matches the locate text.":
    "此范围内没有与定位文本匹配的内容。",
  "Nothing recorded under this reference.": "此引用下没有记录。",
  "This source has no available record in this view.":
    "此来源在此视图中没有可用记录。",
  Content: "内容",
  Facts: "事实",
  "User input": "用户输入",
  Answer: "回答",
  "Final working state": "最终工作状态",
  detail: "详情",
  "Committed turn": "已提交的对话轮",
  "finish failure": "结束失败",
  You: "你",
  "You · added": "你 · 补充",
  "Your reply": "你的回复",
  Question: "提问",
  Reasoning: "思考",
  Interaction: "互动",
  option: "选项",
  Action: "操作",
  action: "操作",
  failed: "失败",
  Request: "请求",
  Result: "结果",
  "Referenced resource": "引用的资源",
  "(unknown link)": "（未知链接）",
  "day {day}": "业务日 {day}",
  "The original binding of this dynamic reference was not recorded.":
    "此动态引用的原始绑定未被记录。",
  interpretation: "解读",
  retracted: "已撤回",
  // panelShared
  "This view belongs to a previous connection — reopen it.":
    "此视图属于之前的连接——请重新打开。",
  "Loading…": "加载中…",
  Retry: "重试",
  "Show more": "显示更多",
  "Inspect the recorded facts": "查看已记录的事实",
  // disclosure
  "Lines {start}–{end};": "第 {start}–{end} 行；",
  "characters {start}–{end} of {total} ({state})":
    "字符 {start}–{end}，共 {total}（{state}）",
  complete: "完整",
  partial: "部分",
  // entries
  History: "历史",
  "Pick a day to browse its conversations": "选择一个业务日浏览其对话",
  "Active day": "当前业务日",
  "Archived day · read-only": "已归档业务日 · 只读",
};
