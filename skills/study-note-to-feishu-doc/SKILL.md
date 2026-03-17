---
name: study-note-to-feishu-doc
description: Save learning notes sent in chat as new Feishu docs. Use when the user sends study notes, course notes, class summaries, training notes, or asks to archive notes into Feishu Docs. Extract the topic and date from the note content first; if extraction is uncertain, ask one short follow-up question. Create a new Feishu doc in the user's personal knowledge base with a title based on topic + date, and format the content into a clean, readable study note.
---

# Study Note To Feishu Doc

## Overview

Turn raw learning notes from chat into a new Feishu document.

Default behavior:
- Prefer extracting **topic** and **date** automatically from the note
- If either is unclear, ask **one short clarification**
- Save the doc to **`my_library`** unless the user specifies another location
- Create a **new** document instead of overwriting an old one

## Workflow

1. Read the note content from the current conversation.
2. Identify the likely **topic**.
3. Identify the likely **date**.
4. If topic or date is uncertain, ask one concise follow-up question.
5. Rewrite the note into clean Lark-flavored Markdown.
6. Create a Feishu doc with `feishu_create_doc`.
7. Return the doc link and a short summary of what was saved.

## Topic Extraction Rules

Infer the topic from the strongest signal available, in this order:

1. Explicit heading or label in the note
2. Repeated keywords in the content
3. Named course/tool/domain mentioned in the first few lines
4. The main body of concepts/examples being discussed

Common examples:
- Python / `while` / `try-except` → **Python 学习笔记**
- 神通数据库 / SQL / 窗口函数 → **国产数据库学习笔记**
- WPS / VLOOKUP / 数据透视表 → **WPS 学习笔记**
- Neo4j / Cypher / 节点关系 → **图数据库学习笔记**

If multiple topics are mixed, choose the dominant one. If there is no clear dominant topic, ask the user whether to:
- split into multiple docs, or
- store as a general study note

## Date Extraction Rules

Prefer the date in this order:

1. Explicit date written in the note
2. Date implied by phrases like “今天/昨日/上午课程/下午学习” using current session date
3. Message date from the current chat context

Use `YYYY-MM-DD` in the title unless the user clearly prefers another format.

If the note references multiple days, use the date of the main note body or ask a short follow-up if the distinction matters.

## Title Pattern

Use this default title pattern:

`<主题>-<YYYY-MM-DD>`

Examples:
- `Python学习笔记-2026-03-17`
- `国产数据库学习笔记-2026-03-15`
- `WPS学习笔记-2026-03-12`

If the user explicitly asks for another naming format, follow that instead.

## Document Formatting Rules

Structure the document for readability, not just raw dumping.

Recommended structure:
- A short opening callout summarizing what this note covers
- 2–6 sections based on the note content
- Bullet points for key concepts
- Code blocks for code / SQL / Cypher examples
- A short “易错点 / 复习提示 / 应用联想” section when useful

Do not invent knowledge that is not supported by the note. Light cleanup and reorganization are good; hallucinated expansion is not.

## Creation Rules

Use `feishu_create_doc` with:
- `wiki_space: "my_library"` by default
- `title`: derived from topic + date
- `markdown`: cleaned and structured study note

If the note is very long:
1. Create a short initial doc first
2. Then continue with `feishu_update_doc` append mode if needed

## Response Pattern

After creation, reply with:
- the document title
- the Feishu doc link
- one short sentence saying what topic/date were recognized

Example:
- 已保存为：`Python学习笔记-2026-03-17`
- 链接：<doc_url>
- 识别到主题是 Python，日期是 2026-03-17。

## Clarification Pattern

When extraction is uncertain, ask only one short question.

Examples:
- “这份笔记我看着像 Python 内容，我就按 Python 学习笔记保存，可以吗？”
- “日期我先按今天 2026-03-17 记，还是你想指定成别的日期？”
- “这份内容同时有 WPS 和数据库，要我拆成两篇还是合成一篇综合笔记？”
