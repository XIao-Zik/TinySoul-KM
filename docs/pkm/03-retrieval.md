# 检索层：源注册、km.search 与模型配置

> 状态：草案 v1 ｜ 里程碑：M2 ｜ 依赖：[01](01-architecture-and-decisions.md)、[02](02-ingestion.md)

## 1. 目标

让模型（和前端）能用自然语言检索 knowledge store，结果：词法 + 向量混合、带来源引用与真实反链、分页渐进披露——**全部复用 kernel/retrieval 管道**，knowledge 只实现"来源 corpus"。

## 2. 源注册（唯一的 kernel 改动）

`tinysoul/kernel/retrieval/policy.py`：

1. `SourceKind` 枚举加 `KNOWLEDGE = "knowledge"`；
2. 解析/校验函数（:261/:356/:556 附近）对齐新枚举；
3. `docs/design/action-model-retrieval.md` 补一段说明（仓库规约：文档与实现一致）。

预计 30–60 行，全部集中在枚举与校验，不碰六操作语义。

插件侧声明 capability（参照 `plugins/memory/plugin.py:61–70`）：

```python
SearchCapability(
    source=SourceKind.KNOWLEDGE,
    operations=frozenset({OperationKind.QUERY, OperationKind.BACKLINKS,
                          OperationKind.DIRECTORY, OperationKind.SELECT,
                          OperationKind.FILTER, OperationKind.RERANK}),
    ...)
```

## 3. corpus 实现（`retrieval/corpus.py`）

| 操作 | 实现要点 |
|---|---|
| query | 两路融合：词法（标题/标签/正文正则与分词命中，参照 memory `retrieval/query.py` 的词法单元做法）+ 向量（`NativeEmbeddingBackend`，对 query 文本取 embedding 后 top-k）；融合分数 = 加权倒数排名（RRF），权重可配 |
| backlinks | 读 `index.json` 的 links 表反向倒排——**真实引用边**（AGENTS.md：反链必须来自真实引用边，不做隐藏预筛） |
| directory | 按 `km_source`/日期/目录树枚举，供浏览型查询 |
| select/filter/rerank | filter 只处理当前候选集（资格判定归 corpus 的 `source.where`）；rerank 默认走模型用途 `knowledge.rerank`（可配关闭退化为分数序） |

快照与分页遵守管道既有契约：结果复用完整快照与来源覆盖，不编造命中理由；分页令牌绑定 Turn/profile。

## 4. action 声明（项目侧，零源码）

### 4.1 catalog（随 profile 初始化进项目，`assets/common/configs/action/catalog/knowledge/`）

```toml
# domain.toml
name = "knowledge"
description = "个人知识库：笔记、聊天记录与知识卡片的检索与组织"
```

```toml
# actions/search.toml
name = "km.search"
description = "在个人知识库中检索笔记、聊天记录与知识卡片"
tool = true                     # 模型可见
[parameters]                    # 以现有 catalog 文件的 schema 写法为准
  # query / source 过滤 / page 等
[execution]
executor = "km.search"          # 插件 actions/search.py 注册
```

### 4.2 skills（Home 内容，项目侧）

- `home/skills_domain/knowledge/DOMAIN.md`：什么时候该用 knowledge 域、与 memory.search 的分工（"找我的笔记/导出的对话 → km.search；找你自己记住的事实 → memory.search"）；
- `home/skills_action/knowledge/km.search.md`：参数细节、结果结构、refs 用法。

### 4.3 检索行为配置（`configs/action/retrieval.toml`）

```toml
[action.retrieval."km.search".query]
enabled = true
[action.retrieval."km.search".select]
enabled = true
[action.retrieval."km.search".rerank]
enabled = true        # 评测后决定默认值
[action.retrieval."km.search".page]
size = 8
```

## 5. 向量与 embedding 配置

### 5.1 索引切分

- 以**段落**为基本单元（空行分隔），标题路径（H1–H3 链）作为每段上下文前缀；
- 段落 > 512 tokens 再按句子切；代码块不跨段切断；
- 每段向量记录 `{doc_id, para_idx, char_range}`，命中后回读原文——**向量缓存只做召回，引用永远指向原文**（快照单一职责）。

### 5.2 后端

`NativeEmbeddingBackend` 包装 `infra/model_services/vectors.py` 的 `EmbeddingIndex`，缓存目录 `<km.root>/.tinysoul_knowledge/embeddings`；向量条目带 `doc checksum`，导入增量更新时仅重算变更文档的段落向量（deleted → 索引删除，modified → 重算）。

### 5.3 模型配置（项目侧）

```toml
# configs/infra/model_services.toml（示意，以现有字段为准）
[embedding.knowledge_main]
adapter = "openai_embedding"
provider_bindings = [{ provider_id = "bigmodel", model = "embedding-3" }]

# configs/knowledge.toml（插件配置段）
[knowledge]
embedding_use = "knowledge_main"
vector_weight = 0.6              # RRF 融合权重
```

本地模型路线（断网/零费用）：`model_services.toml` 换 onnx 本地 adapter；两种模式的检索质量对比进评测报告（06 文档）。

## 6. 验收标准（M2）

- [ ] `km.search` 在 Agent 对话中可被模型选择并正确返回（带 refs、分页）；
- [ ] 同一查询的词法路/向量路/融合路结果可分别观测（调试开关或日志）；
- [ ] 反链来自真实 `km_links` 边：造 1 个 A→B 链接用例验证 backlinks 只返回 B 的真实反链；
- [ ] 评测集（06 文档构建）hit@5 ≥ 词法基线 +5pt；记录 bigmodel API 与本地 onnx 两种模式；
- [ ] 5k 笔记下 `km.search` 端到端延迟 P95 < 2s（不含模型 rerank）；
- [ ] `pytest` 全绿；`test_architecture.py` 类架构约束测试不因新插件破坏。

## 7. 风险

| 风险 | 缓解 |
|---|---|
| `policy.py` 校验逻辑比预期耦合 | 先写失败测试再改；改动 PR 自包含，便于上游合并时快速 rebase |
| embedding API 速率限制 | 导入批量 + 退避重试；缓存按 checksum 幂等 |
| 中文分词质量影响词法路 | 词法单元生成参照 memory 现有做法；权重调优交给评测集 |
