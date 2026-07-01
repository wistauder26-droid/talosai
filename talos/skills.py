"""Skill-System: wiederverwendbare Anleitungen, die der Agent selbst erstellt.

Ein Skill ist eine Markdown-Datei mit Schritt-für-Schritt-Wissen für eine
Aufgabenart ("Wie recherchiere ich Flugpreise", "Wie erstelle ich Backups").
Der Index steht im System-Prompt; den vollen Skill lädt der Agent per Tool,
wenn eine passende Aufgabe kommt. Skills werden bei Nutzung verbessert.
"""

from __future__ import annotations

import re
from pathlib import Path


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-") or "skill"


class Skills:
    def __init__(self, skills_dir: Path):
        self.dir = skills_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def index(self) -> str:
        lines = []
        for path in sorted(self.dir.glob("*.md")):
            first = path.read_text().splitlines()
            desc = first[0].removeprefix("# ").strip() if first else ""
            lines.append(f"- {path.stem} — {desc}")
        return "\n".join(lines)

    def save(self, name: str, description: str, content: str) -> str:
        slug = _slug(name)
        path = self.dir / f"{slug}.md"
        existed = path.exists()
        path.write_text(f"# {description.strip()}\n\n{content.strip()}\n")
        return f"Skill {'aktualisiert' if existed else 'erstellt'}: {slug}"

    def read(self, name: str) -> str:
        path = self.dir / f"{_slug(name)}.md"
        if not path.exists():
            hits = [p.stem for p in self.dir.glob("*.md") if _slug(name) in p.stem]
            return f"Skill nicht gefunden. Ähnliche: {hits}" if hits else "Skill nicht gefunden."
        return path.read_text()
