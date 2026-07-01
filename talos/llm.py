"""Provider-agnostischer LLM-Client.

Spricht das OpenAI-Chat-Completions-Format — damit funktionieren vLLM,
Ollama, OpenRouter, OpenAI und (über deren Kompatibilitäts-API) Anthropic
ohne Codeänderung. Provider wechseln = .env ändern.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from .config import Config

# Preise pro 1 Mio Tokens (Input, Output) in USD — unbekannte Modelle
# (z.B. lokale via Ollama/vLLM) kosten 0.
PRICES: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "gpt-4o": (2.5, 10.0),
}


def _price(model: str) -> tuple[float, float]:
    for key, p in PRICES.items():
        if model.startswith(key):
            return p
    return (0.0, 0.0)


class LLM:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
        # kumulierter Verbrauch dieser Instanz (für Anzeige/Kostenkontrolle)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.last_input_tokens = 0  # Kontext-Größe der letzten Anfrage

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        small: bool = False,
    ) -> Any:
        """Ein Chat-Aufruf. `small=True` nutzt das günstige Modell, falls konfiguriert."""
        model = self.cfg.small_model if (small and self.cfg.small_model) else self.cfg.model
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = self.client.chat.completions.create(**kwargs)
        if getattr(resp, "usage", None):
            tin = resp.usage.prompt_tokens or 0
            tout = resp.usage.completion_tokens or 0
            self.total_input_tokens += tin
            self.total_output_tokens += tout
            self.last_input_tokens = tin
            pin, pout = _price(model)
            self.total_cost_usd += tin / 1e6 * pin + tout / 1e6 * pout
        return resp.choices[0].message
