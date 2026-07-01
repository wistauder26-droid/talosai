"""Der Agent-Loop: Nachricht → LLM → Tool-Calls ausführen → Antwort."""

from __future__ import annotations

from .config import Config
from .llm import LLM
from .memory import Memory
from .skills import Skills
from .tools import SUBAGENT_TOOLS, execute_tool, parse_args, tool_defs

SYSTEM_PROMPT = """Du bist Talos, ein persönlicher AI-Agent.

Grundregeln (nicht verhandelbar):
1. EHRLICHKEIT: Behaupte nur, was durch Tool-Ergebnisse, dein Memory oder \
gesichertes Wissen gedeckt ist. Wenn du etwas nicht weißt oder ein Tool \
fehlschlug, sage das offen. Erfinde niemals Fakten, Quellen oder Ergebnisse. \
Bei Fragen zu aktuellen oder überprüfbaren Fakten: erst web_search, dann antworten.
2. LERNEN: Speichere wichtige Fakten über den Nutzer und laufende Projekte \
mit memory_save. Nach komplexen, gelungenen Aufgaben: Erstelle mit skill_save \
eine wiederverwendbare Anleitung. Existiert für eine Aufgabe schon ein Skill, \
lade ihn ZUERST mit skill_read — und verbessere ihn, wenn du dazulernst.
3. EFFIZIENZ: Antworte knapp. Nutze Tools gezielt statt zu raten. Delegiere \
umfangreiche Recherchen mit delegate an einen Subagenten, damit dein Kontext \
schlank bleibt.

## Dein Memory-Index
{memory_index}

## Lektionen aus früheren Sessions
{lessons}

## Deine Skills (per skill_read laden)
{skills_index}
"""

SUBAGENT_PROMPT = """Du bist ein Subagent von Talos. Erledige exakt die gestellte \
Teilaufgabe mit deinen Tools und liefere ein knappes, vollständiges Ergebnis mit \
Quellenangaben (URLs), falls du recherchiert hast. Behaupte nur, was durch \
Tool-Ergebnisse gedeckt ist. Keine Rückfragen — arbeite mit dem, was du hast."""


class Agent:
    def __init__(
        self,
        cfg: Config | None = None,
        session_id: str = "default",
        allowed_tools: set[str] | None = None,
        system_prompt: str | None = None,
    ):
        self.cfg = cfg or Config()
        self.llm = LLM(self.cfg)
        self.memory = Memory(self.cfg.data_dir / "memory")
        self.skills = Skills(self.cfg.data_dir / "skills")
        self.session_id = session_id
        self.messages: list[dict] = []
        self.allowed_tools = allowed_tools
        self.system_prompt = system_prompt
        # optionale Callbacks: on_tool(name, args) für Live-Anzeige,
        # confirm(command) -> bool für gefährliche Shell-Befehle
        self.on_tool = None
        self.confirm = None

    def _system(self) -> dict:
        if self.system_prompt:
            return {"role": "system", "content": self.system_prompt}
        return {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                memory_index=self.memory.index() or "(noch leer)",
                lessons=self.memory.lessons() or "(noch keine)",
                skills_index=self.skills.index() or "(noch keine)",
            ),
        }

    def spawn_subagent(self, task: str) -> str:
        """Führt eine Teilaufgabe in einem frischen, kleinen Kontext aus."""
        sub = Agent(
            self.cfg,
            session_id=f"{self.session_id}-sub",
            allowed_tools=SUBAGENT_TOOLS,
            system_prompt=SUBAGENT_PROMPT,
        )
        sub.on_tool = self.on_tool
        # Subagenten bestätigen nichts selbst — gefährliche Befehle werden abgelehnt
        return sub.run(task, verify_answer=False)

    def run(self, user_message: str, verify_answer: bool | None = None) -> str:
        """Verarbeitet eine Nutzernachricht bis zur finalen Antwort."""
        self.messages.append({"role": "user", "content": user_message})
        defs = tool_defs(self.allowed_tools)
        used_tools = False
        for _ in range(self.cfg.max_tool_rounds):
            msg = self.llm.chat([self._system()] + self.messages, tools=defs)
            if not msg.tool_calls:
                text = msg.content or ""
                self.messages.append({"role": "assistant", "content": text})
                should_verify = self.cfg.verify if verify_answer is None else verify_answer
                if should_verify and used_tools:
                    from .verifier import verify
                    text = verify(self, text)
                return text
            used_tools = True
            self.messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                }
            )
            for tc in msg.tool_calls:
                args = parse_args(tc.function.arguments)
                if self.on_tool:
                    self.on_tool(tc.function.name, args)
                result = execute_tool(tc.function.name, args, self)
                self.messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
        return "Abbruch: maximale Tool-Runden erreicht. Bitte Aufgabe kleiner formulieren."
