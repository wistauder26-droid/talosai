# TalosAI — Architektur (Phase 1)

```
┌── Kanäle ─────────────────────────────────────────┐
│  Telegram-Gateway        CLI (lokal)              │
└───────────────┬───────────────┬───────────────────┘
                ▼               ▼
┌───────────────────────────────────────────────────┐
│ Agent-Core (talos/agent.py)                       │
│  Agent-Loop: Prompt → LLM → Tool-Calls → Antwort  │
│  Ehrlichkeits-Regeln im System-Prompt             │
│  Tools: memory, files, shell                      │
├───────────────────────────────────────────────────┤
│ Memory + Learning (talos/memory.py, learning.py)  │
│  memory/MEMORY.md   Index, in jeden Prompt geladen│
│  memory/*.md        einzelne Fakten               │
│  memory/lessons.md  Erkenntnisse aus Reflexion    │
│  Session-Ende → Selbstreflexion → Lessons         │
├───────────────────────────────────────────────────┤
│ LLM-Layer (talos/llm.py) — provider-agnostisch    │
│  OpenAI-kompatible API: vLLM · Ollama · OpenRouter│
│  · OpenAI · Anthropic (via Kompatibilitäts-API)   │
│  Konfiguration über .env: BASE_URL, MODEL, KEY    │
└───────────────────────────────────────────────────┘
```

## Entscheidungen

- **Eigener schlanker Agent-Loop statt Claude Agent SDK** — das SDK ist
  Claude-gebunden; Provider-Freiheit (vLLM lokal!) ist Kernversprechen.
- **OpenAI-kompatibles Wire-Format** als kleinster gemeinsamer Nenner:
  vLLM, Ollama, OpenRouter und OpenAI sprechen es nativ, Anthropic über
  die Kompatibilitäts-Schicht. Ein Client, alle Provider.
- **Memory als Markdown-Dateien**, vom Agenten selbst kuratiert
  (Muster: Hermes Agent, MIT). Index (`MEMORY.md`) kommt in jeden
  System-Prompt; Details werden per Tool nachgeladen. Vektor-DB erst,
  wenn Dateien nicht mehr reichen.
- **Learning-Loop v1**: Am Session-Ende beantwortet das Modell drei
  Fragen (Was lief gut? Was schlug fehl und warum? Was sollte ich mir
  merken?) und schreibt das Ergebnis nach `lessons.md` — die in jede
  neue Session eingespeist wird.
- **AGPL-3.0** für die Basis. Kein Code aus Odysseus (ebenfalls AGPL,
  aber fremdes Copyright); Konzepte aus Hermes/OpenClaw (MIT) okay.

## Repo-Struktur

```
TalosAI/
├── talos/
│   ├── config.py        # .env-Konfiguration
│   ├── llm.py           # provider-agnostischer LLM-Client
│   ├── agent.py         # Agent-Loop + System-Prompt
│   ├── tools.py         # Tool-Registry + Implementierungen
│   ├── memory.py        # Memory-Dateien + Index
│   ├── learning.py      # Session-Reflexion → Lessons
│   ├── cli.py           # lokales Chat-REPL
│   └── gateway/
│       └── telegram.py  # Telegram-Bot
├── docker-compose.yml   # Talos + optional vLLM/Ollama
├── pyproject.toml
└── .env.example
```
