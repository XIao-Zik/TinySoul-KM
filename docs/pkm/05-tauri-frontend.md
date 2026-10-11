# Tauri 前端改造

> 状态：草案 v1 ｜ 里程碑：M5 ｜ 依赖：[03](03-retrieval.md)、[04](04-reflection-and-cards.md)

## 1. 现状盘点（已核实）

- 位置：仓库根 `visualization/`，pnpm workspace；
- 栈：**Tauri 2**（`src-tauri/`，`productName: TinySoul`）+ **React 19** + TypeScript + Vite + Tailwind 4 + zustand（状态）+ react-markdown/KaTeX/mermaid（渲染）+ i18n + Playwright（E2E）；
- 源码结构：`src/{api, app, components, features, hooks, i18n, store, styles, types, utils}`——feature 化组织，对新增模块友好；
- 与后端的通信走 endpoint 协议（`docs/design/endpoint/index.md`），`src/api/` 封装。

**本机前置（M0 完成）**：Node 24 ✅；**Rust 工具链缺失**，需 `winget install Rustlang.Rustup`（或 rustup-init.exe）+ MSVC Build Tools；随后 `pnpm install && pnpm tauri dev` 跑通。若 Rust 安装受阻，过渡方案：`pnpm dev` 起浏览器版（Vite dev 页）连同一后端，M5 交付不打折，只是没有桌面壳。

## 2. 改造原则

1. **只加不改**：新增 `src/features/km/` 模块 + 路由入口；现有会话/设置/Home 页不动——与上游合并的冲突面趋近于零；
2. **协议先行**：后端新能力尽量通过既有 endpoint 消息 + action 体系暴露（前端本就能发起 Turn、读 Session/Workspace 投影）；确需新消息时在 `src/api/` 隔离封装并在 06 文档登记；
3. 渲染复用现成组件（markdown/katex/mermaid），不引新 UI 库。

## 3. 页面规划（新增 `features/km/`）

| 视图 | 内容 | 数据来源 |
|---|---|---|
| **检索页** | 查询框 → 结果列表（标题/摘要/命中高亮）→ 点开全文抽屉（右侧滑出，正文 markdown 渲染，refs 可点跳转） | 发起 Turn 内 `km.search`（对话式检索，沿用既有会话流）或直连只读检索通道（若 endpoint 提供 SDK 只读 search，实现时确认；否则走 Turn） |
| **卡片流** | 按日分组的知识卡片瀑布流；卡片 = 问答体 + concept 标签 + source_refs 链接；支持"标记无用"（写回 confidence 反馈文件） | 读 `knowledge/cards/*.md`（经 workspace 投影或新增只读 endpoint 消息） |
| **图谱视图** | 笔记↔笔记、笔记↔memory concept 的引用边图；节点按 `km_source` 着色；mermaid 或轻量 canvas 力导向 | 新增只读数据出口：`km-graph`（后端 `runtime_bridge.py` 从 index.json 生成节点/边 JSON；通过 endpoint 新增一条只读查询消息——**唯一的新协议面**，登记进白名单附录） |
| **导入面板** | vault 路径配置、最近导入统计（新增/更新/tombstone）、`--dry-run` 预览结果、向量缓存重建按钮 | 调 CLI（Tauri sidecar/shell）或后端 ingest service（二选一，实现时定：sidecar 更解耦） |
| **盲区占位** | 二期：`km.gaps` 报告展示（M5 只留路由） | — |

## 4. 后端配合改动（小而明确）

| 改动 | 位置 | 说明 |
|---|---|---|
| `km-graph` 只读查询 | `plugins/knowledge/runtime_bridge.py` + endpoint 只读消息 | 从 index.json 现算节点/边（< 10k 节点直接全量），无持久化 |
| 卡片/笔记只读投影 | 同上 | 遵循"Workspace 只提供引用与状态，正文经有界页"的既有语义（AGENTS.md 语境模型），复用 DisclosurePage 分页 |
| ingest 触发 | 优先 Tauri sidecar 调 CLI（零后端改动）；备选：endpoint 新增受控 ingest 消息 | 前者改动最小，先走 |

## 5. 工期拆解（M5 内部）

1. Rust 环境就绪 + 空跑现有前端（0.5 天，M0 已含）；
2. `features/km/` 骨架 + 路由 + i18n 词条（0.5 天）；
3. 检索页（2–3 天，含 Turn 流对接与高亮）；
4. 卡片流（1–2 天）；
5. 图谱视图（2–3 天，含 `km-graph` 后端出口）；
6. 导入面板（1–2 天）；
7. E2E（Playwright 既有框架）冒烟：导入→检索→卡片→图谱（1 天）。

## 6. 风险

| 风险 | 缓解 |
|---|---|
| Rust/MSVC 安装受阻 | 过渡方案 §1 末尾；桌面壳可最后补 |
| endpoint 协议扩展与上游冲突 | 新消息独立文件 + 只读语义；协议变更在上游文档处同步登记 |
| 图谱大库渲染卡顿 | 前端默认折叠到"当日相关 + 一跳邻域"，全图懒加载 |
| 前后端版本错位（可编辑安装跟随分支） | 前端构建产物不进 git；`pnpm build` 产物喂 Tauri bundle，开发期一律 dev 模式 |
