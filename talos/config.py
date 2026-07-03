"""Zentrale Konfiguration.

Basis über Umgebungsvariablen (.env); die Einstellungsseite des Dashboards
schreibt data/settings.json, das die .env-Werte überschreibt (Provider-
Profile, Voice, Verifier, MCP-Server).
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # LLM-Provider: jede OpenAI-kompatible API (vLLM, Ollama, OpenRouter, OpenAI, ...)
    base_url: str = field(default_factory=lambda: os.getenv("TALOS_BASE_URL", "http://localhost:11434/v1"))
    api_key: str = field(default_factory=lambda: os.getenv("TALOS_API_KEY", "none"))
    model: str = field(default_factory=lambda: os.getenv("TALOS_MODEL", "qwen3:14b"))
    # optional kleineres Modell für einfache Schritte (Token-Effizienz)
    small_model: str = field(default_factory=lambda: os.getenv("TALOS_SMALL_MODEL", ""))

    # Telegram
    telegram_token: str = field(default_factory=lambda: os.getenv("TALOS_TELEGRAM_TOKEN", ""))
    # kommagetrennte Telegram-User-IDs, die den Bot nutzen dürfen (leer = niemand)
    telegram_allowed: list[int] = field(
        default_factory=lambda: [int(x) for x in os.getenv("TALOS_TELEGRAM_ALLOWED", "").split(",") if x.strip()]
    )

    # ElevenLabs (hochwertige Sprachausgabe; leer = Browser-Stimme)
    eleven_key: str = field(default_factory=lambda: os.getenv("TALOS_ELEVENLABS_KEY", ""))
    eleven_voice: str = field(default_factory=lambda: os.getenv("TALOS_ELEVENLABS_VOICE", "pNInz6obpgDQGcFmaJgB"))

    # Daten-Verzeichnis (Memory, Sessions)
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("TALOS_DATA_DIR", "data")))

    max_tool_rounds: int = int(os.getenv("TALOS_MAX_TOOL_ROUNDS", "20"))
    # Verifier: Antworten nach Tool-Nutzung gegen die Tool-Ergebnisse prüfen
    verify: bool = os.getenv("TALOS_VERIFY", "1") != "0"
    # Kontext-Kompaktierung: ab dieser Zeichenzahl wird alter Verlauf
    # zusammengefasst (Token-Effizienz bei langen Sessions)
    compact_chars: int = int(os.getenv("TALOS_COMPACT_CHARS", "60000"))
    # Persona: eigener Zusatz zum System-Prompt (Name/Tonfall/Sprache)
    persona: str = ""
    # Kontextfenster des Modells (nur für die %-Anzeige im Dashboard)
    context_window: int = int(os.getenv("TALOS_CONTEXT_WINDOW", "200000"))
    # Subagenten (delegate-Tool) erlauben
    subagents: bool = True
    # Shell-Tool erlauben (aus Sicherheitsgründen abschaltbar)
    shell_enabled: bool = True
    # Dashboard-Passwort (settings.json überschreibt die Umgebungsvariable)
    web_password: str = field(default_factory=lambda: os.getenv("TALOS_WEB_PASSWORD", ""))
    # Anzeige-Vorgaben fürs Dashboard
    tts_default: bool = False
    tts_rate: float = 1.05
    show_tools: bool = True
    show_graph: bool = True

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "memory").mkdir(exist_ok=True)
        self.mcp_servers: list[dict] = []
        self._apply_settings_file()

    @property
    def settings_file(self) -> Path:
        return self.data_dir / "settings.json"

    def _apply_settings_file(self) -> None:
        """data/settings.json (von der Einstellungsseite) überschreibt .env."""
        if not self.settings_file.exists():
            return
        try:
            s = json.loads(self.settings_file.read_text())
        except json.JSONDecodeError:
            return
        active = s.get("active_provider")
        for p in s.get("providers", []):
            if p.get("name") == active:
                self.base_url = p.get("base_url") or self.base_url
                self.api_key = p.get("api_key") or self.api_key
                self.model = p.get("model") or self.model
                self.small_model = p.get("small_model", self.small_model)
                break
        if s.get("eleven_key"):
            self.eleven_key = s["eleven_key"]
        if s.get("eleven_voice"):
            self.eleven_voice = s["eleven_voice"]
        if "verify" in s:
            self.verify = bool(s["verify"])
        self.mcp_servers = s.get("mcp_servers", [])
        self.persona = s.get("persona", self.persona)
        for key in ("max_tool_rounds", "compact_chars", "context_window"):
            if s.get(key):
                setattr(self, key, int(s[key]))
        for key in ("subagents", "shell_enabled", "tts_default", "show_tools", "show_graph"):
            if key in s:
                setattr(self, key, bool(s[key]))
        if s.get("tts_rate"):
            self.tts_rate = float(s["tts_rate"])
        if s.get("web_password"):
            self.web_password = s["web_password"]
        if s.get("telegram_token"):
            self.telegram_token = s["telegram_token"]
        if s.get("telegram_allowed"):
            self.telegram_allowed = [
                int(x) for x in str(s["telegram_allowed"]).split(",") if str(x).strip()
            ]
