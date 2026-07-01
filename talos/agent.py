"""Der Agent-Loop: Nachricht → LLM → Tool-Calls ausführen → Antwort."""

from __future__ import annotations

from .config import Config
from .llm import LLM
from .memory import Memory
from .tools import TOOL_DEFS, execute_tool, parse_args

SYSTEM_PROMPT = """Du bist Talos, ein persönlicher AI-Agent.

Grundregeln (nicht verhandelbar):
1. EHRLICHKEIT: Behaupte nur, was durch Tool-Ergebnisse, dein Memory oder \
gesichertes Wissen gedeckt ist. Wenn du etwas nicht weißt oder ein Tool \
fehlschlug, sage das offen. Erfinde niemals Fakten, Quellen oder Ergebnisse.
2. LERNEN: Speichere wichtige Fakten über den Nutzer und laufende Projekte \
mit memory_save. Wenn ein Vorgehen fehlschlägt und du die Ursache erkennst, \
merke dir die Lektion.
3. EFFIZIENZ: Antworte knapp. Nutze Tools gezielt statt zu raten.

## Dein Memory-Index
{memory_index}

## Lektionen aus früheren Sessions
{lessons}
"""


class Agent:
    def __init__(self, cfg: Config | None = None, session_id: str = "default"):
        self.cfg = cfg or Config()
        self.llm = LLM(self.cfg)
        self.memory = Memory(self.cfg.data_dir / "memory")
        self.session_id = session_id
        self.messages: list[dict] = []

    def _system(self) -> dict:
        return {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                memory_index=self.memory.index() or "(noch leer)",
                lessons=self.memory.lessons() or "(noch keine)",
            ),
        }

    def run(self, user_message: str) -> str:
        """Verarbeitet eine Nutzernachricht bis zur finalen Antwort."""
        self.messages.append({"role": "user", "content": user_message})
        for _ in range(self.cfg.max_tool_rounds):
            msg = self.llm.chat([self._system()] + self.messages, tools=TOOL_DEFS)
            if not msg.tool_calls:
                text = msg.content or ""
                self.messages.append({"role": "assistant", "content": text})
                return text
            self.messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                }
            )
            for tc in msg.tool_calls:
                result = execute_tool(
                    tc.function.name, parse_args(tc.function.arguments), self.memory
                )
                self.messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
        return "Abbruch: maximale Tool-Runden erreicht. Bitte Aufgabe kleiner formulieren."
