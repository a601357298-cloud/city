# pua-openclaw-safe

基于 upstream：<https://github.com/tanweai/pua>（MIT）

这是给 OpenClaw 的**安全适配版**，不是原样安装。

## 为什么不直接装 upstream

原仓库包含大量面向 Claude Code 的特性：
- hook 注入
- 会话状态持久化到 `~/.pua/`
- 反馈/排行榜/会话脱敏上传逻辑
- 对话挫败语义拦截
- Claude / Codex / Cursor 等平台专用安装物料

这些能力：
1. 与 OpenClaw 架构不完全对齐
2. 有的超出当前环境的安全边界
3. 有的在 OpenClaw 中根本不会按作者预期工作

## 这个适配版保留了什么
- 高能动性
- 闭环验证
- 事实驱动
- 多路径排查
- 冰山法则（修一个点，顺手扫一类问题）

## 移除了什么
- hooks
- 会话上传
- `~/.pua/*` 写入
- 羞辱式/高压人格覆盖
- 平台专属安装脚本依赖
