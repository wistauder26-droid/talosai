"""Web-Tools: Suche (DuckDuckGo) und Seiten-Abruf mit Text-Extraktion."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import httpx


def web_search(query: str, max_results: int = 6) -> str:
    from ddgs import DDGS

    results = list(DDGS().text(query, max_results=max_results))
    if not results:
        return "Keine Treffer."
    return "\n\n".join(
        f"[{i+1}] {r['title']}\n{r['href']}\n{r['body']}" for i, r in enumerate(results)
    )


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip())


def web_fetch(url: str, max_chars: int = 6000) -> str:
    resp = httpx.get(
        url,
        follow_redirects=True,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 (TalosAI)"},
    )
    resp.raise_for_status()
    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype:
        return resp.text[:max_chars]
    parser = _TextExtractor()
    parser.feed(resp.text)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(parser.parts))
    return text[:max_chars] or "(kein Text extrahierbar)"
