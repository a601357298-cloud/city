# web-access (OpenClaw Adapter)

基于 upstream：<https://github.com/eze-is/web-access>（MIT）

这是给 OpenClaw 的适配安装版本：
- 保留 upstream 的核心方法论（目标驱动、分层路由、CDP 兜底、站点经验沉淀）
- 将默认执行路径替换为 OpenClaw 原生工具：`browser` + `web_fetch`
- 仅在必须使用用户本机 Chrome 登录态时才启用 CDP Proxy

## 目录

- `SKILL.md`：OpenClaw 适配说明与路由策略
- `scripts/`：upstream Node 脚本（check-deps / cdp-proxy / match-site）
- `references/cdp-api.md`：CDP API 参考
- `references/site-patterns/`：站点经验沉淀

## 为什么不是直接照搬

原版面向 Claude Code 的工具模型（WebSearch/WebFetch/curl/CDP）。
OpenClaw 已内置浏览器与网页提取能力，直接迁移会导致“工具错位”和不必要复杂度。
因此改为：
1) OpenClaw 原生工具优先
2) CDP 作为登录态兜底
3) 与本地会话、子会话并行机制对齐
