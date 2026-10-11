# TinySoul-KM 总体计划（总纲）

> 状态：草案 v1（待确认 D1 技术路线后定稿）
> 日期：2026-10-11
> 分支：`pkm`（基线 tag `upstream-baseline`）
> 子文档：见文末索引，本文件只记大纲与决策，细节全部下沉到子文档。

## 1. 项目定位

**TinySoul-KM**：基于 TinySoul-Agent 运行时的本地个人知识管理 Agent。核心能力：

1. 把本地 Obsidian/Markdown 笔记库和聊天记录导出收进统一知识库；
2. 自然语言检索（词法 + 向量混合），结果带来源引用、可溯源到原笔记；
3. 每日主动整理：摘要当日消化内容、生成知识卡片（MVP 简版）；
4. 桌面交互：改造自带 Tauri 前端为知识管理界面。
5. （二期）联网降级检索与知识勘误审计：知识库严格优先于网络搜索，网络仅补位；并定期将知识库陈述与网络来源对撞自检，防止错误长期潜伏。

这是一个简历项目：**所有里程碑都有可量化产出与演示路径**（见 `06-testing-eval-and-packaging.md`）。

## 2. 与 DeepSeek 原方案的关系

DeepSeek 计划（2026-10 会话）提供了正确的**产品主线**（导入→检索→反思→卡片→交互→评估→包装），但基于对 TinySoul 内部的过时假设。本计划采纳其主线，修正其技术假设：

| # | DeepSeek 假设 | TinySoul 实际 | 本计划的修正 |
|---|---|---|---|
| 1 | Memory 是"Facts/Annotations"两层，需要扩展 | 那是 Session 的模型；Memory 是"每日活动 Memory.md + 五类持久文档（daily/entity/concept/fact/note，带类型化关系）" | 不动 Memory 的五类契约；外部笔记作为**新存储 owner（knowledge 插件）**，长期实体/概念沉淀仍走 memory |
| 2 | 自建 ChromaDB + sentence-transformers 向量检索 | 内核已有完整检索管道（query/backlinks/directory + select/rerank/filter），memory 已内置 EmbeddingIndex（onnxruntime）与词法+向量融合 | 复用内置管道，**不引入 ChromaDB**（完整论证见 `01-architecture-and-decisions.md` §2）；插件内留 VectorBackend 薄接口作为将来切换的缓冲 |
| 3 | 知识图谱从零建 | memory 的 entity/concept 类型化关系就是图谱；缺的是"外部笔记"这个来源，不是图谱结构 | 图谱 = memory 关系 + knowledge 笔记引用边，不新建图存储 |
| 4 | 自造"每日反思"流水线 | 内核已有 Reflection Turn 机制（TurnProfile 独立执行情景、每日策略自动排根 work） | 复用 reflection 插件，只做配置 + 卡片生成 executor |
| 5 | 新增 tinysoul-km CLI（search/card/…） | CLI 只有 `start/init/reset`；且已决定改 Tauri 前端，命令行需求大幅缩小 | 只加**一个** `km-ingest` 导入子命令（外部工具场景），其余交互全走前端 |
| 6 | Python 3.12 兜底 | 已就绪：conda env `TinySoul-PKM`（3.13 + 可编辑安装 + dev 依赖） | 删除该兜底项 |

## 3. 已确认的决策

| ID | 决策 | 内容 | 状态 |
|---|---|---|---|
| D1 | 技术路线 | 顺应原生架构：knowledge 插件为存储 owner，复用内置检索/向量设施，图谱用 memory entity/concept 关系。**不引入独立 ChromaDB** | ⚠️ 待最终确认（论证见 01 文档 §2，含"如果你仍想要 ChromaDB"的切换代价分析） |
| D2 | 数据源 | MVP：Obsidian/Markdown 库 + 聊天记录导出（DeepSeek 等平台导出文件）。二期：PDF/Zotero、网页剪藏 | ✅ 已确认 |
| D3 | 交互层 | 改造自带 Tauri 前端（`visualization/`，Tauri 2 + React 19 + Tailwind 4 + zustand）。前置：需安装 Rust 工具链（本机尚缺，Node 24 已有） | ✅ 已确认 |
| D4 | MVP 范围 | 检索闭环 + 每日反思简版（摘要 + 知识卡片）进 MVP；盲区发现、PDF/Zotero、网页剪藏 → 二期 | ✅ 已确认 |
| D5 | 版本管理 | `main` = 上游基线不动；所有改动在 `pkm` 分支；运行环境 conda `TinySoul`（原版冻结）/ `TinySoul-PKM`（可编辑安装，跟随 `pkm` 工作树） | ✅ 已完成搭建 |
| D6 | 二期能力启用 | 启用闲置能力落地 6 项功能：Zotero/MCP 文献接入、SDK 无人值守+评测、联网降级检索（**知识库严格优先于网络**）、**知识勘误审计（自检）**、深度整理 Job、研究项目 Workspace、网页剪藏。Execution（shell 执行）明确不启用。设计见 [07](07-capability-activation.md) | ✅ 已确认 |

## 4. 里程碑总表

工期按业余时间（每周 10–15 小时）估算，总计约 **6–8 周**。

| 里程碑 | 内容 | 主要产出 | 验收标准 | 估算 |
|---|---|---|---|---|
| **M0 地基**（大部分已完成） | git 基线/双环境✅；补：初始化 `my-pkm` 项目实例、安装 Rust、前端 `pnpm i && tauri dev` 跑通、后端带凭据跑通一轮对话 | 可开发的全链路环境 | 前端能连后端对话；`pytest` 全绿 | 1–2 天 |
| **M1 knowledge 插件 + Obsidian 导入** | 插件骨架注册进 runtime；vault 解析（frontmatter/双链/标签）；checksum 增量索引；`km-ingest` CLI | `tinysoul/plugins/knowledge/`；5k 笔记导入 < 5 分钟 | 重复导入只处理变更文件；删除笔记产生 tombstone 而非硬删 | 1.5–2 周 |
| **M2 检索接入** | `SourceKind.knowledge` 注册；knowledge corpus（query/backlinks/directory）；`km.search` action + catalog/skills；embedding 配置 | 自然语言检索可用 | 评测集 hit@5 ≥ 基线；结果带 refs 分页 | 1–1.5 周 |
| **M3 聊天记录导入** | DeepSeek/ChatGLM 导出 → Markdown 条目；与 Session organize 联动（话题图可引用知识条目） | 聊天记录可检索 | 导入样本对话后相关内容可被搜到 | 0.5–1 周 |
| **M4 每日反思简版** | reflection.toml 每日策略；两阶段（当日消化摘要 → 知识卡片）；卡片入 knowledge store 可检索 | 每天自动产出 1–5 张卡片 | 连续跑 3 天；卡片带来源引用 | 1–1.5 周 |
| **M5 Tauri 前端改造** | 新增知识库 feature：检索页（高亮+refs 跳转）、卡片流、图谱视图、导入状态面板 | 可演示的桌面应用 | 全流程可演示：导入→检索→看卡片→看图谱 | 1.5–2 周 |
| **M6 评估与包装** | 50–100 题 QA 评测集；hit@k/MRR 报告；README 重写；demo 脚本 | 简历可用的量化叙事 | README 含指标表与截图；面试演示 ≤ 5 分钟 | 0.5–1 周 |

依赖关系：M1 → M2 →（M3、M4 可并行）→ M5 → M6。M0 与 M1 前半可穿插。

### 二期里程碑（能力启用，MVP 验收后启动）

按推荐顺序（可调），总工期约 5–7 周。每项的机制说明与功能设计见 [07-capability-activation.md](07-capability-activation.md)：

| 里程碑 | 内容 | 依托的闲置能力 | 估算 |
|---|---|---|---|
| E1 Zotero/文献接入 | MCP 直连 Zotero + markitdown 转 PDF，文献笔记入库 | Capabilities | 1–1.5 周 |
| E2 无人值守自动化 | SDK 深夜脚本（ingest + 反思授权）；评测 harness SDK 化（与 M6 合并推进） | SDK | 0.5 周 |
| E3 联网降级检索 + 知识勘误审计 | KB 严格优先分层；定期对撞自检产出"勘误报告" | 网络搜索 + Reflection | 1–1.5 周 |
| E4 深度整理 | Agent 内触发批量重建索引/补卡片，Job 承载进度 | Job + 导入双通道化 | 1 周 |
| E5 研究项目模式 | 主题 plan 跨轮推进，与盲区发现联动 | Workspace | 1.5–2 周 |
| E6 网页剪藏 | URL → 正文抽取 → 待确认笔记入库 | crawlee | 0.5–1 周 |

## 5. 子文档索引

| 文档 | 内容 |
|---|---|
| [01-architecture-and-decisions.md](01-architecture-and-decisions.md) | D1 完整论证（为何不用 ChromaDB）、knowledge 插件设计、与 memory 分工、改动白名单/黑名单 |
| [02-ingestion.md](02-ingestion.md) | Obsidian 适配器与聊天记录导入器：文件格式、增量索引、CLI |
| [03-retrieval.md](03-retrieval.md) | 检索源注册、`km.search` action、catalog/skills TOML、embedding 配置与调优 |
| [04-reflection-and-cards.md](04-reflection-and-cards.md) | 每日反思两阶段、知识卡片生成、二期盲区发现占位 |
| [05-tauri-frontend.md](05-tauri-frontend.md) | 前端现状盘点、页面规划、endpoint 对接、Rust 前置 |
| [06-testing-eval-and-packaging.md](06-testing-eval-and-packaging.md) | 测试策略、评测集与指标、README/简历叙事 |
| [07-capability-activation.md](07-capability-activation.md) | 二期能力启用：各闲置能力机制与功能设计（含网络优先级规则、知识勘误审计） |

## 6. 版本管理与"两版本不冲突"纪律

已就绪的骨架（D5）之外，开发期遵守：

1. **提交纪律**：每个里程碑至少一次结构化提交（`feat(km): ...`），简历项目的 commit 历史本身就是展示物。
2. **改动白名单**（允许触碰的既有文件，全部有明确理由）：
   - `tinysoul/agent/composition/builder.py` — `_standard_plugins()` 注册行 + `references.bind` 增加 `km` 端口 + `_validate_selected_models` 增加 knowledge 的 embedding owner 映射（共三处，均在装配关键路径上）；
   - `tinysoul/gateway/cli.py` — 加 `km-ingest` 子命令；
   - `tinysoul/infra/config/catalog/context.toml` — 新增 `knowledge.*` 配置描述条目（上游契约：打包 TOML 叶子必须有 catalog 覆盖，否则 `test_config_catalog` 失败）；
   - `tinysoul/kernel/retrieval/policy.py` — `retrieval_schema()` 模型可见 schema 摊平（去掉嵌套 oneOf；`parse_retrieval_request` 仍是权威语法，上游测试全过）。动机：弱模型（glm-4.5-flash）会把嵌套 oneOf 的 source 对象序列化成 JSON 字符串，检索调用全部失败。
   - 其余一律走新增文件或项目侧配置。白名单变更需先在本文件登记。
3. **改动黑名单**（不触碰）：`kernel` 其余部分、`agent` 装配核心、Session 格式、endpoint 协议既有消息、`prompts/`（身份/人格走项目 Home 内容，不走 prompts）。
4. **上游同步**：上游更新时 `git switch main && git merge upstream/main`，跑 `pytest`，再 `git switch pkm && git merge main`。冲突预期集中在白名单四处。
5. **数据隔离**：PKM 项目实例 `my-pkm` 独立初始化，不复用 `my-agent` 数据；`reset` 不当迁移工具用（上游 README 明确）。

## 7. 风险登记

| 风险 | 影响 | 缓解 |
|---|---|---|
| 上游仍在大重构（近七轮重构均在动检索/装配） | 合并冲突 | 改动面压到白名单四处；新增文件为主；每里程碑结束即合并一次上游 |
| Rust 工具链首次安装/Tauri 编译失败 | 阻塞 M5 | M0 提前装；失败则 M5 降级为"浏览器访问 Vite dev 页 + FastAPI endpoint"过渡方案 |
| embedding 依赖外部 API（费用/断网） | M2/M4 | 配置层支持本地 onnx 模型切换（`infra/model_services.toml`），评测时记录两种模式 |
| Obsidian 方言（Dataview/插件语法）解析不完整 | 导入质量 | 尽力解析 + 未识别语法原样保留；验收只要求常规 frontmatter/双链/标签 |
| 评测集主观性 | 指标可信度 | 评测集构建与校对流程写进 06 文档，人工复核比例 ≥ 80% |
| 联网检索污染答案域 | KM 可信度 | 严格 KB 优先分层（07 §4.1）；网络内容永不与 KB 平权合并；来源强制标注 |
| 勘误审计误报 / 成本失控 | 用户信任、API 费用 | 只查可验证事实性陈述、每轮限额、无法判定不进报告（07 §4.2） |
