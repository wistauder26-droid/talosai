"""Tool-Registry: Definitionen (OpenAI-Format) + Ausführung."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from .memory import Memory

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
            "description": "Führt einen Shell-Befehl auf dem Host aus und liefert stdout/stderr. Nutze das für Datei-Operationen, Recherche mit curl, Berechnungen usw.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


def execute_tool(name: str, args: dict[str, Any], memory: Memory) -> str:
    try:
        if name == "memory_save":
            return memory.save(args["name"], args["content"], args["hook"])
        if name == "memory_read":
            return memory.read(args["name"])
        if name == "shell":
            proc = subprocess.run(
                args["command"], shell=True, capture_output=True, text=True, timeout=120
            )
            out = (proc.stdout + proc.stderr).strip()
            return out[:8000] if out else f"(kein Output, exit code {proc.returncode})"
        return f"Unbekanntes Tool: {name}"
    except Exception as e:  # Fehler gehen als Text zurück ans Modell — daraus lernt es
        return f"FEHLER: {type(e).__name__}: {e}"


def parse_args(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
