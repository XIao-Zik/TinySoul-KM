# TinySoul-KM 执行文档（工作区归档收编）

> 状态：**已执行（T1–T8 代码落地，见文末执行记录）** ｜ 日期：2026-10-13
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

- [x] 拖入工作区的 .md 在跨天归档后，无需手动导入即被收编（`km_source=workspace`，`imported_on=归档业务日`，已在 my-pkm 真实收编）；
- [x] 重复收编幂等（unchanged 计数正确，实测重复 0 写入）；
- [x] 超期清理：仅删除"已收编且超期"的归档 workspace 文件；未收编文件与 session/memory 快照保留；`retention_days=0` 时完全不清理；
- [ ] 12 号归档里的《2026-09-07-如何让大模型为你所用.md》经收编 + 12 号补反思后生成卡片，来源引用指向它（已按业务日 `imported_on=2026-10-12` 收编，待下次 10-12 反思轮出卡片）；
- [x] `km.search` 可用 `where: {source: workspace}` 过滤；前端图谱/来源芯片有 workspace 颜色；
- [ ] `km_type`/`km_topics`/`km_summary` 出现在新收编文档的 frontmatter（由反思轮标注；单测已用桩 LLM 验证写回路径，真实标注待反思轮）；
- [x] 全量 pytest 绿（基线口径：仅剩与本特性无关的预存失败，已用 git stash 基线逐一核实）。

### 风险与边界

- 非 .md 文件跳过（PDF 二期接上游 markitdown/pypdf 转换）；
- 知识库副本 ≠ 原稿：过档即定稿（D-3），修订版机制二期；
- 归档目录名无法解析日期时，收编退回当天日期（记录 warning）；
- `retention_days` 的前端设置编辑器列为二期（当前改 `configs/knowledge.toml` 或告诉我帮你改）。

---

## 第三部分：执行记录（2026-10-13）

### 改动清单（T1–T8 全部完成）

| 任务 | 文件 | 说明 |
|---|---|---|
| T1 | `tinysoul/plugins/knowledge/storage/store.py` | `workspace_root` 属性、`write_workspace`、`write_document`（按 km_source 分发读写，供标注写回） |
| T2 | `tinysoul/plugins/knowledge/config.py` | `KnowledgeArchiveSettings`（archive_root 默认项目根 `archive/`；retention_days 默认 30，0=禁用）+ 解析与校验 |
| T3 | `tinysoul/plugins/knowledge/engine.py` | `ingest_workspace_archive()`、`cleanup_expired_archives()`、`annotate_document()`、`archive_root` 属性 |
| T4 | `tinysoul/plugins/knowledge/actions/card.py` | 反思轮候选选择前调收编→随后调清理；卡片 prompt 扩展 `annotations` 输出；D-1 标注写回（逐条校验，伪造/非法跳过不致命） |
| T5 | `plugin.py` + `assets/common/home/skills_action/km/km.search.md` + `skills_domain/km/DOMAIN.md` | capability scopes 与 skills 文案加 workspace |
| T6 | `visualization/src/features/km/KmPage.tsx` | `SOURCE_COLORS.workspace = "#22c55e"`（绿色系） |
| T7 | `tests/km/test_workspace_ingest.py`（新增，19 例） | 收编幂等/归档日标注/日期回退/清理保留未收编/session 与 memory 不触碰/清理禁用/标注写回且重收编不丢/where=workspace 过滤/配置解析/反思轮集成 |
| T8 | `tinysoul/assets/common/configs/knowledge.toml` + `my-pkm/configs/knowledge.toml` | `[knowledge.archive]` 设置值暴露与注释文档 |
| 追加 | `tinysoul/infra/config/catalog/context.toml` | `knowledge.archive` 字段组登记（打包 toml 叶子覆盖测试要求，非前端编辑器） |

### 验证结果

- `tests/km/`（63 例）与 `tests/infra/config/` 全绿；全量 pytest 仅剩预存失败（缺可选依赖 `acp`/`crawlee`、wheel 构建、若干 asyncio 时序用例），已用 `git stash` 基线逐一核实与本特性无关；
- 真实数据（my-pkm，临时知识库根只读验证）：`20261013T092229` 归档里的《2026-09-07-如何让大模型为你所用.md》收编为 `workspace/2026-10-13/2026-09-07-如何让大模型为你所用.md`，`km_source=workspace`、`imported_on=2026-10-13`；重复收编 unchanged=1 零写入；保留期 30 天清理不删除（未超期）。

### 归档日口径说明（重要，2026-10-13 晚修订）

最初实现按设计要点 2 取**归档目录名前 8 位**（执行归档的时间戳）。实测发现口径错误：跨天归档发生在次日 00:15（或用户早上开机时），目录名日期恒为业务日的**下一天**，导致文档永远赶不上对应业务日的补反思，且与前端归档视图（按业务日展示）不一致。已修订为：

1. **`transition.json` 的 `from_day` 优先**——归档目录内上游写入的记录，`from_day` 即被归档的业务日（权威口径）；
2. 目录名前 8 位退回（transition.json 缺失/损坏时）；
3. 两者皆不可解析 → 退回当天 + warning。

修订后《2026-09-07-如何让大模型为你所用》`imported_on=2026-10-12`，成为 **target_day=2026-10-12 补反思**的同日候选，与验收标准原文一致；此后每个归档目录都按其真实业务日对应反思轮，当晚即可出卡片，无一天滞后。

### 卡片重复问题与修复（2026-10-13 晚）

反思轮一个 turn 内会多次调用 `km.generate_card`（实测 22:08–22:13 五分钟内 40 次），且跨重启的补跑会重跑同一 target_day——原 `write_cards` 盲目追加，导致 `cards/2026-10-12.md` 同 4 张卡片重复 6 轮（20 段）。修复：

1. `write_cards` 按 **(问题, 来源引用)** 去重：已存在的组合跳过不追加（返回 `CardWriteReport{ref, written, duplicates}`，载荷含 `duplicates_skipped`）；同一天内真正的新卡片仍正常追加；
2. 存量清理：`cards/2026-10-12.md` 移除 16 个重复段、保留 4 张唯一卡片（`2026-10-11.md` 本无重复），索引条目同步更新。

注：每轮重复调用仍消耗一次 LLM 生成（调用次数属上游反思轮行为，本文档"上游稳定性问题"第 1 条），去重只消除数据层面的重复堆积。

### 卡片来源"找不到文件"修复（2026-10-14）

Turn 2026-10-14/3（手动补反思 target_day=2026-10-12）验证了收编链路全通：卡片执行成功（新格式载荷，cards_written=2、annotated=4），《如何让大模型为你所用》被引用进卡片（km:k-a118b1d747bc）且 km_type/km_topics/km_summary 标注写回。但点击卡片来源报"找不到文件"：**Tauri 端 `km_document` 命令自带一份 source→子目录映射，缺 `workspace` 分支**，工作区文档被落到 `notes/` 下查找而 404。修复 `visualization/src-tauri/src/lib.rs`（补 `"workspace" => "workspace"`）并重建桌面端。

另：该 Turn 内 `km.search.query.embedding` 多次报 `unavailable`（embedding 提供方不可达），检索自动退回词法通道，属环境/模型可用性问题，非本特性缺陷。

### 知识卡片清理/编辑功能（2026-10-14）

用户侧卡片治理能力补齐：卡片流每张卡片支持**编辑**（问题/答案/标签/置信度，来源引用保持不变）与**删除**（两步确认）。实现于桌面端（与 `km_cards`/`km_document` 的直读架构一致）：`km_card_delete`/`km_card_update` Tauri 命令按 (问题, 来源引用) 定位卡片段，整文件规范化重写——其余卡片段、frontmatter 标注（km_type 等）逐行保留；删除时从索引标题重算 `km_links`（维护真实反边），并把派生索引条目（checksum/size/mtime/links）同步刷新。Rust 单测 6 例覆盖解析往返/删除重算/km_links 手术/校验和与 Python 口径一致。

已知边界：删除的卡片若同日反思**重跑**会被重新生成（去重只认文件现存内容）；桌面端直改文件后，后端 `km.search` 的内存检索缓存待其下次自身索引变更或重启后刷新。

### 横幅不消除修复：write_daily 拒绝循环（2026-10-14）

横幅消除机制（前端复查 + 后端 `missing_daily_days`）本身已实现，但被上游校验卡死形成死循环：`DailyMemoryDocument` **禁止正文含一级标题**（`_without_h1`），而模型每次都提交 `# 2026-10-12 Daily Memory` 开头的正文；`memory.write_daily` 的拒绝反馈是通用文案、不含真实规则，模型在轮内无法自我纠正 → 日程 Memory 从建库起一篇都没写出 → `missing_daily_days` 永不消空。修复三处：

1. `plugins/memory/actions/write.py`：`MemoryContractError` 的具体信息（如 "cannot contain a level-1 heading"）附加到拒绝反馈，模型可在轮内自我纠正；
2. `write_daily` 工具描述与前端补跑指令（`REFLECTION_INSTRUCTIONS`）显式写明：正文不要一级标题/frontmatter/自拟标题，直接以 `##` 小节开始；
3. 前端横幅状态机：`running` 此前成功后从不清除（芯片永远"自动补跑中…"），现改为按 10s/40s/90s/180s/300s 轮询可用性、最后一次仍缺才交还手动按钮。

部署后实测：10-11/10-12 两日补跑均成功写入 `memory/daily/`，`missing_daily_days` 清空（13:13:51），横幅消除。

### 生效条件

- 后端已重启（2026-10-13 22:57，`start-backend.bat`），`card.cpython-313.pyc` 编译时间确认加载的是修复后代码；桌面端已自动重连；
- 《2026-09-07》已实际收编入 `my-pkm/knowledge/workspace/2026-10-12/`（停机窗口内完成，幂等验证通过）；打开 KM 页触发横幅补跑 target_day=2026-10-12 即可出卡片并写回标注；
- 前端 workspace 来源颜色需重新构建桌面端（Vite dev 模式即时生效）。

### 运维插曲（记录）

22:04 首次重启后、22:32 用户重启前，事件流中出现旧格式卡片载荷（22:08–22:13），且 `__pycache__` 同时存在 cpython-312 与 cpython-313 两套字节码——该时段有一个**非当前 env 的旧代码进程**在服务（疑似桌面端自动拉起）。22:32 用户重启后 22:57 最终重启均确认从本仓库可编辑安装加载新代码。若再次出现"改码不生效"，先核对 `python -c "import tinysoul; print(tinysoul.__file__)"`（须在中性 CWD 下执行）与 `__pycache__` 编译时间。
