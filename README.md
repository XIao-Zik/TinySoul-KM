# TinySoul-KM

TinySoul-KM 是构建在 TinySoul-Agent 运行时上的本地个人知识管理 Agent。它把 Obsidian/Markdown 笔记和聊天记录导入统一知识库，提供带真实来源的混合检索、每日知识卡片和桌面端知识浏览。

项目强调“复用运行时，而不是另造一套系统”：检索复用 TinySoul 的检索管道，知识卡片复用 Reflection Turn，向量索引复用既有 Embedding 能力。

## 项目结构

```text
tinysoul/                 # Agent 运行时与知识库插件
├── plugins/knowledge/    # 笔记、聊天、卡片、索引与检索能力
├── assets/               # 默认配置、Action 与提示词资源
└── gateway/              # CLI 入口
visualization/            # Tauri 2 + React 19 桌面端
tests/km/                 # KM 插件测试
docs/pkm/                 # 架构、导入、检索、卡片与路线文档
evals/                    # 检索质量与性能评测
scripts/                  # 测试和类型检查入口
```

## 项目功能

- 导入 Obsidian/Markdown 笔记及 JSON、Markdown、HTML 聊天记录，并按 checksum 增量更新。
- 通过词法与向量混合检索查找笔记、聊天与知识卡片；结果保留可追溯的真实引用。
- 使用 Memory Reflection 自动生成每日知识卡片，并在写入前校验每一条来源引用。
- 在桌面端浏览检索结果、卡片流、知识图谱和导入任务。
- 提供评测集与报告，覆盖检索命中率、延迟及增量导入性能。

## 安装与运行

### 环境要求

- Python 3.13+
- Node.js 20+、pnpm（桌面端）
- Rust 1.97+（构建 Tauri 桌面端）

```powershell
git clone https://github.com/XIao-Zik/TinySoul-KM.git
cd TinySoul-KM
python -m pip install -e ".[dev]"

# 创建一个用于存放个人知识库的项目目录
tinysoul init my-pkm
```

编辑 `my-pkm/.env`，填写模型凭据与模型配置。随后可先预览、再执行导入：

```powershell
tinysoul km-ingest --root my-pkm --obsidian "D:\Obsidian\MyVault" --dry-run
tinysoul km-ingest --root my-pkm --obsidian "D:\Obsidian\MyVault"
tinysoul start --root my-pkm
```

导入聊天记录时使用：

```powershell
tinysoul km-ingest --root my-pkm --chat <导出文件> --platform deepseek
```

启动桌面端：

```powershell
cd visualization
pnpm install
pnpm tauri dev
```

在 Knowledge 页面把 `projectRoot` 设置为 `my-pkm`，即可使用检索、卡片流、图谱和导入面板。

## 下一步方向

- 接入 Zotero、MCP 等研究资料来源。
- 增加无值守 SDK 自动化、网页剪藏和联网降级检索。
- 支持深度整理 Job、研究项目 Workspace 与知识勘误审计。
- 扩展评测集，持续验证引用准确性、检索质量和大规模知识库性能。

详细设计与评测结果见 [docs/pkm/](docs/pkm/) 和 [evals/](evals/)。项目基于 TinySoul-Agent（MIT）进行扩展。
