"""Lokales Chat-REPL: `talos` im Terminal."""

from __future__ import annotations

from .agent import Agent
from .learning import reflect


def main() -> None:
    agent = Agent()
    print(f"Talos ({agent.cfg.model} @ {agent.cfg.base_url}) — 'exit' zum Beenden.")
    try:
        while True:
            try:
                user = input("\ndu> ").strip()
            except EOFError:
                break
            if not user:
                continue
            if user.lower() in ("exit", "quit"):
                break
            print(f"\ntalos> {agent.run(user)}")
    except KeyboardInterrupt:
        pass
    lessons = reflect(agent)
    if lessons:
        print("\n[Gelernt: " + "; ".join(lessons) + "]")
    print("Bis bald.")


if __name__ == "__main__":
    main()
