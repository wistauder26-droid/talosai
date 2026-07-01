"""Verifier: prüft, ob die Antwort durch Tool-Ergebnisse gedeckt ist.

Läuft nach Turns, in denen Tools benutzt wurden. Ein günstiges Modell prüft
jede Faktenbehauptung gegen die Tool-Outputs; bei ungedeckten Behauptungen
muss das Hauptmodell einmal korrigieren. Kern des "nicht lügen"-Prinzips.
"""

from __future__ import annotations

import json

VERIFY_PROMPT = """Du bist ein strenger Faktenprüfer. Unten eine Antwort eines \
AI-Agenten und die Tool-Ergebnisse, auf denen sie basieren muss.

Prüfe: Ist jede konkrete Faktenbehauptung in der Antwort durch die \
Tool-Ergebnisse gedeckt? Meinungen, Vorschläge und Allgemeinwissen zählen nicht.

Antworte NUR mit JSON:
{{"ok": true}} — wenn alles gedeckt ist
{{"ok": false, "probleme": ["Behauptung X ist nicht durch Tool-Output belegt", ...]}}

## Tool-Ergebnisse
{evidence}

## Antwort des Agenten
{answer}"""


def _tool_evidence(messages: list[dict]) -> str:
    """Sammelt die Tool-Outputs des letzten Turns (seit der letzten User-Frage)."""
    evidence = []
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            break
        if msg.get("role") == "tool":
            evidence.append(str(msg.get("content", ""))[:3000])
    return "\n---\n".join(reversed(evidence))


def verify(agent, answer: str) -> str:
    """Gibt die (ggf. korrigierte) Antwort zurück."""
    evidence = _tool_evidence(agent.messages)
    if not evidence or not answer.strip():
        return answer
    msg = agent.llm.chat(
        [{"role": "user", "content": VERIFY_PROMPT.format(evidence=evidence, answer=answer)}],
        small=True,
    )
    try:
        raw = (msg.content or "").strip()
        raw = raw[raw.index("{") : raw.rindex("}") + 1]
        result = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return answer
    problems = result.get("probleme") or []
    if result.get("ok", True) or not problems:
        return answer
    # Eine Korrektur-Runde beim Hauptmodell — ohne Tools, nur umformulieren
    agent.messages.append(
        {
            "role": "user",
            "content": "[Verifier] Folgende Behauptungen deiner Antwort sind nicht durch "
            "Tool-Ergebnisse gedeckt:\n- " + "\n- ".join(problems) +
            "\nKorrigiere deine Antwort: Entferne oder kennzeichne Ungedecktes als unsicher. "
            "Gib nur die korrigierte Antwort aus.",
        }
    )
    revised = agent.llm.chat([agent._system()] + agent.messages)
    text = revised.content or answer
    agent.messages.append({"role": "assistant", "content": text})
    return text
