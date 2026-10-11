# 二期能力启用计划：闲置能力 → 功能（E1–E6）

> 状态：草案 v1（决策 D6 已确认）｜ 时机：MVP（M0–M6）验收后启动 ｜ 依赖：[00](00-master-plan.md)、[01](01-architecture-and-decisions.md)、[04](04-reflection-and-cards.md)
> 总则：**功能倒逼能力，不是能力找功能**——以下 6 项均以产品价值与简历叙事立项；启用方式 = 挂载 + 配置 + 插件内 executor，不做内核手术。Execution（shell 执行）经评估**明确不启用**（动操作系统的能力与"不碰用户原始数据"红线冲突）。
> 纪律延续：任何 E 里程碑新增的 runtime 触碰点，必须先登记进 [00 §6.2 白名单](00-master-plan.md)。

## E1 Zotero/文献接入（Capabilities + markitdown）

**依托能力**：capabilities 插件 = MCP/ACP 外部工具标准通道（`mcp 2.2.0`、`agent-client-protocol 0.12.1` 已在 `external-tools` extra 中）；工具目录 + profile 授予（`configs/capabilities/`），模型经统一协议调用。

**功能设计**：
1. 部署 Zotero MCP server（社区实现），项目 `configs/capabilities/` 授予"检索文献/读元数据/取附件"三类工具；
2. domain skill 增补指引：何时该查 Zotero（引用溯源、找原文）而非 km.search；
3. markitdown 把 PDF 附件转 Markdown → 走既有 ingest 管道入库（`km_source: zotero`，frontmatter 记 DOI/年份/作者）。

**改动面**：项目侧为主；knowledge 的 ingest 增加一个 zotero 适配器（小）。**零内核改动。**
**验收**：文献可检索、引用可跳回 Zotero 条目；10 篇 PDF 文献入库并参与混合检索。

## E2 SDK：无人值守自动化 + 评测 harness

**依托能力**：SDK（`agent/sdk.py:97`）——`Agent.create / submit_turn / handle.wait`、`ReflectionRequest` 显式授权一次反思 Turn、配置 PATCH + reload；无终端无 HTTP。

**功能 A 无人值守晨间流水线**：Windows 任务计划深夜执行 SDK 脚本——
```
km-ingest 增量导入 → ReflectionRequest（知识反思：消化 + 卡片）
→ （E3 后追加）km.audit 勘误审计 → 生成晨报（昨日变更/新卡片/审计结果摘要）
```
全程无界面，早上打开前端看结果。

**功能 B 评测 harness SDK 化**：[06 文档](06-testing-eval-and-packaging.md)的 QA 评测集用 SDK 批量执行（逐题 submit_turn、收集 refs 命中、算 hit@k/MRR），`python evals/run.py --set qa_set.jsonl` 一键复现。**此项从 E2 提前挂到 M6**——M6 本来就要跑评测。

**改动面**：零内核；新增 `evals/run.py` + `scripts/morning.py`。
**验收**：连续 7 天无人值守流水线成功；评测一键跑出报告。

## E3 联网降级检索 + 知识勘误审计（本里程碑含两条用户指定的硬规则）

**依托能力**：开发 profile 的 Kimi 网络搜索能力（provider 适配层）+ Reflection Turn（知识反思情景）。

### 4.1 硬规则一：知识库严格优先于网络（分层答案合成）

| 层 | 内容 | 语义 |
|---|---|---|
| **L1 用户知识库** | `km.search` + `memory.search` | **唯一权威层**，答案默认只从 L1 合成 |
| **L2 网络搜索** | Kimi search | **仅当 L1 置信不足/空结果时启用**（触发条件写入 domain skill；km.search 结果携带置信信号供 Phase1 判断） |
| **L3 网络内容处置** | 搜索命中的外部内容 | 回答必须标注"来自网络 + 来源链接"；如需留存，以**待确认笔记**入库（`km_source: web` + `needs_review: true`），**永不与 L1 平权合并，不进入卡片生成语料** |

**冲突语义**：L1 与 L2 矛盾时，答案以 L1 为准、同时明示差异，矛盾对自动进入勘误队列（§4.2）——网络永远不"纠正"知识库，只"提示"。
**实现**：默认关闭，E3 打开；配置授予 + skill 指引为主，`km.search` 加置信信号输出（插件内小改）。

### 4.2 硬规则二：知识勘误审计（自检，防错误长期潜伏）

**定位**：发现"一直没被发现的错误"，产出**勘误报告**交用户裁决——**绝不自动修改 vault 原文**（产品红线）。

- **审计对象**（四类，成本递减）：`km_review: time-sensitive` 标记的笔记/卡片 → memory 的 fact 类文档 → 高置信度卡片抽样 → 用户指定范围；
- **选样启发式**：只挑可验证的事实性陈述（数字/日期/版本号/比较级断言），每轮限额默认 10 条，杜绝全库扫荡；
- **对撞流程**：Reflection Turn 选样 → 网络查证（强制来源引用）→ LLM 对撞判定，三值输出：**支持 / 矛盾 / 无法判定**（无法判定不进报告，防噪音）→ 报告写入 `knowledge/audits/YYYY-WW.md`（矛盾清单 + 双方证据链接 + 建议动作）；
- **裁决后动作**：卡片降 confidence 或标 `outdated`（knowledge store 侧，可逆）；若问题出在 vault 原文 → 生成**修改建议补丁文件**，用户自己决定是否应用；
- **入口**：晨间流水线每周触发一次（E2），也可在前端手动触发。

**验收**：预埋 3 条故意过时陈述（如旧版本号/已变更的事实），一周内审计命中 ≥ 2；误报率 < 30%；每轮 API 成本有记录上限。

## E4 深度整理（Job）

**依托能力**：Job = 单 Turn 内跨 Cycle 后台工作（`kernel/jobs` 监督），启动/检查/回应/等待/停止是独立 Action，Turn 收束强制收集。

**启用前提——导入双通道化**：把 ingest 核心（解析 + 索引 + 向量化）封装为 Agent 内 action（`km.reindex`、`km.bulk_cards`），CLI 保留不动。这是本项的主要工作量。

**功能设计**：对话或前端发起"对某目录/某时间段深度整理"→ 启动 Job → 你继续干别的 → 进度随时查 → 完成出摘要。5k 文档级别的重建不再要求你守着命令行。

**改动面**：knowledge 插件 `requires` 增加 `JobRegistry`，插件内新增 2 个 action；中等。
**验收**：重建期间对话不阻塞、进度可见、Turn 结束 Job 正确回收（不泄漏后台资源）。

## E5 研究项目模式（Workspace）

**依托能力**：Working 语境段承载 plan 的 milestones/todos 投影；`workspace.inspect` 提供资源有界页。

**功能设计**：针对学习主题建研究 plan（要读哪些笔记、补哪些概念、生成哪些卡片），Agent 跨多轮按计划推进，前端实时看进度。与[盲区发现](04-reflection-and-cards.md)联动：**盲区清单 → 自动起草研究 plan → 跨轮推进补齐**，形成"发现薄弱 → 主动学习"闭环——这是全项目简历叙事的天花板功能。

**改动面**：knowledge 插件 `requires` 增加 `WorkspaceService`；优先复用 workspace 既有 action + skill 指引，不足再补插件内 action；中大。
**验收**：一个真实主题从盲区到 plan 到卡片的全闭环；进度投影在前端可见。

## E6 网页剪藏（crawlee）

**依托能力**：crawlee（`web-crawl` extra，已就位）+ trafilatura（已是基础依赖）。

**功能设计**：URL（单条或列表）→ 正文抽取 → 规范化为 `km_source: web` 笔记 → 既有索引。遵循 §4.1 的 L3 语义：**剪藏默认进"待确认"**，经勘误审计（或你手动确认）后才转正进入卡片语料——保证"网络来客"不污染权威层。

**改动面**：ingest 增加网页适配器；小。
**验收**：批量剪藏 20 篇文章入库可检索；未确认内容不出现在卡片来源中。

## 建议执行顺序

**E1 → E2 → E3 → E4 → E5 → E6**。理由：E1 数据源价值最高且几乎纯配置；E2 白拿且服务 M6；E3 是你指定的核心差异化（两条硬规则）；E4/E5 依赖前面地基；E6 最轻收尾。E5 与盲区发现的联动设计建议在 E3 完成后做一次联合评审再动手。

二期总工期约 **5–7 周**（业余时间）。全部完成后，"闲置能力"清单中除 Execution 外全部转化为用户可见功能，且每项都有独立验收标准——这本身构成简历项目第二阶段的量化叙事。
