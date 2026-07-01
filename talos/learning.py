"""Learning-Loop v1: Selbstreflexion am Session-Ende.

Das Modell beantwortet drei Fragen über die abgelaufene Session; brauchbare
Lektionen landen in lessons.md und fließen in jede zukünftige Session ein.
Nutzt das kleine Modell, falls konfiguriert (Token-Effizienz).
"""

from __future__ import annotations

import json

from .agent import Agent

REFLECT_PROMPT = """Reflektiere über die bisherige Konversation:
1. Was hat gut funktioniert?
2. Welche Tool-Aufrufe oder Vorgehen sind fehlgeschlagen — und warum?
3. Was solltest du dir für zukünftige Sessions merken?

Antworte NUR mit JSON: {"lessons": ["...", "..."]}
Nur konkrete, wiederverwendbare Lektionen aufnehmen ("bei X immer Y prüfen").
Keine Lektion ist okay: {"lessons": []}"""


def reflect(agent: Agent) -> list[str]:
    """Führt die Reflexion aus und speichert neue Lektionen. Gibt sie zurück."""
    if len(agent.messages) < 2:
        return []
    msg = agent.llm.chat(
        agent.messages + [{"role": "user", "content": REFLECT_PROMPT}], small=True
    )
    try:
        raw = (msg.content or "").strip()
        raw = raw[raw.index("{") : raw.rindex("}") + 1]
        lessons = json.loads(raw).get("lessons", [])
    except (ValueError, json.JSONDecodeError):
        return []
    existing = agent.memory.lessons()
    new = [l for l in lessons if isinstance(l, str) and l.strip() and l.strip() not in existing]
    for lesson in new:
        agent.memory.add_lesson(lesson)
    return new
