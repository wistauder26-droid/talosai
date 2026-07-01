"""Datei-basiertes Memory.

- MEMORY.md: Index, eine Zeile pro Fakt — wird in jeden System-Prompt geladen.
- <slug>.md: einzelne Fakten, per Tool nachladbar.
- lessons.md: Erkenntnisse aus der Session-Reflexion (Learning-Loop).
"""

from __future__ import annotations

import re
from pathlib import Path


class Memory:
    def __init__(self, memory_dir: Path):
        self.dir = memory_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.dir / "MEMORY.md"
        self.lessons_file = self.dir / "lessons.md"

    def index(self) -> str:
        return self.index_file.read_text() if self.index_file.exists() else ""

    def lessons(self) -> str:
        return self.lessons_file.read_text() if self.lessons_file.exists() else ""

    def save(self, name: str, content: str, hook: str) -> str:
        """Fakt speichern und im Index verlinken. Existiert der Name, wird überschrieben."""
        slug = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-") or "memo"
        path = self.dir / f"{slug}.md"
        existed = path.exists()
        path.write_text(content)
        line = f"- [{name}]({slug}.md) — {hook}\n"
        idx = self.index()
        if f"({slug}.md)" in idx:
            idx = re.sub(rf"^- \[.*?\]\({re.escape(slug)}\.md\).*$", line.rstrip(), idx, flags=re.M)
            self.index_file.write_text(idx)
        else:
            self.index_file.write_text(idx + line)
        return f"{'Aktualisiert' if existed else 'Gespeichert'}: {slug}.md"

    def read(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
        path = self.dir / f"{slug}.md"
        if not path.exists():
            hits = [p.name for p in self.dir.glob("*.md") if slug in p.name]
            return f"Nicht gefunden. Ähnliche Dateien: {hits}" if hits else "Nicht gefunden."
        return path.read_text()

    def add_lesson(self, lesson: str) -> None:
        prev = self.lessons()
        self.lessons_file.write_text(prev + f"- {lesson.strip()}\n")
