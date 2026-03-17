# MEMORY.md

## Assistant Identity
- Name: sk
- Creature: AI coworker
- Vibe: sharp, resourceful, no-nonsense
- Emoji: 🦞
- Source: IDENTITY.md

## User Profile
- Name: 刘石开
- Age: 25
- Timezone: Asia/Shanghai
- Occupation: 审计员（中铝集团）
- Education: 刚研究生毕业，专业为财务管理
- Current training: 在南京审计大学参加计算机培训，持续到 2026-04-15

## User Work and Interests
- 目前主要负责在小坤智能体平台（Dify 本地化部署）搭建智能体。
- 使用 Python 和 vibe coding 编写审计工具。
- 培训内容包括神通数据库、Python 程序编写、WPS 使用等。
- 有每天总结知识的习惯。
- 关注 AI、经济、国际时事，并希望结合当天知识思考其在审计工作中的应用。

## Communication Preferences
- 希望沟通风格幽默、不太正式。

## Operations / Troubleshooting Memory
- 如果飞书出现“用户发了消息但我完全没收到”的情况，先查 `/tmp/openclaw/openclaw-YYYY-MM-DD.log` 里 `gateway/channels/feishu` 的最新入站记录；若最后一条 Feishu 入站长时间停滞、但 gateway 进程仍正常，则优先重启 gateway 以重建 Feishu websocket 长连接。
- 当天若同时出现 `open.feishu.cn` DNS 解析失败（ENOTFOUND）或网络接口变化异常，说明问题更像是网络/长连接失活，而不是单次回复失败。
