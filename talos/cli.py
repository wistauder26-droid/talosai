"""Lokales Chat-REPL: `talos` im Terminal."""

from __future__ import annotations

from .agent import Agent
from .learning import reflect


def _show_tool(name: str, args: dict) -> None:
    detail = args.get("command") or args.get("name") or ""
    print(f"  ⚙ {name}: {str(detail)[:80]}")


def main() -> None:
    agent = Agent()
    agent.on_tool = _show_tool
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
