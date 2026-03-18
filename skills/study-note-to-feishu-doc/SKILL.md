---
name: study-note-to-feishu-doc
description: Save learning notes sent in chat as new Feishu docs. Use when the user sends study notes, course notes, class summaries, training notes, asks to archive notes into Feishu Docs, or says to save/sort/organize the note as a Feishu document. Also use by default when the user's message clearly looks like raw study notes or dictated classroom notes, even if they did not explicitly ask to create a doc, unless they only want plain chat cleanup. Extract the topic and date first; if either is uncertain, ask one short follow-up question. Create one or more new Feishu docs in the user's personal knowledge base with titles based on topic + date, split mixed-topic notes into separate docs when the user asks or when the note is obviously divided into distinct subjects.
---

# Study Note To Feishu Doc

## Overview

Turn raw learning notes from chat into a new Feishu document.

Default behavior:
- Prefer extracting **topic** and **date** automatically from the note
- If either is unclear, ask **one short clarification**
- Save the doc to **`my_library`** unless the user specifies another location
- Create a **new** document instead of overwriting an old one
- When the incoming message is clearly a raw note dump, default to creating the Feishu doc proactively instead of waiting for a second confirmation
- When the note clearly contains two or more distinct topics, split it into multiple docs if the user asks to split, or ask one short question only if the split is ambiguous

## Workflow

1. Read the note content from the current conversation.
2. Decide whether the message is a **raw study note** or just a normal question/chat.
3. Identify the likely **topic**.
4. Identify the likely **date**.
5. Decide whether the content should stay in one doc or be split into multiple docs by topic.
6. If topic/date/splitting is genuinely uncertain, ask one concise follow-up question.
7. Rewrite the note into clean Lark-flavored Markdown.
8. Create one or more Feishu docs with `feishu_create_doc`.
9. Return the doc title(s), link(s), and a short summary of what was saved.

## Automatic Trigger Heuristics

Treat the message as a note that should be archived proactively when several of these signals are present:
- long paragraph or multiple paragraphs of dense factual content
- dictated/classroom style wording, including fragmented spoken phrases
- many concept keywords, examples, code fragments, or API/function names
- obvious learning structure such as definitions, points, methods, parameters, or "第一/第二/最后"
- the user is continuing a running stream of class notes

Do **not** auto-create a doc when the user is clearly just:
- asking a question
- requesting explanation only
- brainstorming
- sharing a tiny snippet that is not yet a note

If the message is borderline, ask one short confirmation instead of assuming.

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
