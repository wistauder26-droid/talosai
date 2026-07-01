"""Provider-agnostischer LLM-Client.

Spricht das OpenAI-Chat-Completions-Format — damit funktionieren vLLM,
Ollama, OpenRouter, OpenAI und (über deren Kompatibilitäts-API) Anthropic
ohne Codeänderung. Provider wechseln = .env ändern.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from .config import Config


class LLM:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
        # kumulierter Verbrauch dieser Instanz (für Anzeige/Kostenkontrolle)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

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
            self.total_input_tokens += resp.usage.prompt_tokens or 0
            self.total_output_tokens += resp.usage.completion_tokens or 0
        return resp.choices[0].message
