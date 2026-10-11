# TinySoul-KM 进度日志

> 本文件是长会话中唯一的进度事实源。每个里程碑完成时更新：完成项 / 偏差 / 遗留。
> 约定：日期 2026-xx-xx；分支 `pkm`；开发环境 conda `TinySoul-PKM`；项目实例 `D:\ProgramData\RESUME\my-pkm`。

## 状态总览

| 里程碑 | 状态 | 提交 |
|---|---|---|
| M0 地基 | ✅ 完成 | `docs(km)` / `chore(km)` |
| M1 插件+导入 | ✅ 完成 | `feat(km): M1 knowledge 插件骨架与 Obsidian 增量导入` |
| M2 检索 | ✅ 完成 | `feat(km): M2 km.search 混合检索接入内核管道` |
| M3 聊天导入 | ⬜ 未开始 | |
| M4 每日反思 | ⬜ 未开始 | |
| M5 前端 | ⬜ 未开始 | |
| M6 评估包装 | ⬜ 未开始 | |

## M0 地基（2026-10-11）

完成项：

- [x] `docs/pkm` 8 份计划文档入库并提交（`docs(km): M0 PKM 计划文档入库`）。
- [x] `tinysoul init --config-profile standard my-pkm`（位于 `D:\ProgramData\RESUME\my-pkm`，与 my-agent 数据隔离）。
- [x] my-pkm 配置：`configs/llm/models/custom.toml` 定义 `glm_4_5_flash`；`tasks.toml` 三任务绑定该模型；`providers.toml` 启用 glm provider；`configs/infra/model_services.toml` 启用 bigmodel embedding（embedding-3，1024 维）；`.env` 含 `GLM_API_KEY` / `ARK_API_KEY` / `GLM_EMBEDDING_API_KEY`。
- [x] 后端带凭据跑通一轮对话：`tinysoul start --root . --once "你好…"` 正常回复。
- [x] pytest 全量基线：`747 passed, 1 failed`（详见下"偏差 4"），唯一失败为上游自带的环境依赖测试。
- [x] Rust 工具链：rustup 1.99.0 stable（rustc 1.99.0，位于 `D:\Program Files (x86)\rust\cargo\bin`，MSVC host）。
- [x] 前端跑通：`pnpm tauri dev` 首次编译 3m30s 成功，桌面窗口启动；后端 endpoint（127.0.0.1:57136，协议 v2）以实例记录 token 握手 `/v2/status` 返回 `ready:true`，前端-后端连接链路验证通过。

偏差（设计文档 vs 实际环境）：

1. `tinysoul init` 默认 tasks 绑定的模型（gpt_5_6_terra/deepseek_flash/kimi 等）在本机无凭据，按 my-agent 已验证可行方案改为 `glm_4_5_flash`（bigmodel 免费额度模型）。
2. 直接复制 my-agent 的 custom.toml 会引入 `doubao_seed`（引用未在本项目定义的 ark provider）导致装配失败 `Model references unknown provider`，已裁剪只留 glm_4_5_flash。
3. conda `TinySoul-PKM` 激活脚本把 `SSL_CERT_FILE` 指到 `<env>/ssl/cacert.pem`（不存在，实际在 `<env>/Library/ssl/cacert.pem`），首次 HTTPS 调用报 FileNotFoundError；已把 cacert.pem 复制到 `<env>/ssl/` 修复。**新终端跑 tinysoul 前若复现，重做该复制即可。**
4. pytest 基线唯一失败：`tests/plugins/capabilities/expand/test_engine.py::test_real_sdk_streamable_http_discovery_and_call`（真实 HTTP 探测返回 `unavailable`，期望 `available`）——上游自带测试、依赖本机外网/服务可用性，与本次改动无关，登记为基线已知失败。此后的"全量 pytest 绿"按"除该用例外全绿"口径执行。

遗留：无。

## M1 knowledge 插件 + Obsidian 导入（2026-10-11）

完成项（对照 02 文档 §5 验收表）：

- [x] 插件 `tinysoul/plugins/knowledge/`：plugin/config/engine/failures/runtime_bridge/storage(store+index)/ingest(obsidian)；`KnowledgePlugin` 注册进 `_standard_plugins()`（builder.py 白名单行）。
- [x] `tinysoul km-ingest --root <proj> --obsidian <vault> [--dry-run] [--full]`（cli.py 白名单改动；Windows 控制台输出已做 errors=replace 兜底）。
- [x] 性能：5k 笔记全量导入 **19.3s**（验收 <5min）；重复导入 **0.5s**（验收 <10s，mtime+size 预筛 + checksum 二级判）。
- [x] 增量四分支单测：新增/修改（km_id 按路径稳定）/删除（tombstone，store 文件保留，tombstones.jsonl 审计）/重命名（checksum 归并 km_id）；已删除笔记恢复可复活。
- [x] km_links/km_tags 抽检 20 篇（5k 基准 vault）：40/40 = **100%**（验收 ≥95%）。
- [x] `--dry-run` 输出与实际执行一致（单测断言三个列表相等，且 dry-run 不落盘）。
- [x] 解析器单测含畸形 frontmatter 降级、围栏内标签跳过、标题行不误判、CRLF/BOM 归一。
- [x] 全量 pytest 绿（基线口径：仅剩 M0 登记的 expand 环境依赖失败）。
- [x] 装配验证：my-pkm（含新插件）`tinysoul start --once` 对话正常。

偏差（登记进 00-master-plan §6.2 白名单）：

1. **`SourceKind` 实际位于 `kernel/retrieval/contracts.py`**（非总纲所写 policy.py），M2 改动点以代码为准。
2. **新增白名单第 5 处：`tinysoul/infra/config/catalog/context.toml`**。上游有"每个打包项目 TOML 叶子必须在 config catalog 登记"的契约测试；新增资产 `assets/common/configs/knowledge.toml` 后必须补 `knowledge.*` 字段描述（纯数据，7 个 field + 4 个 field_group + 1 个 surface）。initializer.py 本身无需改动（资产遍历是数据驱动的）。
3. 验收用基准 vault 为程序生成的 5k 笔记（真实个人 vault 待用户侧数据）。

遗留：

- 向量化尚未接入（M2）；`km.search`/cards/chats 未开始（M2/M3/M4）。

## M2 检索接入（2026-10-12）

完成项（对照 03 文档 §6 验收表）：

- [x] `km.search` 在 Agent 对话中可被模型选择并正确返回（带 refs、分页 continuation）：真实对话闭环验证——模型选中 km 域 → 调用 km.search → 返回 625 候选/词法证据/分页令牌 → 答案引用真实 `km:` refs（Note 48/248/448 等）。
- [x] 反链来自真实 `km_links` 边：单测覆盖（悬空链接不产生反链、无链接文档无反链）。
- [x] 评测集 `evals/qa_set.jsonl` 60 题（40 fact + 15 synthesis + 5 holdout）+ `evals/run_eval.py` harness；词法基线：**hit@1=0.717 / hit@5=0.917 / hit@10=0.950 / MRR=0.822**。
- [x] 5k 笔记检索延迟：corpus 候选缓存后 warm **p50=60ms / p95=81ms**（验收 <2s；冷启动一次 2.0s）。
- [x] 词法路/向量路可观测：结果 payload 带 `stages` / `missing_stages`。
- [x] 全量 pytest 绿（基线口径）。

架构要点（与设计文档的差异，以代码为准）：

1. **不需要 `SourceKind.knowledge`**（contracts.py 已回退）：来源形状（query/backlinks/directory/refs/result）是跨 owner 的通用词表，knowledge 的"来源"由 `km.search` 的 capability + catalog + corpus 表达。给枚举加值会污染所有既有 action 的模型可见 schema 并破坏 capability 校验（实测）。
2. **catalog 域名必须叫 `km`**：上游强制 action 名 `<domain>.` 命名空间（`km.search` ∈ domain km），03 文档所写 domain "knowledge" 不合法。
3. **retrieval_schema 摊平（policy.py 白名单内，重要）**：原 schema 的 `source` 是嵌套 oneOf，glm-4.5-flash 会把嵌套对象序列化成 JSON 字符串导致全部调用失败。摊平为单层对象提示后模型调用 100% 成形；严格语义仍由 `parse_retrieval_request` 独立把关（上游测试全部通过）。
4. **builder.py 三处接线**：插件注册、`references.bind` 加 `km` 端口、`_validate_selected_models` 加 `km` embedding owner 映射（已登记总纲 §6.2）。
5. 快照预算：5k 全库查询超默认 4MB 快照，km.search 策略 `snapshot_max_chars=16000000`。

遗留 / 阻塞：

- **向量通道未激活**：bigmodel embedding-3 返回 429"余额不足"（免费 key 只覆盖 glm-4.5-flash），ARK key 无效。管路已就绪（channels 已声明 embedding、EmbeddingIndex 已装配、rerank 已绑 embedding_similarity），换有余额的 embedding key 或本地 onnx 模型即生效。`hit@5 ≥ 词法基线+5pt` 的向量验收顺延至凭据可用。
- glm-4.5-flash 偶发仍把 source 序列化为字符串（约 1/10 次调用），失败反馈可自愈重试；属免费模型 tool-calling 质量问题。
- 评测集当前基于合成 vault；真实笔记题目待用户数据接入后滚动补充（人工复核 ≥80% 要求适用于真实题）。

## 附录：环境事实

- 开发：conda `TinySoul-PKM`（Python 3.13.x，可编辑安装 tinysoul）；原版对照：conda `TinySoul`。
- Node 24.11.1 + pnpm 12.10.1 已有；MSVC Build Tools 2022（VC 14.44）已装。
- my-pkm 路径：`D:\ProgramData\RESUME\my-pkm`。
