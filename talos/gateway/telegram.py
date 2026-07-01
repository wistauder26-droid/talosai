"""Telegram-Gateway: ein Agent pro Chat, nur für erlaubte User-IDs."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ..agent import Agent
from ..config import Config
from ..learning import reflect

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("talos.telegram")

_agents: dict[int, Agent] = {}
_cfg = Config()


def _agent_for(chat_id: int) -> Agent:
    if chat_id not in _agents:
        _agents[chat_id] = Agent(_cfg, session_id=f"tg-{chat_id}")
    return _agents[chat_id]


def _allowed(update: Update) -> bool:
    user = update.effective_user
    return user is not None and user.id in _cfg.telegram_allowed


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        log.warning("Abgelehnt: User %s", update.effective_user)
        return
    agent = _agent_for(update.effective_chat.id)
    text = update.message.text
    await update.effective_chat.send_action("typing")
    # Agent-Loop blockiert — im Thread ausführen, damit der Bot reaktiv bleibt
    reply = await asyncio.to_thread(agent.run, text)
    await update.message.reply_text(reply or "…")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reset — Session beenden, Reflexion (Learning-Loop) ausführen, neu starten."""
    if not _allowed(update):
        return
    agent = _agents.pop(update.effective_chat.id, None)
    lessons = await asyncio.to_thread(reflect, agent) if agent else []
    msg = "Neue Session gestartet."
    if lessons:
        msg += " Gelernt: " + "; ".join(lessons)
    await update.message.reply_text(msg)


def main() -> None:
    if not _cfg.telegram_token:
        raise SystemExit("TALOS_TELEGRAM_TOKEN fehlt (.env)")
    if not _cfg.telegram_allowed:
        raise SystemExit("TALOS_TELEGRAM_ALLOWED fehlt (.env) — sonst darf niemand den Bot nutzen")
    app = Application.builder().token(_cfg.telegram_token).build()
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Talos Telegram-Gateway läuft.")
    app.run_polling()


if __name__ == "__main__":
    main()
