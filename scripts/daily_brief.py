#!/usr/bin/env python3
"""Generate a daily brief from mixed domestic + international news sources.

Design goals:
- prefer stable public feeds when possible
- degrade gracefully when some sites block scraping
- output a compact markdown brief for chat delivery
- no required third-party dependencies

Usage:
  python3 scripts/daily_brief.py
  python3 scripts/daily_brief.py --save /tmp/daily_brief.md
  python3 scripts/daily_brief.py --json
"""

from __future__ import annotations

import argparse
import dataclasses
import email.utils
import hashlib
import html
import json
import re
import ssl
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Optional

try:
    import certifi
except Exception:  # noqa: BLE001
    certifi = None


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20
MAX_ITEMS_PER_SOURCE = 8
DEFAULT_PER_CATEGORY = 4
TOP_ANALYSIS_COUNT = 3

CATEGORIES = ("AI", "经济", "国际")

CATEGORY_KEYWORDS = {
    "AI": [
        "ai", "人工智能", "大模型", "模型", "算力", "芯片", "openai", "anthropic",
        "google", "microsoft", "英伟达", "nvidia", "智能体", "机器人",
    ],
    "经济": [
        "经济", "金融", "财政", "货币", "利率", "通胀", "股市", "债券", "基金", "快递",
        "消费", "制造业", "新能源", "供应链", "光伏", "出口", "投资", "并购", "财报",
    ],
    "国际": [
        "国际", "全球", "美国", "欧洲", "日本", "欧盟", "俄罗斯", "乌克兰", "中东", "外交",
        "联合国", "关税", "战争", "冲突", "安全", "地缘", "反恐", "制裁",
    ],
}

ANALYSIS_HINTS = {
    "AI": "这条更像技术与产业协同升级信号，值得关注投入是否真正转化为效率、产品或流程收益。",
    "经济": "这条更像经营和产业景气度信号，可结合订单、物流、回款、库存等数据做交叉验证。",
    "国际": "这条更像外部风险变量，容易传导到市场预期、企业投资节奏和跨境业务安排。",
}

AUDIT_HINTS = {
    "AI": "可关注 AI/算力/系统采购投入是否形成真实应用成效，避免“花了钱但没有产出闭环”。",
    "经济": "适合从业务流、资金流、票据流、物流四个维度做穿透式核验。",
    "国际": "适合提前关注外部风险如何影响预算、采购、供应链与合规安排。",
}


@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    published_at: Optional[str] = None
    category: str = "未知"
    score: float = 0.0
    source_status: str = "ok"
    raw_text: str = ""
    uid: str = field(init=False)

    def __post_init__(self) -> None:
        base = f"{self.source}|{self.title}|{self.url}"
        self.uid = hashlib.sha1(base.encode("utf-8")).hexdigest()
        if not self.raw_text:
            self.raw_text = " ".join([self.title or "", self.summary or "", self.source or ""])


@dataclass
class SourceResult:
    source: str
    ok: bool
    items: List[NewsItem]
    note: str = ""


class FetchError(RuntimeError):
    pass


def build_ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def fetch_url(url: str, timeout: int = REQUEST_TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = build_ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            content_type = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read()
            return raw.decode(content_type, errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"fetch failed: {url} -> {exc}") from exc


def strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_summary(text: str, limit: int = 80) -> str:
    text = strip_html(text)
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_rfc822_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().isoformat(timespec="minutes")
    except Exception:  # noqa: BLE001
        return None


def score_and_category(text: str) -> tuple[str, float]:
    lowered = text.lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(3 if kw in lowered else 0 for kw in keywords)
        scores[category] = score
    category = max(scores, key=scores.get)
    if scores[category] == 0:
        category = "经济"
    return category, float(scores.get(category, 0))


def parse_feed(feed_text: str, source: str) -> List[NewsItem]:
    items: List[NewsItem] = []
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError as exc:
        raise FetchError(f"xml parse failed for {source}: {exc}") from exc

    channel_items = root.findall(".//item")
    if not channel_items:
        channel_items = root.findall("{http://www.w3.org/2005/Atom}entry")

    for node in channel_items[:MAX_ITEMS_PER_SOURCE]:
        title = _find_text(node, ["title", "{http://www.w3.org/2005/Atom}title"]) or "无标题"
        link = _find_text(node, ["link"]) or ""
        if not link:
            atom_link = node.find("{http://www.w3.org/2005/Atom}link")
            if atom_link is not None:
                link = atom_link.attrib.get("href", "")
        summary = (
            _find_text(node, ["description", "summary", "{http://www.w3.org/2005/Atom}summary"])
            or ""
        )
        published_at = parse_rfc822_date(
            _find_text(node, ["pubDate", "updated", "{http://www.w3.org/2005/Atom}updated"])
        )
        category, score = score_and_category(f"{title} {summary} {source}")
        items.append(
            NewsItem(
                title=clean_summary(title, 120),
                summary=clean_summary(summary, 100),
                url=link,
                source=source,
                published_at=published_at,
                category=category,
                score=score,
            )
        )
    return items


def _find_text(node: ET.Element, tags: Iterable[str]) -> Optional[str]:
    for tag in tags:
        child = node.find(tag)
        if child is not None:
            if child.text and child.text.strip():
                return child.text.strip()
            href = child.attrib.get("href")
            if href:
                return href.strip()
    return None


def fetch_feed_source(name: str, url: str) -> SourceResult:
    try:
        text = fetch_url(url)
        items = parse_feed(text, name)
        if not items:
            return SourceResult(name, False, [], "feed empty")
        return SourceResult(name, True, items)
    except FetchError as exc:
        return SourceResult(name, False, [], str(exc))


def fetch_search_source(name: str, query: str) -> SourceResult:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    return fetch_feed_source(name, url)


def build_source_results() -> List[SourceResult]:
    results: List[SourceResult] = []

    # International feeds: relatively stable.
    results.append(fetch_feed_source("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"))
    results.append(fetch_feed_source("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"))
    results.append(fetch_feed_source("FT World", "https://www.ft.com/world?format=rss"))

    # Search-based fallbacks for sites that often block direct scraping.
    results.append(fetch_search_source("36氪搜索", 'site:36kr.com AI OR 经济 OR 国际'))
    results.append(fetch_search_source("虎嗅搜索", 'site:huxiu.com AI OR 经济 OR 国际'))
    results.append(fetch_search_source("财联社搜索", 'site:cls.cn AI OR 经济 OR 国际'))
    results.append(fetch_search_source("界面搜索", 'site:jiemian.com AI OR 经济 OR 国际'))
    results.append(fetch_search_source("澎湃搜索", 'site:thepaper.cn AI OR 经济 OR 国际'))
    results.append(fetch_search_source("WSJ搜索", 'site:wsj.com AI OR economy OR world'))
    results.append(fetch_search_source("Bloomberg搜索", 'site:bloomberg.com AI OR economy OR world'))

    return results


def dedupe_items(items: Iterable[NewsItem]) -> List[NewsItem]:
    seen = {}
    for item in items:
        key = normalize_title(item.title)
        existing = seen.get(key)
        if existing is None or item.score > existing.score:
            seen[key] = item
    return list(seen.values())


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"https?://\S+", " ", title)
    title = re.sub(r"[^\w\u4e00-\u9fff]+", "", title)
    return title[:80]


def select_by_category(items: Iterable[NewsItem], per_category: int = DEFAULT_PER_CATEGORY) -> dict[str, List[NewsItem]]:
    buckets: dict[str, List[NewsItem]] = {c: [] for c in CATEGORIES}
    for item in sorted(items, key=lambda x: (x.category, -x.score, x.title)):
        if item.category in buckets:
            buckets[item.category].append(item)

    selected: dict[str, List[NewsItem]] = {c: [] for c in CATEGORIES}
    used_ids: set[str] = set()
    for category in CATEGORIES:
        for item in sorted(buckets[category], key=lambda x: (-x.score, x.title)):
            if item.uid in used_ids:
                continue
            selected[category].append(item)
            used_ids.add(item.uid)
            if len(selected[category]) >= per_category:
                break

    # backfill sparse categories from remaining pool
    remaining = [i for i in sorted(items, key=lambda x: (-x.score, x.title)) if i.uid not in used_ids]
    for category in CATEGORIES:
        while len(selected[category]) < min(2, per_category) and remaining:
            selected[category].append(remaining.pop(0))
    return selected


def choose_top_analysis(selected: dict[str, List[NewsItem]], count: int = TOP_ANALYSIS_COUNT) -> List[NewsItem]:
    pool = []
    for items in selected.values():
        pool.extend(items)
    pool = sorted(pool, key=lambda x: (-x.score, x.title))
    out: List[NewsItem] = []
    seen_categories: set[str] = set()
    for item in pool:
        if item.category not in seen_categories or len(out) < count:
            out.append(item)
            seen_categories.add(item.category)
        if len(out) >= count:
            break
    return out[:count]


def render_markdown(results: List[SourceResult], selected: dict[str, List[NewsItem]], top_items: List[NewsItem]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: List[str] = []
    lines.append(f"# 今日早报（{now}）")
    lines.append("")

    failed = [r for r in results if not r.ok]
    succeeded = [r.source for r in results if r.ok]
    if failed:
        lines.append("> 说明：部分主源不可达，已自动使用备用源补齐。")
        lines.append("")

    lines.append("## 一、简报")
    lines.append("")
    for category in CATEGORIES:
        lines.append(f"### {category}")
        items = selected.get(category, [])
        if not items:
            lines.append("- 暂无足够条目")
        for item in items:
            source = f"（{item.source}）" if item.source else ""
            summary = item.summary or "暂无摘要"
            lines.append(f"- {item.title} {source}：{summary}")
        lines.append("")

    lines.append("## 二、重点解读")
    lines.append("")
    if not top_items:
        lines.append("- 今日可用条目偏少，暂不展开重点解读。")
    for idx, item in enumerate(top_items, start=1):
        hint = ANALYSIS_HINTS.get(item.category, "这条值得继续跟踪其后续影响。")
        lines.append(f"**{idx}. {item.title}**")
        lines.append(f"- 来源：{item.source}")
        if item.url:
            lines.append(f"- 链接：{item.url}")
        lines.append(f"- 解读：{hint}")
        lines.append("")

    lines.append("## 三、对审计/当前工作的启发")
    lines.append("")
    used_hints = []
    for item in top_items:
        hint = AUDIT_HINTS.get(item.category)
        if hint and hint not in used_hints:
            used_hints.append(hint)
    if not used_hints:
        used_hints.append("今天更适合把新闻当作外部环境样本，关注其如何映射到预算、采购、运营和合规数据。")
    for hint in used_hints[:3]:
        lines.append(f"- {hint}")
    lines.append("")

    lines.append("## 四、来源状态")
    lines.append("")
    if succeeded:
        lines.append("- 成功：" + "、".join(succeeded))
    if failed:
        for result in failed:
            lines.append(f"- 失败：{result.source} — {result.note}")

    return "\n".join(lines).strip() + "\n"


def render_json(results: List[SourceResult], selected: dict[str, List[NewsItem]], top_items: List[NewsItem]) -> str:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": [dataclasses.asdict(r) for r in results],
        "selected": {k: [dataclasses.asdict(i) for i in v] for k, v in selected.items()},
        "top_items": [dataclasses.asdict(i) for i in top_items],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a mixed-source daily brief")
    parser.add_argument("--per-category", type=int, default=DEFAULT_PER_CATEGORY)
    parser.add_argument("--save", help="Optional path to save markdown output")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    args = parser.parse_args(argv)

    results = build_source_results()
    all_items: List[NewsItem] = []
    for result in results:
        all_items.extend(result.items)

    items = dedupe_items(all_items)
    for item in items:
        if item.category not in CATEGORIES:
            item.category, item.score = score_and_category(item.raw_text)

    selected = select_by_category(items, per_category=args.per_category)
    top_items = choose_top_analysis(selected)

    output = render_json(results, selected, top_items) if args.json else render_markdown(results, selected, top_items)

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
