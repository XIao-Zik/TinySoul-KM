# TinySoul-KM 进度日志

> 本文件是长会话中唯一的进度事实源。每个里程碑完成时更新：完成项 / 偏差 / 遗留。
> 约定：日期 2026-xx-xx；分支 `pkm`；开发环境 conda `TinySoul-PKM`；项目实例 `D:\ProgramData\RESUME\my-pkm`。

## 状态总览

| 里程碑 | 状态 | 提交 |
|---|---|---|
| M0 地基 | ✅ 完成 | 见下文 M0 记录 |
| M1 插件+导入 | ⬜ 未开始 | |
| M2 检索 | ⬜ 未开始 | |
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

## 附录：环境事实

- 开发：conda `TinySoul-PKM`（Python 3.13.x，可编辑安装 tinysoul）；原版对照：conda `TinySoul`。
- Node 24.11.1 + pnpm 12.10.1 已有；MSVC Build Tools 2022（VC 14.44）已装。
- my-pkm 路径：`D:\ProgramData\RESUME\my-pkm`。
