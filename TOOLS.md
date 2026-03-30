# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## Web search
Use the openclaw-tavily-search skills as the top_priority search tool when do web search.
If the question requires searching for more relevant knowledge, use multi-search-engine skill as an alternative solution.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Feishu / Screenshot Notes

- 发截图到飞书时，优先先把图片落到 workspace 下的稳定目录（如 `/Users/sk1/.openclaw/workspace/tmp/`）再发送；不要直接依赖 macOS 的 `$TMPDIR` / system temp 路径，发送链路可能不稳定。
- 如果需求来自微信等其他渠道，不要直接跨上下文往飞书发消息；先回到飞书当前会话内发送，或者先把文件放到稳定目录后在目标会话中发送。
- 这类问题若表现为“截图已生成，但发送失败”，先排查：`文件路径是否可稳定访问` > `是否跨会话/跨 provider 发送` > `权限问题`。

## Feishu Quiz Site Default Rule

- 当用户要求把飞书文档、学习笔记、培训材料、课程内容、知识总结等**整理成答题网站 / 选择题网站 / 刷题页 / 点击选项显示解析的网站**时，默认优先调用 `skills/feishu-doc-to-quiz-site/SKILL.md`。
- 触发词包括但不限于：`答题网站`、`选择题网站`、`刷题网站`、`题库网站`、`点击答案显示解析`、`导出错题`、`发布到 GitHub Pages`。
- 默认遵循该 skill 里的 source priority：
  1. 当前消息里的内容/附件/共享文档
  2. 用户明确给出的飞书文档链接
  3. 再去搜索现有飞书文档
- 默认发布模板仓库：`a601357298-cloud/shentong`
- 若用户只是说“出题”“帮我做题库”“整理成练习题页面”，且语境明显是网页化刷题，而不是单纯聊天里列题，也优先按这个 skill 处理。

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
