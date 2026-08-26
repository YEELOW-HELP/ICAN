import asyncio
import logging

from aiogram import Bot, Dispatcher, Router

from app.bot.handlers import register_handlers
from app.bot.handlers_v1 import register_handlers_v1
from app.core.config import settings
from app.db.session import async_session_factory
from app.services.screening import ScreeningAgent


async def main() -> None:
    logging.basicConfig(level=settings.log_level)

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    router = Router()
    # Exactly one flow is ever registered on the dispatcher -- never both --
    # so there is no ambiguity about which /start handler wins (Section 17).
    if settings.bot_flow == "v1":
        register_handlers_v1(router, async_session_factory)
    else:
        register_handlers(router, async_session_factory, ScreeningAgent())
    dp.include_router(router)

    # Discard any updates (messages, button clicks) that piled up in Telegram's
    # queue while the bot wasn't running — replaying a stale backlog against
    # freshly-reset in-memory FSM state produces garbled, keyboard-less output.
    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
