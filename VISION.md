# TalosAI — Vision

**Ein selbstlernender persönlicher AI-Agent mit erstklassiger nativer iOS-App.**

## Warum TalosAI gewinnt

Analyse der Konkurrenz (Stand Juli 2026):

| | Odysseus | OpenClaw | Hermes Agent | **TalosAI** |
|---|---|---|---|---|
| Zielgruppe | Self-Hosting-Techies | Techies (CLI-Setup) | Techies (Terminal) | **Normale Nutzer (iPhone)** |
| Selbstlernend | teilweise (Memory) | nein | ja (Skill-Loop) | **ja, Kernfeature** |
| Native iOS-App | nein | rudimentär | nein | **ja, Apple-Design** |
| Monetarisierung | keine (AGPL) | keine (Sponsoren) | keine (Forschung) | **App-Store-Abo** |
| Token-Effizienz | – | – | Trajectory-Compression | **Kernprinzip** |

Die Lücke: Alle drei sind Open-Source-Werkzeuge für Entwickler. Keiner
verkauft ein poliertes Consumer-Produkt. TalosAI muss nicht technisch in
allem überlegen sein — es muss das erste sein, das sich wie ein
Apple-Produkt anfühlt.

## Kernprinzipien

1. **Selbstlernend** — Nach jeder abgeschlossenen Aufgabe reflektiert der
   Agent: Was hat funktioniert, was nicht? Erkenntnisse werden als
   Memory-Dateien und wiederverwendbare Skills gespeichert (Vorbild:
   Hermes-Agent-Learning-Loop, MIT-lizenziert — Konzepte übernehmbar).
2. **Aus Fehlern lernen** — Fehlgeschlagene Tool-Calls und Nutzer-
   Korrekturen werden protokolliert; eine Feedback-Datenbank fließt in
   den System-Prompt zukünftiger Sessions ein.
3. **Nicht lügen** — Jede Faktenaussage braucht eine Quelle (Tool-Ergebnis,
   Memory, Web). Ohne Quelle sagt der Agent "weiß ich nicht". Erzwungen
   durch Prompt-Design + einen Verifier-Schritt bei kritischen Antworten.
4. **Token-effizient** — Prompt-Caching, Kontext-Kompaktierung,
   Modell-Routing (Haiku für einfache Schritte, Fable/Opus für Planung),
   Subagents mit eng geschnittenem Kontext statt einem fetten Hauptkontext.
5. **Multi-Agent** — Ein Orchestrator plant, spezialisierte Subagents
   (Recherche, Code, Schreiben, Kalender/Mail) führen aus.

## Produkt

- **Backend**: Agent-Server (Python, Claude Agent SDK), läuft in der Cloud.
  Pro Nutzer ein isolierter Agent mit eigenem Memory.
- **iOS-App**: SwiftUI, Apple Human Interface Guidelines. Chat, Sprach-
  eingabe, Push bei fertigen Aufgaben, Widgets, Siri-Shortcuts.
- **Monetarisierung**: Freemium-Abo (StoreKit 2). Free: begrenzte
  Nachrichten/Monat auf kleinem Modell. Pro (~9,99 €/Monat): starkes
  Modell, unbegrenztes Memory, Automationen. Marge über Modell-Routing
  und Caching steuern.

## Roadmap

- **Phase 1 (Wochen 1–4): Agent-Core** — Orchestrator + 2 Subagents,
  Tool-Set (Web, Dateien, Kalender), Memory-System, Learning-Loop v1.
  Testbar über CLI.
- **Phase 2 (Wochen 5–8): Server + API** — FastAPI, Auth, Streaming
  (SSE), Per-User-Isolation, Usage-Tracking/Billing-Grundlage.
- **Phase 3 (Wochen 9–14): iOS-App** — SwiftUI-App gegen die API,
  TestFlight-Beta.
- **Phase 4 (Wochen 15+): Launch** — App-Store-Review, Abo live,
  Feedback-Loop mit echten Nutzern.
