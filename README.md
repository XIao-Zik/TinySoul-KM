# TinySoul-KM

基于 [TinySoul-Agent](https://github.com/your-org/TinySoul-Agent) 运行时的**本地个人知识管理 Agent**：把 Obsidian/Markdown 笔记库和聊天记录导出收进统一知识库，自然语言混合检索（词法 + 向量、带真实来源引用），每日自动整理并生成带强制来源引用的知识卡片，Tauri 桌面端提供检索 / 卡片流 / 知识图谱 / 导入面板。

```
Obsidian vault ──┐            ┌─ cards/（每日知识卡片）
聊天记录导出 ────┤            │
                 ▼            ▼
        knowledge 插件（唯一存储 owner：notes/ chats/ cards/ + checksum 增量索引 + tombstone）
                 │
   km.search（复用内核检索管道：query/backlinks/directory + filter/select/rerank + 分页）
                 │
   Memory Reflection Turn（每日反思 → km.generate_card → 伪造引用被类型化拒绝）
                 │
   Tauri 2 + React 19 桌面端（Knowledge 页：检索 / 卡片流 / 图谱 / 导入）
```

## 为什么值得看

- **在约束严格的 Agent 运行时里按 owner/插件协议扩展**：全部源码改动只触碰 4 个白名单位置（插件注册行、检索 schema 摊平、CLI 子命令、config catalog 条目），其余均为新增文件——对上游持续可合并。为什么不用 ChromaDB：`docs/pkm/01-architecture-and-decisions.md` §2 的六条论证。
- **复用而非自造**：检索走内核 `kernel/retrieval` 管道（来源→约束→引用快照→分页令牌），卡片复用 Reflection Turn 内核，向量复用 `EmbeddingIndex`——没有第二个向量库。
- **可量化的验收**：5k 笔记全量导入 19.3s / 重复导入 0.5s / 删除可追溯（tombstone）；检索 hit@5 = 0.917、MRR = 0.822（60 题，词法基线）；warm p95 = 81ms。完整数字与消融见 [evals/report.md](evals/report.md)。
- **诚实工程**：卡片 `source_refs` 逐一校验、伪造引用被类型化拒绝；免费模型的 tool-calling 缺陷（嵌套 schema 字符串化）定位并修复；已知限制全部写进报告。

## 快速开始（≤ 6 条命令）

```powershell
# 0) 前置：Python 3.13+、Node 20+、pnpm、Rust 1.97+（桌面端）
python -m pip install .
tinysoul init my-pkm                      # 1) 初始化项目（标准 profile）
# 2) 配置凭据：编辑 my-pkm/.env（GLM_API_KEY 等）与 configs/llm/providers.toml
tinysoul km-ingest --root my-pkm --obsidian "D:\Obsidian\MyVault" --dry-run   # 3) 预览导入
tinysoul km-ingest --root my-pkm --obsidian "D:\Obsidian\MyVault"             # 4) 增量导入
tinysoul start --root my-pkm              # 5) 启动后端（每日 00:15 自动反思出卡片）
# 6) 桌面端：cd visualization && pnpm install && pnpm tauri dev
#    Knowledge 页 → 设置 projectRoot 为 my-pkm → 检索 / 卡片流 / 图谱 / 导入
```

聊天记录导入：`tinysoul km-ingest --root my-pkm --chat <导出文件> --platform deepseek`（JSON / Markdown / HTML）。

## 评测

| 指标 | 数值 |
|---|---|
| 检索 hit@1 / hit@5 / hit@10 | 0.717 / **0.917** / 0.950 |
| MRR | 0.822 |
| 5k 笔记全量导入 / 重复导入 | 19.3 s / **0.5 s** |
| 检索延迟（5k，warm p95） | 81 ms |
| 卡片来源引用抽检 | 100% 指向真实文档（伪造即类型化拒绝） |

方法、分题型数字、失败案例与配置消融：[evals/report.md](evals/report.md)；评测集与 harness：[evals/](evals/)。

## 与上游的关系

基于 TinySoul-Agent（MIT）——一个以 Context / Action / Session / Workspace / Agent Home / Memory / 日生命周期为边界的本地 provider-neutral Agent 运行时。上游能力全部保留；本项目的改动面：

| 位置 | 改动 |
|---|---|
| `tinysoul/agent/composition/builder.py` | 插件注册行 + `references.bind` km 端口 + embedding owner 映射（3 处） |
| `tinysoul/kernel/retrieval/policy.py` | 检索 action 的模型可见 schema 摊平（弱模型 tool-calling 兼容；`parse_retrieval_request` 仍是权威语法） |
| `tinysoul/gateway/cli.py` | `km-ingest` 子命令 |
| `tinysoul/infra/config/catalog/context.toml` | `knowledge.*` 配置描述条目（上游 catalog 覆盖契约） |

其余全部是新增文件（`tinysoul/plugins/knowledge/`、`tinysoul/assets` 的 km 目录、`tests/km/`、`evals/`、`visualization/src/features/km/`）。设计文档：[docs/pkm/](docs/pkm/)（总纲、架构决策、导入、检索、反思卡片、前端、评测、二期路线）。上游原 README 的安装 / SDK / 开发说明继续有效，见 git 历史（`upstream-baseline` tag）。

## 二期路线（已设计，未实施）

文献接入（Zotero/MCP）· 无人值守 SDK 自动化 · 联网降级检索（知识库严格优先）与知识勘误审计 · 深度整理 Job · 研究项目 Workspace · 网页剪藏——见 [docs/pkm/07-capability-activation.md](docs/pkm/07-capability-activation.md)。
