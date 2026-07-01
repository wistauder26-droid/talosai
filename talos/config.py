"""Zentrale Konfiguration — alles über Umgebungsvariablen (.env)."""

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

    # Daten-Verzeichnis (Memory, Sessions)
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("TALOS_DATA_DIR", "data")))

    max_tool_rounds: int = int(os.getenv("TALOS_MAX_TOOL_ROUNDS", "20"))

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "memory").mkdir(exist_ok=True)
