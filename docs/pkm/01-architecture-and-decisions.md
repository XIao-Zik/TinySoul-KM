# 架构决策与 knowledge 插件设计

> 状态：草案 v1 ｜ 依赖：[00-master-plan.md](00-master-plan.md)
> 本文回答两个问题：**为什么选原生路线而不是独立 ChromaDB 向量库**（§2，回应你的提问）；**knowledge 插件长什么样**（§4–§6）。

## 1. TinySoul 扩展机制速览（写插件的地图）

依赖方向：`infra → runtime/llm → kernel → plugins/environment → agent → gateway`。

| 机制 | 位置 | 要点 |
|---|---|---|
| 插件协议 | `tinysoul/kernel/registration.py` | `AgentPlugin`：`id` / `provides` / `requires` / `configuration` / `model_uses` / `search_capabilities` / `build_generation()`；`PluginProfileExtension` 可贡献 services、context 段、actions（经 `ActionEngineBuilder` 装饰）、events、preparation/completion、trap_handlers 等 |
| 注册点 | `tinysoul/agent/composition/builder.py:978` `_standard_plugins()` | 静态显式注册，无动态发现（AGENTS.md 规约）。`gateway/cli.py:181` 与 `agent/sdk.py:97` 都走 `standard_agent()` |
| 最小模板 | `tinysoul/plugins/execution/plugin.py`（70 行） | 新插件的形态参照 |
| executor 注册 | `tinysoul/kernel/action/execution/executor.py:119–157` | catalog 里每个 action 的 `execution.executor` 必须被某插件注册，否则装配失败 |
| action catalog | 项目侧 `configs/action/catalog/<domain>/*.toml` | 纯数据驱动，**加 domain 不需要源码**（只要 executor 已存在） |
| 检索管道 | `tinysoul/kernel/retrieval/policy.py` | `SearchCapability`(:33) / `RetrievalPolicy`(:106) / `SourceKind`、`OperationKind` 枚举；六操作 = query/backlinks/directory（来源）+ select/rerank/filter（约束）；**词表是代码固定的** |
| 向量设施 | `tinysoul/infra/model_services/vectors.py` `EmbeddingIndex`；`service.py` `EmbeddingSession`(:74) | memory 已用它做 `<memory.root>/.tinysoul/embeddings` 缓存；embedding 提供商由 `configs/infra/model_services.toml` 配置（如 bigmodel embedding-3，OpenAI 兼容 adapter） |
| 反思机制 | `tinysoul/plugins/reflection/` | Reflection Turn 与 User Turn 同级；每日策略自动安排根 work；见 [04](04-reflection-and-cards.md) |
| 前端协议 | `docs/design/endpoint/index.md` | Tauri 前端经 endpoint 与后端通信，见 [05](05-tauri-frontend.md) |

## 2. 决策 D1：为什么"顺应原生架构"优于"ChromaDB 独立向量库"

DeepSeek 方案主张引入 ChromaDB + sentence-transformers，另建独立向量库与知识图谱层。**不推荐**，六个理由：

### 2.1 重复造轮子，且新轮子更差

TinySoul 的检索不是一个"向量查询函数"，而是一条有语义的管道：来源（query/backlinks/directory）→ 约束（select/rerank/filter）→ 引用快照 → 分页令牌 → 渐进披露与 Inspect 展示保护，且"引用实际内容范围、模型判断、页面摘录"各有单一职责（AGENTS.md 检索条目）。ChromaDB 只提供"向量相似度 + 元数据过滤"。外挂它意味着你要自己在旁边重写：分块与元数据模型、与 TinySoul refs/引用边体系的对接、分页与 lease 绑定、展示保护——等于把内置管道复刻一遍，还缺一半语义。**内置的词法+向量融合检索已经存在，memory 插件就是现成示范**（`plugins/memory/plugin.py:151–162` 的 SearchSession 装配）。

### 2.2 双权威问题：ChromaDB 把"派生状态"变成"权威状态"

TinySoul 的设计里，embedding 缓存、catalog、反链、词法单元都是**派生可重建状态**——删掉缓存重跑即可，没有任何一致性负担（`docs/design/memory.md`）。引入独立 ChromaDB 后，笔记数据事实上存了两份（Markdown 原文 + 向量库），删改同步、增量更新、崩溃恢复的一致性全要自己维护。个人知识库这个量级，ChromaDB（本身也是本地 SQLite 文件）与内置 EmbeddingIndex 在**能力上没有差异**，差异只在"谁替你管一致性"——内置方案把这个成本交还给了"重建"这个动作。

### 2.3 合并成本：你明确要求两版本不冲突

- **原生路线**的源码改动集中在：一个新插件目录（全是新增文件）+ `builder.py` 一行注册 + `policy.py` 加一个枚举值（几十行）。上游更新时 90% 的冲突面是"新增文件"，git 自动合并。
- **ChromaDB 路线**必须改 Memory 插件内部、绕开内置 EmbeddingIndex、可能动 `kernel/retrieval` 公共协议。而上游最近七轮重构一直在动检索和装配——你的分支每次都要手工重接。

### 2.4 依赖与打包成本

`chromadb + sentence-transformers + torch` ≈ 2–3 GB 依赖，Windows 上 torch/onnxruntime 版本匹配是常见坑。内置 `EmbeddingIndex` 基于 onnxruntime（已在依赖里），且支持 OpenAI 兼容 API（你已有 bigmodel embedding-3 可用）。简历项目要的是"clone 下来能跑"，不是 3 GB 的安装磨难。

### 2.5 简历叙事：ChromaDB 反而是减分项

"我集成了 ChromaDB"在面试里一行依赖就问穿了；真正能讲出深度的是：**"我在一个约束严格的 Agent 运行时里，按它的 owner/插件协议扩展了一个知识存储 owner，复用了它的混合检索管道与反思内核，并保持了对上游的可合并性"**——这体现架构判断力。量化指标（hit@k、增量索引性能）两条路线都能拿到，ChromaDB 不增加任何亮点。（如果面试官问"为什么不用 ChromaDB"，§2 的任何一条都是标准答案——这本身就是加分回答。）

### 2.6 规模不匹配

ChromaDB 的价值区间是百万级向量、复杂元数据过滤、多租户。个人知识库是几千~几万条笔记，内置索引毫秒级返回，性能瓶颈根本不在向量库。

### 2.7 什么时候 ChromaDB 才合理 + 缓冲设计

只有当出现"超大规模 + 复杂结构化过滤 + 多端共享向量服务"需求时才值得。为保留退路，knowledge 插件内部定义一个**薄接口**：

```python
class VectorBackend(Protocol):
    def upsert(self, ids, vectors, metadata) -> None: ...
    def query(self, vector, top_k, where) -> list[Hit]: ...
    def rebuild(self) -> None: ...   # 派生状态，必须可整体重建
```

默认实现 `NativeEmbeddingBackend` 包装内置 `EmbeddingIndex`。将来真要换 ChromaDB，只是插件内新增一个 `ChromaBackend`，**不触碰 runtime 其余部分**。这样 D1 就从"二选一"变成了"默认 A、随时可切 B、切换成本局部化"。

## 3. knowledge 插件：定位与边界

**一句话**：knowledge 是"外部笔记知识库"的唯一存储 owner（vault 笔记、聊天导出、知识卡片），memory 负责 Agent 的长期记忆沉淀，两者通过引用边互通，不互相拥有。

| 职责 | owner |
|---|---|
| Obsidian/Markdown 笔记原文、frontmatter、双链、标签 | **knowledge** |
| 聊天记录导入的知识条目 | **knowledge** |
| 每日反思生成的知识卡片 | **knowledge** |
| Agent 的实体/概念/事实沉淀（跨日记忆） | memory（不动） |
| 会话话题图（当日语义整理） | session（不动） |
| 笔记 ↔ 笔记、笔记 ↔ memory 概念的引用边 | 边归来源 owner（AGENTS.md 资源规约） |

**为什么不直接扩 Memory 的五类文档**：`docs/design/memory.md` 把五类契约锁死了（schema v2、固定 ref 方案）；塞进外部笔记要动 `documents/models.py` + `codec.py` + `infra/references.py`，是全计划侵入性最大的改法，且违背"一个事实一个 owner"的仓库规约（AGENTS.md）。新 owner 是架构明文支持的路。

## 4. 插件目录设计

```
tinysoul/plugins/knowledge/
├── plugin.py            # AgentPlugin 声明（照 execution/plugin.py 的形态）
├── config.py            # PluginConfig("knowledge", ...) ← 项目 configs/knowledge.toml
├── engine.py            # KnowledgeEngine：门面，owner 服务
├── failures.py          # 类型化失败（解析失败、索引损坏等）
├── runtime_bridge.py    # 供 gateway/endpoint 使用的投影
├── storage/
│   ├── store.py         # Markdown 文件存储：<km.root>/notes/**.md + tombstones
│   └── index.py         # checksum/mtime 增量索引（.tinysoul_knowledge/index.json）
├── ingest/
│   ├── obsidian.py      # vault 适配器（frontmatter/双链/标签）
│   └── chat_export.py   # DeepSeek/ChatGLM 导出适配器
├── retrieval/
│   ├── corpus.py        # query(词法)/backlinks/directory 三来源实现
│   └── vector.py        # VectorBackend 协议 + NativeEmbeddingBackend
├── actions/
│   ├── search.py        # km.search executor
│   └── card.py          # km.generate_card executor（M4）
└── background.py        # 可选：knowledge 目录的 Heap context 段（按需加载）
```

声明要点（签名以代码为准，下同）：

- `provides = (KnowledgeEngine,)`；`requires = (HomeService,)`（最小依赖，先不挂 workspace）。
- `model_uses`：声明 `knowledge.embedding`、`knowledge.card_writer`（卡片生成的 LLM 用途），项目侧 `routing.toml` 绑定具体模型——参照 `plugins/memory/plugin.py:71–91`。
- `search_capabilities`：声明 knowledge 的 `SearchCapability`——参照 `plugins/memory/plugin.py:61–70`。
- `build_generation()` 返回 `PluginGeneration`，`profile_extension_factory` 里注册 actions 与（可选）context 段。

## 5. 数据流

```
Obsidian vault ─┐
                ├─► ingest 适配器 ─► storage/store.py (Markdown+frontmatter)
聊天导出文件 ───┘         │                │
                          ▼                ▼
                 storage/index.py      retrieval/vector.py
                 (checksum 增量)       (EmbeddingIndex 缓存,可重建)
                          │                │
                          └───────┬────────┘
                                  ▼
                     retrieval/corpus.py (query/backlinks/directory)
                                  ▼
                  kernel/retrieval 管道 (select/rerank/filter/分页)
                                  ▼
              km.search / km.generate_card ──► Tauri 前端 + 每日反思
                                  ▼
              memory (concept/entity 沉淀) ◄──引用边── knowledge 笔记
```

## 6. 需要触碰的既有文件（白名单，对应总纲 §6.2）

| 文件 | 改动 | 为什么不可避免 |
|---|---|---|
| `tinysoul/agent/composition/builder.py:978` | `_standard_plugins()` 追加 `KnowledgePlugin()` | 注册点是静态的，架构无免改路径 |
| `tinysoul/kernel/retrieval/policy.py` | `SourceKind` 加 `knowledge`；校验逻辑同步 | 检索词表代码固定；改动预计几十行且集中在枚举与校验 |
| `tinysoul/gateway/cli.py` | 加 `km-ingest` 子命令 | 导入是外部工具场景（前端尚未就绪/批量初始化） |
| `tinysoul/gateway/project/initializer.py` | standard profile 的 assets 加 knowledge 域目录与默认 catalog | 让 `tinysoul init` 产出的新项目自带 KM 基线 |

其余一切通过**项目侧配置**完成（catalog TOML、skills、`tinysoul.toml` document_sets、`retrieval.toml`/`routing.toml`/`model_services.toml`），见 [03](03-retrieval.md)。
