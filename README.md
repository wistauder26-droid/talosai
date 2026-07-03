# TalosAI

**Ein selbstlernender, ehrlicher AI-Agent — open source, self-hostbar,
erreichbar über Telegram oder das Terminal.**

- 🧠 **Selbstlernend** — reflektiert nach jeder Session, speichert Lektionen
  und Fakten in einem datei-basierten Memory, das jede neue Session prägt.
- 🤝 **Ehrlich** — behauptet nur, was durch Tool-Ergebnisse oder Memory
  gedeckt ist; sagt sonst "weiß ich nicht".
- 🔌 **Provider-frei** — jede OpenAI-kompatible API: vLLM oder Ollama
  (100 % lokal), OpenRouter, OpenAI, Anthropic. Wechsel per `.env`.
- 📱 **Telegram-first** — dein Agent in der Hosentasche, ohne App-Installation.

## Quick Start

```bash
git clone <repo-url> && cd TalosAI
cp .env.example .env        # Provider + Modell eintragen
pip install .
talos                        # Chat im Terminal
talos-web                    # lokales Dashboard: http://localhost:7777
talos-telegram               # oder als Telegram-Bot
```

### Native Mac-App

Ein eigenes Programmfenster (kein Browser), per Doppelklick startbar:

```bash
uv pip install -p .venv/bin/python '.[app]'   # pywebview
bash scripts/build-mac-app.sh                 # erzeugt TalosAI.app
```

Danach `TalosAI.app` in den Ordner **Programme** ziehen. Alternativ direkt
`talos-app` starten. Auf Linux/Windows funktioniert `talos-app` ebenso
(pywebview nutzt das jeweilige System-WebView).

### Docker

```bash
cp .env.example .env
docker compose up -d --build
```

### 100 % lokal (Ollama)

```bash
ollama pull qwen3:14b
# .env: TALOS_BASE_URL=http://localhost:11434/v1, TALOS_MODEL=qwen3:14b
talos
```

## Wie das Lernen funktioniert

1. Während der Session speichert der Agent wichtige Fakten per
   `memory_save` (Index in `data/memory/MEMORY.md`).
2. Nach komplexen, gelungenen Aufgaben erstellt er mit `skill_save` eine
   wiederverwendbare Anleitung — und verbessert sie bei erneuter Nutzung.
3. Am Session-Ende (CLI-Exit, `/reset` in Telegram, "Session beenden" im
   Dashboard) reflektiert er: Was lief gut, was schlug fehl? → `lessons.md`.
4. Memory-Index, Skills und Lektionen werden in jeden zukünftigen
   System-Prompt geladen — der Agent wird mit jeder Session besser.

Außerdem: **Verifier** — nach jedem Turn mit Tool-Nutzung prüft ein
günstiges Modell, ob die Antwort durch die Tool-Ergebnisse gedeckt ist;
ungedeckte Behauptungen müssen korrigiert werden. **Subagents** — das
`delegate`-Tool erledigt Recherchen in frischem, kleinem Kontext.
**Web-Tools** — `web_search` (DuckDuckGo) und `web_fetch` ohne API-Key.

## Sicherheit

Der Agent hat ein `shell`-Tool und damit vollen Zugriff auf den Host, auf
dem er läuft. Betreibe ihn in Docker oder auf einer eigenen VM, und trage
in `TALOS_TELEGRAM_ALLOWED` nur deine eigene User-ID ein.

## Roadmap

Multi-Agent-Orchestrierung, Verifier für kritische Antworten,
Skill-System, Web-Tools, TalosAI Cloud, native iOS-App. Details in
[VISION.md](VISION.md) und [ARCHITECTURE.md](ARCHITECTURE.md).

## Lizenz

AGPL-3.0-or-later
