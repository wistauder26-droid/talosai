# TalosAI — Vision

**Ein selbstlernender, ehrlicher AI-Agent — open source, self-hostbar,
erreichbar über Telegram.**

## Strategie: Open Core

- **Basis auf GitHub (AGPL-3.0)**: Agent-Core, Telegram-Gateway,
  Memory- und Learning-System, Self-Hosting via Docker. Jeder kann es
  kostenlos selbst betreiben — mit vLLM/Ollama komplett lokal oder mit
  einem API-Provider.
- **Geld verdienen** mit dem, was Self-Hoster nicht wollen/können:
  1. **TalosAI Cloud** — gehostete Version für Nicht-Techies (Abo).
  2. **iOS-App** (Produkt Nr. 2, Apple-Design) — Premium-Frontend für
     Cloud-Nutzer, Abo über den App Store.
- AGPL schützt uns: Niemand kann TalosAI als Closed-Source-Cloud-Dienst
  verkaufen; wir als Rechteinhaber dürfen unsere Cloud-Version frei
  betreiben.

## Konkurrenz (Stand Juli 2026)

| | Odysseus | OpenClaw | Hermes Agent | **TalosAI** |
|---|---|---|---|---|
| Learning-Loop | teilweise | nein | ja | **ja, Kernfeature** |
| Ehrlichkeit/Verifier | nein | nein | nein | **ja, Kernfeature** |
| Lokal (vLLM/Ollama) | ja | teilweise | ja | **ja** |
| Telegram | nein | ja | ja | **ja, erster Kanal** |
| Geschäftsmodell | keins | Sponsoren | keins | **Cloud + iOS-Abo** |

Differenzierung: nicht Feature-Breite (kein E-Mail-Client, kein
Dokumenten-Editor wie Odysseus), sondern **Lernfähigkeit + Ehrlichkeit
+ Token-Effizienz** — und später das erste polierte Consumer-Frontend.

## Kernprinzipien

1. **Selbstlernend** — Nach jeder Session reflektiert der Agent und
   speichert Erkenntnisse als Memory-Dateien; sie fließen in zukünftige
   System-Prompts ein.
2. **Aus Fehlern lernen** — Fehlgeschlagene Tool-Calls und Nutzer-
   Korrekturen landen als "Lessons" im Memory.
3. **Nicht lügen** — Behauptungen brauchen eine Quelle (Tool-Ergebnis,
   Memory); sonst sagt der Agent "weiß ich nicht". Verifier-Schritt für
   kritische Antworten.
4. **Token-effizient** — Modell-Routing (kleines Modell für einfache
   Schritte), knappe Kontexte, Kompaktierung langer Sessions.
5. **Multi-Agent** — Orchestrator + spezialisierte Subagents (ab v2).
6. **Provider-agnostisch** — OpenAI-kompatible Schnittstelle: vLLM,
   Ollama, OpenRouter, Anthropic/OpenAI — Wechsel per Config, kein
   Lock-in.

## Roadmap

- **Phase 1: Open-Source-Basis** — Agent-Core, LLM-Layer, Memory +
  Learning-Loop v1, Telegram-Gateway, CLI, Docker. → GitHub-Launch.
- **Phase 2: Reife** — Multi-Agent, Verifier, Skills, Web-Tools,
  Community aufbauen (Stars, Contributors).
- **Phase 3: TalosAI Cloud** — gehostete Version, Abo-Billing.
- **Phase 4: iOS-App** — SwiftUI, Apple HIG, App-Store-Abo.
