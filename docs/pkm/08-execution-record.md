# TinySoul-KM 执行文档（工作区归档收编）

> 状态：**待确认，未执行** ｜ 日期：2026-10-13
> 本文是唯一的执行依据：第一部分压缩整理全部已完成能力，第二部分是待实施特性的设计与任务清单。
> 01–07 号文档保留为设计论证历史；与实施不符之处一律以本文为准。

---

## 第一部分：已完成能力压缩记录（M0–M6 + 修复）

### 存储与插件（M1/M2/M3）

- **knowledge 插件**（`tinysoul/plugins/knowledge/`）：Markdown 原生存储，四类根目录 `notes/ chats/ cards/` + 派生索引 `index.json` + tombstone 审计 `tombstones.jsonl`。
- **km-ingest CLI**：vault 目录（checksum 增量：全量 19.3s / 重复 0.5s / 5k 笔记）与聊天导出（JSON/MD/HTML，>20 轮切分）。
- **km.search**：复用内核检索管道（query/backlinks/directory/refs + filter/select/rerank + 分页），真实 `km_links` 反链；`retrieval_schema()` 已摊平（弱模型 tool-calling 兼容）。
- **评测基线**：60 题词法 hit@5=0.917 / MRR=0.822；检索 warm p95=81ms。
- **前端**：Tauri 桌面端 KM 页（检索/卡片流/图谱邻域浏览器/导入面板），卡片来源可点开原文抽屉。

### 每日反思与卡片（M4）

- `km.generate_card`（仅 memory_reflection 情景）：当日导入文档 ≤12 篇 → LLM 结构化卡片 → **source_refs 逐一校验，伪造即类型化拒绝** → 追加 `cards/<日>.md`（frontmatter `km_source: card`，`km_links` 带来源标题供反链）。
- 频控 `daily_card_limit=5`；`enabled=false` 时无副作用。
- 配置：`configs/knowledge.toml`（reflection.enabled / daily_card_limit / search.embedding_use）。

### 自动化与审查

- **打开程序自动补跑**：KM 页横幅读 `GET /v2/reflection` 的 `missing_daily_days`，发现缺口**无需点击**自动逐日提交补跑（每会话每日一次防重复，失败退化为手动按钮）。`POST /v2/reflection` kind=memory target_day。
- 按用户决定**移除**了计划任务自启动方案——软件不静默注册系统计划任务。后端由用户手动启动（`tinysoul start --root my-pkm`）。

### 已登记的上游稳定性问题（未修，属上游）

1. 反思轮打满 max_cycles 进入预算等待后，后端可能无输出退出（exit 1）；
2. endpoint 客户端 abrupt 断连可致 `ConnectionResetError` 带崩后端 CLI。
   缓解：重开即可；缺口由打开程序时的自动补跑兜底。

### 最终白名单（源码改动清单）

| 文件 | 改动 |
|---|---|
| `agent/composition/builder.py` | 插件注册行、`references.bind` km 端口、embedding owner 映射 |
| `kernel/retrieval/policy.py` | 检索 schema 摊平（parser 仍是权威语法） |
| `gateway/cli.py` | `km-ingest` 子命令 |
| `infra/config/catalog/context.toml` | `knowledge.*` 配置描述条目 |
| `README.md` | M6 重写 |

---

## 第二部分：待实施特性——工作区归档收编（本次执行范围）

### 背景与目标

用户拖文件进**工作区**（Agent 当天的草稿台，跨天归档），原流程下这些文件进不了知识库、出不了卡片。本特性把流程收敛为：

```
拖文件进工作区（唯一入口，当天 Agent 可用）
  → 夜里跨天，内核归档工作区（上游已有机制，不动）
  → 归档收编：archive/*/workspace/**/*.md 进知识库（km_source=workspace，imported_on=归档日）
  → 每日反思：出知识卡片 + LLM 深度标注写回文档
  → 超期归档清理：已收编且超过保留期的归档工作区文件删除（可配置，默认 30 天）
```

### 已确认的设计决策

| # | 决策 |
|---|---|
| D-1 | **LLM 深度标注并进每日反思**（不在归档前单独调用）：反思轮为每篇新文档输出知识类型/主题/一句话摘要，写回 frontmatter（`km_type` / `km_topics` / `km_summary`）；失败的文档次日反思可再处理 |
| D-2 | **超期归档清理可配置**：设置项 `retention_days`（用户可选，**默认 30 天**，0=禁用）；只清理"已收编"的归档工作区文件，session/memory 快照永不触碰 |
| D-3 | **过档即定稿**：不做知识库→归档的反向回写；跨天后改稿走"知识库内新修订版"，二期实现 |

### 设计要点

1. **存储**：知识库新增第四个根目录 `knowledge/workspace/`；`read_document` 按 `km_source=workspace` 分发；文件命名 `<归档日>/<原相对路径>`。
2. **收编算法**（`KnowledgeEngine.ingest_workspace_archive()`）：扫 `archive/*/workspace/**/*.md` → normalize → checksum → **幂等**（未变即跳过）→ 解析（frontmatter/双链/标签，复用现有解析器）→ 合并 `km_*` frontmatter → 写入 + 索引。`imported_on` 取**归档日**（目录名前 8 位），保证 target_day 反思把它们当同日候选。
3. **时序**：上游保证跨天时先归档、00:15 反思后跑；卡片执行器挑候选**之前**先调收编（幂等兜底，与归档时序解耦）。
4. **清理**（`cleanup_expired_archives()`）：逐个归档日目录，超期且 checksum 已在知识库（live）中的 workspace 文件删除，未收编的保留；空目录回收；`retention_days <= 0` 禁用。清理在反思轮收编之后执行。session/memory 快照永不触碰。
5. **检索维度**：`km.search` capability scopes 增加 `workspace`；文档 `source=workspace` 自然进入 where 过滤与属性投影。
6. **元数据**：收编时提取廉价元数据（标题/标签/双链）；`km_type`/`km_topics`/`km_summary` 由反思轮 LLM 标注（D-1），卡片 prompt 扩展要求顺带输出。
7. **前端**：`SOURCE_COLORS` 增加 workspace（绿色系），图谱/卡片来源芯片同步。

### 实现清单（确认后执行）

| # | 任务 | 文件 | 规模 |
|---|---|---|---|
| T1 | store：`workspace_root` 属性 + `write_workspace` + `read_document` 分发 | `storage/store.py` | ~20 行 |
| T2 | config：`[knowledge.archive]`（archive_root 可选、retention_days 默认 30，0=禁用） | `config.py` | ~50 行 |
| T3 | engine：`ingest_workspace_archive()` + `cleanup_expired_archives()` | `engine.py` | ~150 行 |
| T4 | 执行器：候选选择前调收编，随后调清理 | `actions/card.py` | ~10 行 |
| T5 | capability scopes + skills 文案加 workspace | `plugin.py` / skills 资产 | ~5 行 |
| T6 | 前端：SOURCE_COLORS 加 workspace（绿色） | `features/km/KmPage.tsx` | ~3 行 |
| T7 | 测试：收编幂等/归档日标注/清理保留未收编文件/清理禁用 | `tests/km/test_workspace_ingest.py` | ~120 行 |
| T8 | 设置值暴露：`configs/knowledge.toml` 支持 `[knowledge.archive] retention_days=30`（用户项目侧直接改；前端设置编辑器列二期） | 用户项目侧 | 文档 |

### 验收标准

- [ ] 拖入工作区的 .md 在跨天归档后，无需手动导入即被收编（`km_source=workspace`，`imported_on=归档日`）；
- [ ] 重复收编幂等（unchanged 计数正确，实测重复 0 写入）；
- [ ] 超期清理：仅删除"已收编且超期"的归档 workspace 文件；未收编文件与 session/memory 快照保留；`retention_days=0` 时完全不清理；
- [ ] 12 号归档里的《2026-09-07-如何让大模型为你所用.md》经收编 + 12 号补反思后生成卡片，来源引用指向它；
- [ ] `km.search` 可用 `where: {source: workspace}` 过滤；前端图谱/来源芯片有 workspace 颜色；
- [ ] `km_type`/`km_topics`/`km_summary` 出现在新收编文档的 frontmatter（由反思轮标注）；
- [ ] 全量 pytest 绿（基线口径）。

### 风险与边界

- 非 .md 文件跳过（PDF 二期接上游 markitdown/pypdf 转换）；
- 知识库副本 ≠ 原稿：过档即定稿（D-3），修订版机制二期；
- 归档目录名无法解析日期时，收编退回当天日期（记录 warning）；
- `retention_days` 的前端设置编辑器列为二期（当前改 `configs/knowledge.toml` 或告诉我帮你改）。
