/**
 * zh-CN segment: global shell (TopBar, NavRail, StatusBar, AppShell,
 * ConnectScreen). Keys are the collapsed English source strings.
 */
export const shellText: Record<string, string> = {
  // TopBar
  "turn active": "任务进行中",
  History: "历史",
  Organize: "整理",
  Context: "上下文",
  "Restart backend": "重启后端",
  "Restart the backend?": "重启后端？",
  "The host rebuilds the current Agent generation. The running turn is stopped and the view re-synchronizes afterwards. The endpoint itself keeps its address and event history.":
    "宿主将重建当前 Agent 运行世代。进行中的 Turn 会停止，界面随后重新同步。Endpoint 本身保持地址与事件历史不变。",
  Cancel: "取消",
  Restart: "重启",
  "connecting…": "连接中…",
  "reconnecting…": "重连中…",
  disconnected: "未连接",
  // NavRail
  Chat: "对话",
  Workspace: "工作区",
  Home: "人设",
  Memory: "记忆",
  Runtime: "运行时",
  "Switch to light theme": "切换到浅色主题",
  "Switch to dark theme": "切换到深色主题",
  Settings: "设置",
  // StatusBar
  "not responding…": "无响应…",
  connected: "已连接",
  ready: "就绪",
  "starting…": "启动中…",
  "day {day}": "业务日 {day}",
  "waiting for input": "等待输入",
  "{kind} turn · {state}": "{kind} 轮 · {state}",
  // AppShell
  "The backend is not responding — the conversation stays in place and reconnects automatically.":
    "后端无响应——对话保持原位，将自动重连。",
  // ConnectScreen
  "Connect to TinySoul": "连接到 TinySoul",
  "The app is a pure client of a running TinySoul Endpoint. Enter the client-reachable address (IP:Port, http(s) URL) and the access token the instance published.":
    "本应用是运行中的 TinySoul Endpoint 的纯客户端。输入客户端可达的地址（IP:端口，http(s) URL）与实例发布的访问令牌。",
  Address: "地址",
  Token: "令牌",
  "Connecting…": "连接中…",
  Connect: "连接",
  "Use the local instance of this project": "使用本项目本机实例",
};
