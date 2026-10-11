# 测试、评估与简历包装

> 状态：草案 v1 ｜ 里程碑：M6（评测集构建从 M2 起滚动进行）｜ 依赖：全部前序文档

## 1. 测试策略

| 层 | 工具 | 覆盖 |
|---|---|---|
| 单元 | pytest（已是 dev 依赖） | frontmatter/双链/标签解析（含畸形输入）、checksum 增量四分支（新增/修改/删除/重命名）、聊天导出适配器、卡片 schema 校验、`source_refs` 真实性校验 |
| 装配 | pytest + pytest-asyncio | knowledge 插件装配（`Agent.create` 后 services 可取）、executor 注册与 catalog 校验（坏 catalog 必须装配失败）、`SourceKind.knowledge` 检索管道解析 |
| 架构约束 | 参照 `tests/test_architecture.py` 现有做法 | 新插件不违反依赖方向（plugins 不得反向 import agent/gateway 内部等） |
| E2E | Playwright（前端既有） | 检索→抽屉→refs 跳转；卡片流渲染；导入面板 dry-run |
| 回退性 | pytest | 关闭 knowledge 配置后，行为与 `upstream-baseline` 一致（配置开关验收） |

测试放在 `tests/km/`（新增目录，避免与上游测试目录合并冲突）。**每个里程碑完成即跑全量 pytest**，这同时是上游合并前的回归闸门。

## 2. 评测集与指标（简历的量化核心）

### 2.1 QA 评测集（50–100 题）

构建流程（写进 README 方法论，体现严谨性）：

1. 从你的真实笔记抽 30 篇 + 导出会话抽 10 段，每篇/段出 1–2 题（问"内容里的事实"，不问观点）；
2. 另造 20 题**需要跨文档综合**的题（A 文的结论 + B 文的前提）——这是混合检索与卡片价值的体现；
3. 每题标注：标准答案要点、来源文档与段落（`km_id#pN`）、题型（事实/综合/时间敏感）；
4. 人工复核 ≥ 80%（抽同事/朋友盲答一轮校准难度）；留 10 题 never-touch 作防泄漏对照。

存 `evals/qa_set.jsonl`（不进公开仓库的版本另存）。

### 2.2 指标与报告

- 检索：**hit@5 / hit@10 / MRR**（来源段落命中即算 hit）；
- 端到端问答：答案要点覆盖率（LLM-as-judge + 人工抽检 20%）；
- 性能：5k 笔记导入耗时、增量导入耗时、检索 P95；
- 消融（加分项）：词法 only / 向量 only / 融合 / 融合+rerank 四行对比表；
- 配置消融：bigmodel embedding-3 vs 本地 onnx。

产出 `evals/report.md`：方法、数字表、失败案例分析（README 引用此表）。跑分 harness 用 SDK 批量执行（[07](07-capability-activation.md) §E2），一键复现。

## 3. README 重写（简历项目的门面）

结构：

1. **一句话 + 截图/GIF**（检索页与图谱视图，M5 后录制）；
2. 架构图（复用 01 文档 §5 数据流图 + 前端结构）；
3. 亮点条目（对应下 §4）；
4. 快速开始（clone → conda env → init → ingest → tauri dev，**≤ 5 条命令**）；
5. 评测指标表（引自 evals/report.md）；
6. 与上游的关系声明（基于 TinySoul-Agent，列出改动白名单，致谢上游 MIT 协议）；
7. 二期路线（能力启用计划：文献接入、联网降级检索与知识勘误审计、研究项目等，见 `docs/pkm/07-capability-activation.md`）。

## 4. 简历/面试叙事点（每条都有代码与数字背书）

| 叙事 | 背书物 |
|---|---|
| 在约束严格的 Agent 运行时中按 owner/插件协议扩展知识存储 owner，保持上游可合并 | 插件目录 + 白名单仅 4 处 + git 历史 |
| 词法+向量混合检索（RRF 融合、可配置权重），hit@5 从词法基线提升 X pt | evals/report.md 消融表 |
| 复用 Reflection Turn 内核实现每日主动整理：自动生成带强制来源引用的知识卡片，伪造引用被类型化拒绝 | actions/card.py 校验 + 连续 3 天运行记录 |
| 增量导入：5k 笔记全量 < 5 min，重复导入 < 10 s，删除可追溯（tombstone） | 性能数字 + 单测 |
| Tauri 2 + React 19 桌面端：检索高亮、卡片流、知识图谱可视化 | 截图 + E2E |

面试必问题预答（写进 README FAQ 或个人备忘）："为什么不用 ChromaDB/LangChain？"→ 01 文档 §2 六条；"和 Obsidian 自带搜索差别？"→ 语义综合、跨文档、卡片、每日主动整理；"数据隐私？"→ 全本地存储、embedding 可切本地模型。

## 5. 发布与演示

- GitHub 公开仓（剥离真实笔记数据与密钥；`.env` 已在 .gitignore）；
- Demo 脚本（≤ 5 分钟）：`km-ingest --dry-run` 展示增量 → 对话检索一个跨文档问题 → 打开卡片流 → 图谱视图一跳邻域 → 评测表收尾；
- 可选：Tauri bundle 出 Windows 安装包（`pnpm tauri build`），README 放 release 链接。

## 6. 时间线对账

评测集构建（§2.1 的 1–3 步）在 M2 期间滚动完成（约 2 个业余晚上），不占 M6 整块时间；M6 剩余工作 = 跑评测 + 写报告 + README + 录屏，约 3–5 个晚上。总工期 6–8 周的估算成立。
