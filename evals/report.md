# TinySoul-KM 评测报告

> 日期：2026-10-12 ｜ 分支 `pkm` ｜ 环境：conda `TinySoul-PKM`（Python 3.13）
> 复现：`python evals/run_eval.py --root my-pkm --vault <vault> --qa evals/qa_set.jsonl`

## 1. 检索质量（词法基线，60 题）

| 指标 | 值 |
|---|---|
| hit@1 | **0.717** |
| hit@5 | **0.917** |
| hit@10 | **0.950** |
| MRR | **0.822** |

分题型：

| 题型 | 命中 | 说明 |
|---|---|---|
| fact（单文档事实，40 题） | 38/40 | 两例 MISS 为查询词未出现在目标文档（中文问句 + 停用词主导） |
| synthesis（跨文档综合，15 题） | 15/15 | 题面含目标文档词形；不含目标词的纯语义综合题依赖向量路（见 §4） |
| holdout（防泄漏对照，5 题） | 5/5 | 与调优集同分布，验证无过拟合 |

评测集：`evals/qa_set.jsonl`，基于程序化生成 vault（5000 笔记，主题/双链/标签已知，ground truth 精确到文档路径）。真实个人笔记题目随数据接入滚动补充（06 文档：人工复核 ≥ 80% 适用于真实数据题）。

## 2. 导入性能（5000 笔记合成 vault）

| 场景 | 耗时 | 验收线 |
|---|---|---|
| 全量导入（含解析/frontmatter 合并/索引） | **19.3 s** | < 5 min ✅ |
| 重复导入（mtime+size 预筛，全 unchanged） | **0.5 s** | < 10 s ✅ |
| 修改后增量导入 | 单文件级（checksum 二级判） | — |

删除行为：tombstone 审计（`tombstones.jsonl`），store 文件保留；重命名/恢复通过 checksum 归并稳定 `km_id`（单测覆盖四分支）。

## 3. 检索延迟（5000 笔记，corpus 候选缓存后）

| 指标 | 值 | 验收线 |
|---|---|---|
| warm p50 | **60 ms** | < 2 s ✅ |
| warm p95 | **81 ms** | < 2 s ✅ |
| 冷启动（首次物化候选集） | 2.0 s | 一次性 |

端到端（含内核词法排序 + 分页）实测同一量级；rerank 模型步骤不计入（验收口径"不含模型 rerank"）。

## 4. 配置消融：embedding 通道

- **词法 only**（本报告全部数字）：glm 无 LLM 参与，确定性可复现。
- **词法 + 向量（embedding-3）**：管路已就绪（`km.search` 已声明 embedding 通道、`EmbeddingIndex` 已装配、rerank 已绑 `embedding_similarity`；结果 payload 的 `missing_stages` 可观测通道缺失），但 bigmodel embedding-3 返回 429"余额不足"、ARK key 无效——**待有余额凭据后按同集复测**，预期改善纯语义综合题与中文停用词主导的 fact 题。
- 本地 onnx 模型：runtime 未内置本地 embedding adapter（`model_services` 仅 openai 兼容 API adapter），为二期能力。

## 5. 失败案例与已知限制

1. **免费模型 tool-calling 质量**：glm-4.5-flash 对嵌套 oneOf schema 会把参数序列化成 JSON 字符串（上游 `memory.search` 等同样受影响）。已在 `retrieval_schema()` 摊平模型可见 schema 解决；残余 ~1/10 概率的字符串化调用由失败反馈自愈重试。
2. **反思轮稳定性**：flash 驱动的 Memory Reflection Turn 偶发在 core.answer 中传 km: refs（core 的 reference resolver 仅注册 workspace 前缀）循环重试至预算耗尽；卡片生成主链路不受影响（Day 1 真机验证通过）。
3. **合成 vault 局限**：评测集题目词形与 ground truth 已知，真实笔记的模糊查询/拼写变体未覆盖；真实题补充后本表更新。

## 6. 端到端演示记录（2026-10-12）

- 导入→检索：CLI 导入 5000 笔记 + 3 个聊天会话；对话"用 km.search 检索 transformer"返回真实 `km:` refs（Note 48/248/448）。
- 卡片：Memory Reflection Turn 生成 `cards/2026-10-12.md`（2 卡，来源引用真实聊天条目，伪造引用被类型化拒绝）。
- 卡片可检索：`km.search "RRF 融合"` 命中 `km:card-41c9e73cb1c5`（source=card）。
- 前端：Tauri 桌面端 Knowledge 页（检索/卡片流/图谱/导入）。
