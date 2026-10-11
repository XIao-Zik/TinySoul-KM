# 数据接入：Obsidian 导入与聊天记录导入

> 状态：草案 v1 ｜ 里程碑：M1、M3 ｜ 依赖：[01-architecture-and-decisions.md](01-architecture-and-decisions.md)

## 1. 目标

1. 把 Obsidian vault（Markdown 库）收进 knowledge store，保留 frontmatter、双链、标签语义；
2. 把聊天平台导出文件（DeepSeek/ChatGLM 等）转成可检索的知识条目；
3. **增量**：重复导入只处理变更文件，删除/重命名可追溯（tombstone，不硬删——与 memory 的"无硬删除"纪律一致）。

## 2. knowledge store 的存储格式

knowledge 是 Markdown 原生 owner，不另造数据库（向量缓存是唯一派生物，见 03 文档）。

```
<my-pkm>/knowledge/
├── notes/                     # 来自 vault，目录结构镜像原 vault
│   └── <相对路径>.md
├── chats/                     # 来自聊天导出，一文件一会话
│   └── 2026-10/<platform>/<会话标题-slug>.md
├── cards/                     # M4：每日知识卡片
│   └── 2026-10-11.md
├── tombstones.jsonl           # 删除/重命名审计（老路径、时间、原因）
└── .tinysoul_knowledge/
    ├── index.json             # 路径 → {checksum, mtime, doc_id, links[], tags[]}
    └── embeddings/            # 向量缓存（派生，可整体重建）
```

每篇文档的 frontmatter（导入时生成/补充，`km.` 前缀避免与用户字段冲突）：

```yaml
---
km_id: k-20261011-a1b2c3          # 稳定 ID（内容路径 hash），重命名不变
km_source: obsidian               # obsidian | chat | card
km_source_path: D:/Obsidian/MyVault/notes/foo.md   # 原始位置（obsidian 类）
km_imported: 2026-10-11T21:04:11+08:00
km_checksum: sha256:...           # 正文规范化后的哈希
km_tags: [ml, transformer]        # 合并 frontmatter tags 与正文 #标签
km_links: [bar, subdir/baz]       # 解析后的 [[双链]] 目标
km_chat:                          # 仅 chat 类
  platform: deepseek
  date: 2026-10-02
  url: https://chat.deepseek.com/share/...
---
```

正文规则：**原样保留**，只在文首追加来源块（chat 类需要），不重排用户 Markdown。

## 3. Obsidian 适配器（M1）

### 3.1 解析范围（尽力而为，未识别语法原样保留）

| 元素 | 处理 |
|---|---|
| YAML frontmatter | 解析 tags/aliases/创建时间等并入 `km_*` 字段；解析失败不致命，降级为无 frontmatter 文档并记 warning |
| `[[双链]]` / `[[路径\|别名]]` / `![[嵌入]]` | 提取目标 → `km_links`（嵌入链接标记 `embed=true`）；目标不做存在性校验（反链按真实边计算，见 03 文档） |
| `#标签` / frontmatter `tags:` | 合并去重 → `km_tags` |
| 附件引用（图片/pdf） | 记录引用关系，附件本体不复制（检索正文时按需跳原路径） |
| Dataview/插件查询块 | 原样保留，不解析 |

实现用 Python 标准库 + `PyYAML`（已是依赖），**不引入 markdown 解析重依赖**；正文切分（供向量）在 03 文档定义。

### 3.2 增量索引算法

```
for each *.md in vault (walk):
    h = sha256(normalize(content))          # 规范化：换行统一、去 BOM
    if index[path].checksum == h: continue  # 未变，跳过
    upsert(path, h, parsed_metadata)        # 写 store + 更新 index
for each path in index not seen:
    tombstone(path, reason="vanished")      # 记录而非删除 store 文件
save index
```

- 重命名 = 旧路径 tombstone + 新路径 upsert；`km_id` 由内容首行标题+创建时间派生时跨重命名不稳定，**采用"frontmatter 已有 km_id 则沿用，否则路径 hash"**，重命名后再次导入时以 frontmatter 归并。
- 性能目标：5k 笔记全量导入 < 5 分钟（瓶颈是向量化，批量调 embedding API，见 03）；未变更文件的重复导入 < 10 秒。

### 3.3 CLI（白名单改动：`gateway/cli.py`）

```
tinysoul km-ingest --root my-pkm --obsidian "D:/Obsidian/MyVault" [--dry-run] [--full]
tinysoul km-ingest --root my-pkm --chat <导出文件/目录> [--platform deepseek]
```

- `--dry-run`：只打印将发生的变更（简历演示有用）；
- 导入完成打印统计：新增/更新/tombstone/失败清单。

## 4. 聊天记录导入器（M3）

### 4.1 输入格式

| 来源 | 格式 | 策略 |
|---|---|---|
| DeepSeek 分享链接/导出 HTML | HTML | 提取会话标题、轮次（user/assistant 交替）；分享页为 JS 渲染，优先用平台"导出/复制 Markdown"产物；HTML 兜底用 `trafilatura`（已是依赖）抽取 |
| ChatGLM/其他平台 | 导出 JSON/Markdown | 按平台写小适配器，输出统一中间结构 `{title, turns[{role, text, ts?}], url?}` |

### 4.2 转换规则

- 一会话一文件 → `chats/YYYY-MM/<platform>/<title-slug>.md`；
- 正文结构：`## 问题` / `## 回答` 交替，保留代码块；
- 长会话（> 8k tokens）按主题切分为多文件（简单启发式：连续同问Topic 聚类交给 M4 的反思去做，M3 先按轮数 20 轮一切）；
- frontmatter 记 `km_source: chat` + 平台/日期/URL，`km_links` 可指向会话中提到的笔记（M3 简化为空，交给每日反思补注）。

### 4.3 与 Session organize 的联动

导入完成后，Agent 在 User Turn 里可用既有 `core.session.organize` 把当日对话整理进话题图；知识条目侧的反向入口是 `km.search`。M3 只要求"聊天内容可被检索"，话题图↔知识条目的深度关联归 M4 反思（见 04 文档 §4）。

## 5. 验收标准（M1/M3 合并检查表）

- [ ] 5k 笔记 vault 全量导入成功，重复导入 < 10 秒；
- [ ] 修改/删除/重命名笔记后增量导入行为正确（update / tombstone / 归并 km_id）；
- [ ] `km_links`/`km_tags` 抽取抽检 20 篇，准确率 ≥ 95%；
- [ ] DeepSeek 导出样例（≥ 3 个会话）导入后正文完整、元数据正确；
- [ ] 单测：解析器（含畸形 frontmatter）、增量算法（新增/修改/删除/重命名四分支）覆盖；
- [ ] `--dry-run` 输出与实际执行一致。

## 6. 风险

| 风险 | 缓解 |
|---|---|
| vault 超大（>20k 文件）walk 慢 | 增量靠 mtime 预筛；walk 用 `os.scandir` 迭代 |
| 用户 frontmatter 字段冲突 | 只读不写用户字段；`km_*` 前缀隔离 |
| 平台导出格式变更 | 适配器按"统一中间结构"隔离，换格式只改一处 |
