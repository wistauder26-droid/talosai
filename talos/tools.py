"""Tool-Registry: Definitionen (OpenAI-Format) + Ausführung.

Tools erhalten den Agenten als Kontext (Memory, Config, Subagents).
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

# Befehle, die ohne explizite Bestätigung nicht ausgeführt werden
DANGEROUS = re.compile(
    r"\brm\s+-[rf]|\bsudo\b|\bmkfs|\bdd\s+if=|\bshutdown\b|\breboot\b|>\s*/dev/"
    r"|\bkillall\b|curl[^|]*\|\s*(ba)?sh|\bchmod\s+-R|\bdiskutil\b"
)

TOOL_DEFS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "memory_save",
            "description": "Speichert einen Fakt dauerhaft im Memory (überlebt Sessions). Nutze das für alles, was du dir über den Nutzer oder laufende Projekte merken sollst.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "kurzer Name, z.B. 'nutzer-zeitzone'"},
                    "content": {"type": "string", "description": "der vollständige Fakt"},
                    "hook": {"type": "string", "description": "Ein-Zeilen-Zusammenfassung für den Index"},
                },
                "required": ["name", "content", "hook"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_read",
            "description": "Liest einen gespeicherten Fakt aus dem Memory (Namen stehen im Memory-Index im System-Prompt).",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Führt einen Shell-Befehl auf dem Host aus und liefert stdout/stderr. Für Datei-Operationen, Berechnungen usw. Gefährliche Befehle erfordern Nutzer-Bestätigung.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Websuche (DuckDuckGo). Nutze das für aktuelle Informationen, Fakten und alles außerhalb deines Wissens. Liefert Titel, URL und Snippet.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Ruft eine URL ab und liefert den extrahierten Text der Seite. Nutze das nach web_search, um Quellen wirklich zu lesen statt nur Snippets zu zitieren.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_save",
            "description": "Erstellt oder verbessert einen wiederverwendbaren Skill (Schritt-für-Schritt-Anleitung für eine Aufgabenart). Nutze das nach komplexen, gelungenen Aufgaben — und aktualisiere einen Skill, wenn du bei der Nutzung etwas Besseres gelernt hast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "kurzer Name, z.B. 'flugpreise-recherchieren'"},
                    "description": {"type": "string", "description": "Ein-Zeilen-Beschreibung, wofür der Skill ist"},
                    "content": {"type": "string", "description": "die vollständige Anleitung (Markdown, Schritte + Stolperfallen)"},
                },
                "required": ["name", "description", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_read",
            "description": "Lädt einen Skill (Namen stehen im Skill-Index im System-Prompt). Nutze das IMMER, bevor du eine Aufgabe angehst, für die ein passender Skill existiert.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate",
            "description": "Delegiert eine abgegrenzte Teilaufgabe an einen Subagenten mit frischem, kleinem Kontext (token-effizient). Gut für Recherchen oder Analysen, deren Zwischenschritte du nicht brauchst — du bekommst nur das Endergebnis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "präzise, in sich vollständige Aufgabenbeschreibung"},
                },
                "required": ["task"],
            },
        },
    },
]

SUBAGENT_TOOLS = {"shell", "web_search", "web_fetch", "memory_read", "skill_read"}


def tool_defs(allowed: set[str] | None = None) -> list[dict[str, Any]]:
    if allowed is None:
        return TOOL_DEFS
    return [t for t in TOOL_DEFS if t["function"]["name"] in allowed]


def execute_tool(name: str, args: dict[str, Any], agent) -> str:
    try:
        if name.startswith("mcp__"):
            if agent.mcp is None:
                return "Kein MCP-Server verbunden."
            return agent.mcp.call(name, args)
        if name == "memory_save":
            return agent.memory.save(args["name"], args["content"], args["hook"])
        if name == "memory_read":
            return agent.memory.read(args["name"])
        if name == "skill_save":
            return agent.skills.save(args["name"], args["description"], args["content"])
        if name == "skill_read":
            return agent.skills.read(args["name"])
        if name == "shell":
            cmd = args["command"]
            if DANGEROUS.search(cmd):
                confirm = getattr(agent, "confirm", None)
                if confirm is None or not confirm(cmd):
                    return "ABGELEHNT: Dieser Befehl gilt als gefährlich und wurde vom Nutzer nicht bestätigt."
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
            out = (proc.stdout + proc.stderr).strip()
            return out[:8000] if out else f"(kein Output, exit code {proc.returncode})"
        if name == "web_search":
            from .web import web_search
            return web_search(args["query"])
        if name == "web_fetch":
            from .web import web_fetch
            return web_fetch(args["url"])
        if name == "delegate":
            return agent.spawn_subagent(args["task"])
        return f"Unbekanntes Tool: {name}"
    except Exception as e:  # Fehler gehen als Text zurück ans Modell — daraus lernt es
        return f"FEHLER: {type(e).__name__}: {e}"


def parse_args(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
