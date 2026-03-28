---
name: feishu-doc-to-quiz-site
description: Turn a user-provided document or an existing Feishu document into a static quiz website, mainly multiple-choice questions, where clicking an option reveals the answer and explanation below the question. Use when the user asks to convert notes, study docs, Python docs, training materials, or Feishu documents into an answer-practice website; especially for requests like “整理成答题网站”, “做成选择题网站”, “点击答案显示解析”, “发布到 GitHub Pages”, or “把飞书文档做成刷题页”. Default source priority: (1) current message document/content, (2) explicitly provided Feishu doc link, (3) search existing Feishu docs.
---

# Feishu Doc To Quiz Site

Build a small static site from study material and publish it with minimal repo changes.

## Core behavior

- Prefer the current message's attached/shared document or pasted note content first.
- If the user gives a Feishu doc link or wiki link, use that exact source.
- If no source is provided, search Feishu docs and choose the most relevant one.
- Default output is a static website whose home page is `index.html`.
- Default interaction is: user clicks an option → show correctness + explanation directly under that question.
- Prefer touching as few repo files as possible. If feasible, create or update only `index.html`.

## Workflow

1. Identify the source material.
2. Extract the core knowledge points.
3. Rewrite them into mostly single-choice questions.
4. Create a fully static `index.html` (HTML + CSS + JS inline is fine).
5. Keep the site lightweight and dependency-free unless the repo clearly already uses a frontend stack and the user wants that.
6. Commit only the necessary file changes.
7. Push to the requested branch, usually `main`.
8. Return and, if requested, send the final online link back to the user.

## Source selection rules

### Priority order

1. **Current message content or attached/shared doc**
   - If the user pasted notes directly in chat, treat that as the primary source.
   - If the current message includes a document link, file, or quoted study note, use it first.

2. **Explicit Feishu document provided by the user**
   - If the user gave a doc/wiki URL or token, fetch that exact document.

3. **Existing Feishu docs discovered by search**
   - Search only when source is not already specified.
   - Choose the most relevant doc by title + summary + recency.
   - Prefer documents owned/edited by the user over unrelated shared docs.

## Question-writing rules

- Make the site mainly multiple-choice questions.
- Prefer 8–20 questions unless the user asks for a different size.
- Cover the main concepts, high-frequency pitfalls, definitions, flow, and practical usage.
- Make distractors plausible but clearly wrong after explanation.
- Do not invent content not supported by the source.
- Use concise explanations that teach the point, not just reveal the answer.
- When a code fragment or SQL fragment helps, show a tiny snippet in the explanation.

## Site rules

- Home page must be `index.html` unless the user explicitly wants another structure.
- Pure static delivery is preferred.
- Inline CSS/JS is acceptable and often ideal for minimal-change repos.
- Each question should support this interaction pattern:
  - click one option
  - highlight correct / incorrect state
  - reveal the explanation under the same question
- Mobile-friendly layout by default.
- Keep the copy clear and study-oriented rather than flashy.

## Repo handling rules

- Inspect the repo first.
- Do not modify unrelated files.
- If the repo is nearly empty, adding only `index.html` is preferred.
- If the repo already has a static homepage, update only what is necessary.
- Before commit, check `git status` and confirm the changed files are within scope.

## Git / publish rules

- Use the branch explicitly requested by the user; default to `main` when they say so.
- Commit with a clear message like `feat: add quiz static homepage`.
- Push to origin.
- If the repo is for GitHub Pages, return the Pages URL in the final reply.
- If the user explicitly asks to send the final link to Feishu, send it after push.

## Preferred tool pattern

- For Feishu docs: use `feishu_fetch_doc` or Feishu search tools.
- For implementation: edit/write files directly when simple; use a coding agent only when the repo/app is more complex.
- For remote publish: use git in the target repo.
- For notifying the user in Feishu: use the message tool if they explicitly want the link sent there.

## Response checklist

Before finishing, confirm all of these:

- Source document was identified correctly
- `index.html` exists
- Questions are mainly multiple-choice
- Clicking an option reveals explanation below the question
- Only necessary files changed
- Changes were committed
- Changes were pushed to `main` if requested
- Final online link was returned
- Link was sent to Feishu if requested

## Example user requests this should handle

- “把这份飞书文档整理成一个选择题网站”
- “基于我发你的 Python 笔记做一个答题网页”
- “做成静态网站，点击答案后显示解析”
- “从我飞书现有文档里找一份 Python 学习笔记，整理成刷题网站并发布到 GitHub Pages”
- “把这个培训文档做成题库网站，首页必须是 index.html”
