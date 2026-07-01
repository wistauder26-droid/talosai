# TalosAI — Architektur

```
┌─────────────── iOS-App (SwiftUI) ───────────────┐
│ Chat · Voice · Push · Widgets · StoreKit-Abo    │
└───────────────────────┬─────────────────────────┘
                        │ HTTPS / SSE-Streaming
┌───────────────────────▼─────────────────────────┐
│ API-Server (FastAPI)                            │
│ Auth (Sign in with Apple) · Rate-Limits ·       │
│ Usage-Tracking · Abo-Validierung                │
└───────────────────────┬─────────────────────────┘
┌───────────────────────▼─────────────────────────┐
│ Agent-Runtime (Claude Agent SDK, pro Nutzer)    │
│                                                 │
│  Orchestrator (starkes Modell)                  │
│   ├── Recherche-Subagent   (Haiku, Web-Tools)   │
│   ├── Schreib-Subagent     (Sonnet)             │
│   └── Aufgaben-Subagent    (Haiku, Kalender…)   │
│                                                 │
│  Learning-Loop:                                 │
│   Session-Ende → Reflexion → Memory/Skill-Datei │
│   Fehler-Log → fließt in nächsten System-Prompt │
└───────────────────────┬─────────────────────────┘
┌───────────────────────▼─────────────────────────┐
│ Storage: Postgres (Nutzer, Sessions, Usage)     │
│ + Memory-Dateien pro Nutzer (verschlüsselt)     │
└─────────────────────────────────────────────────┘
```

## Entscheidungen

- **Claude Agent SDK statt Eigenbau**: Agent-Loop, Tool-Handling,
  Subagents, Kontext-Kompaktierung und Prompt-Caching sind gelöst —
  wir bauen nur die Schicht darüber (Memory, Learning, Produkt).
- **Modell-Routing für Token-Effizienz**: Orchestrator entscheidet pro
  Schritt das billigste ausreichende Modell. Prompt-Caching überall.
- **Ehrlichkeit als Verifier**: Kritische Antworten laufen durch einen
  billigen Check "Ist jede Behauptung durch Tool-Output gedeckt?" —
  sonst wird umformuliert oder Unsicherheit ausgewiesen.
- **Memory als Dateien, nicht Vektor-DB (v1)**: Ein MEMORY-Index +
  einzelne Fakten-Dateien, vom Agenten selbst kuratiert (Muster von
  Hermes Agent, MIT). Vektor-Suche erst, wenn nötig.
- **Kein Code aus Odysseus übernehmen** (AGPL → würde uns zwingen,
  alles offenzulegen). Hermes/OpenClaw (MIT) sind als Vorlage okay.

## Repo-Struktur (Ziel)

```
TalosAI/
├── agent/          # Agent-Core: Orchestrator, Subagents, Tools
│   ├── memory/     # Memory- & Learning-Loop
│   └── skills/     # selbst erzeugte + mitgelieferte Skills
├── server/         # FastAPI: Auth, Streaming, Billing
├── ios/            # SwiftUI-App (Xcode-Projekt)
└── docs/
```
