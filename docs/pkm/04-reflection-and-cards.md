# 每日反思与知识卡片（MVP 简版）

> 状态：草案 v1 ｜ 里程碑：M4 ｜ 依赖：[02](02-ingestion.md)、[03](03-retrieval.md)
> 原则：**复用 reflection 插件的 Reflection Turn 机制**（TurnProfile 独立 Context/Action 策略、每日策略自动安排根 work），不自造调度。盲区发现是二期占位（§6）。

## 1. Reflection 机制现状（我们要接的口）

- Reflection Turn 与 User Turn 同级，复用同一 Turn/Cycle/Phase 内核，通过 TurnProfile 取得独立 Context、Action 策略与受约束服务；不发布用户回答、不写入 User Session（AGENTS.md 执行模型）。
- 每日策略（项目 `configs/reflection.toml`）在日期切换/空闲时自动安排独立根 work；用户也可显式授权单次。
- 既有两种 profile：Home Reflection（身份演进）、Memory Reflection（`memory.write`/`memory.write_daily` 持久写）。

**接入方式**：给 knowledge 增加一个 Reflection 情景（`knowledge-reflection` profile extension，由插件 `profile_extension_factory` 提供），或先走最小路径——**在 Memory Reflection 的每日策略里追加 km action 的可见性**（若 profile 的 action 白名单支持跨插件配置，则零源码）。实现时按此顺序尝试，取先可行者。

## 2. 两阶段流水线（DeepSeek 方案的合理内核，落地到 TurnProfile）

**阶段一：当日消化**（低模型用量）

- 输入：当日新增/变更的知识文档（`km_imported` 当日）、当日 User Session 摘要、当日 memory daily；
- 输出：更新 memory `daily` 文档（"今天收进了什么、聊了什么"），并经 `core.session.organize` 维护当日话题图；
- 全部用既有 action（`memory.write_daily`、`core.session.organize`），不写新 executor。

**阶段二：知识卡片生成**（核心差异化）

- 新 executor `km.generate_card`（插件 `actions/card.py`，模型用途 `knowledge.card_writer`）：
  - 候选来源：当日新增文档 + 阶段一产出的要点，经 `km.search` 拉取关联旧知识（限制候选数，控制上下文）；
  - 模型任务输出结构化卡片（JSON，schema 固定）：
    ```json
    {
      "question": "这个概念解决什么问题？",
      "answer": "3–5 句话，含关键结论",
      "concept_tags": ["attention", "kv-cache"],
      "source_refs": ["k-20261011-a1b2c3#p3", "memory:concept/transformer"],
      "confidence": "high|medium|low"
    }
    ```
  - **来源引用强制校验**：`source_refs` 必须指向真实存在的文档与段落（executor 内校验，失败即类型化失败，不伪造——对齐 AGENTS.md"不伪造工具结果"纪律）；
  - 频控：每日 1–5 张（按当日新增量伸缩），配置上限。

## 3. 卡片存储（归 knowledge，不归 memory）

`<my-pkm>/knowledge/cards/YYYY-MM-DD.md`，一文件多卡片，frontmatter 记 `km_source: card` + 生成批次；卡片正文是自含的问答体。理由：

- 卡片是从笔记派生的**整理产物**，生命周期跟随 knowledge store（重索引/重建不影响）；
- memory 五类契约不动（卡片不是 daily/entity/concept/fact/note 任何一个）；
- 卡片自动进入 `km.search` 语料（`km_source: card` 可作为过滤维度），也可被 M5 前端按日浏览。

**可逆性**：删除 `cards/` 即回滚全部卡片，不影响笔记与 memory。

## 4. 跨日关联的边界

- 卡片的 `source_refs` 可以指向 memory 的 concept/entity ref（读取引用边归来源 owner 校验），形成"笔记 ↔ 记忆概念"的图谱边——这是总纲图谱叙事的实现处；
- **不做**：跨日大规模重组织（那属于 Session 明确不承担、Memory 五类契约管不到的灰色地带，二期用"盲区发现"启发式替代，见 §6）。

## 5. 配置与验收

```toml
# configs/reflection.toml 追加（示意，以现有字段为准）
[reflection.knowledge]
enabled = true
daily_card_limit = 5
card_model_use = "knowledge.card_writer"
```

验收（M4）：

- [ ] 连续 3 天真实使用：每日自动产出 1–5 张卡片，无人工触发；
- [ ] 卡片 `source_refs` 抽检 20 条 100% 指向真实文档；
- [ ] 卡片可被 `km.search` 检索（构造"只有卡片里有答案"的用例验证）；
- [ ] Reflection Turn 不写 User Session、不产生用户可见回答（符合内核语义）；
- [ ] 关闭 `[reflection.knowledge] enabled` 后行为与原版完全一致（可回退性验收）。

## 6. 二期占位：盲区发现

MVP 不实现，但设计预留：基于 knowledge index 的**纯启发式**（不花模型调用）计算——孤立文档度（无入边无出边）、概念覆盖缺口（高频 tag 无对应 memory concept）、卡片问题重复度；结果作为 `km.gaps` 报告文档 + 前端面板（M5 预留路由）。二期再加"主动提问"（让 Agent 针对盲区向你提问）。盲区清单同时是二期「研究项目模式」的输入（见 [07](07-capability-activation.md) §E5）：盲区 → 自动起草研究 plan → 跨轮推进补齐。

## 7. 风险

| 风险 | 缓解 |
|---|---|
| Reflection profile 的 action 白名单不支持跨插件扩展 | 回退到插件自带 profile extension 路线（多 1–2 天工作量，已在 01 文档 §4 的 `profile_extension_factory` 里） |
| 卡片质量低/啰嗦 | prompt 用 TaskPrompt 挂 domain skill（`home/skills_domain/knowledge/` 下加卡片写作指引），并依赖评测集迭代；confidence=low 的卡片默认不入库 |
| 每日任务与用户活跃时间冲突 | 每日策略时间可配；错过的合并到下一次 |
