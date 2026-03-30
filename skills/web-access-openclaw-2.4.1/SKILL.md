---
name: web-access-openclaw
license: MIT
upstream_github: https://github.com/eze-is/web-access
description: |
  OpenClaw 适配版联网技能：统一处理搜索、网页读取、动态页面交互与登录态场景。
  优先使用 OpenClaw 原生 browser/web_fetch 工具；仅在确需用户本机 Chrome 登录态时启用 CDP Proxy。
metadata:
  upstream_author: 一泽Eze
  upstream_version: "2.4.1"
  adapter: sk
  adapter_version: "1.0.0"
---

# web-access (OpenClaw Adapter)

> 这是 `eze-is/web-access` 的 OpenClaw 适配版，不是直接迁移版。

## 核心原理（保留 upstream 精髓）

1. **目标驱动，不是工具驱动**：先定义“什么算完成”，再选最短路径。  
2. **分层路由**：轻任务走轻工具，重交互走浏览器，避免一上来就重型自动化。  
3. **证据迭代**：每一步结果都用于修正策略，不在错误路径上盲目重试。  
4. **可复用经验**：按站点沉淀“有效模式/已知陷阱”。

## OpenClaw 架构适配（关键）

原版针对 Claude Code 的 `WebSearch/WebFetch/curl + CDP Proxy`。  
在 OpenClaw 中改为以下优先级：

### Layer 1（默认首选）
- `web_fetch`：已知 URL 的正文抽取、快速读取。

### Layer 2（动态交互首选）
- `browser`：页面点击、输入、截图、登录流程、动态渲染处理。
- 优先使用 OpenClaw 托管浏览器（隔离环境）。

### Layer 3（仅当必须使用“你自己的 Chrome 登录态”）
- `scripts/check-deps.mjs` + `scripts/cdp-proxy.mjs`（保留 upstream）
- 通过本机 Chrome remote debugging 处理强登录态/特定反爬场景。

> 简单说：**OpenClaw 原生 browser 是主通道，CDP Proxy 是登录态兜底通道**。

## 决策路由

| 场景 | 优先工具 |
|---|---|
| 已知 URL，主要抽文本 | `web_fetch` |
| 需要点击、输入、滚动、上传、截图 | `browser` |
| 网站内容必须依赖用户已登录 Chrome 且隔离浏览器拿不到 | CDP Proxy（`scripts/*.mjs`） |
| 多目标独立调研 | `sessions_spawn` 并行分治 |

## CDP Proxy 使用说明（仅兜底）

### 前置
```bash
node "<skill_dir>/scripts/check-deps.mjs"
```

要求：
- Node.js 22+（低版本需全局安装 `ws`）
- Chrome 打开 `chrome://inspect/#remote-debugging` 并允许 remote debugging

### API（保持与 upstream 一致）
- `GET /targets`
- `GET /new?url=...`
- `POST /eval?target=...`
- `POST /click?target=...`
- `POST /clickAt?target=...`
- `POST /setFiles?target=...`
- `GET /scroll?target=...`
- `GET /screenshot?target=...`
- `GET /close?target=...`

详见：`references/cdp-api.md`

## 站点经验

按域名写入：`references/site-patterns/<domain>.md`  
记录三类信息：
- 平台特征
- 有效模式
- 已知陷阱

## 安全边界（OpenClaw）

- 不主动操作用户已有 tab（除非明确要求）
- 任务结束关闭自己新建 tab
- 不读凭据文件，不导出敏感会话数据
- 遇到登录/权限障碍先告知用户再继续

## 兼容性说明

- upstream 的设计思想、CDP 脚本与 API 保留
- 工具编排已适配 OpenClaw（browser/web_fetch/sessions_spawn）
- 避免把 Claude Code 的工具名硬套到 OpenClaw
