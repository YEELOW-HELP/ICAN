import asyncio
import logging

from aiogram import Bot, Dispatcher, Router

from app.bot.handlers import register_handlers
from app.core.config import settings
from app.db.session import async_session_factory
from app.services.screening import ScreeningAgent


async def main() -> None:
    logging.basicConfig(level=settings.log_level)

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    router = Router()
    register_handlers(router, async_session_factory, ScreeningAgent())
    dp.include_router(router)

    # Discard any updates (messages, button clicks) that piled up in Telegram's
    # queue while the bot wasn't running — replaying a stale backlog against
    # freshly-reset in-memory FSM state produces garbled, keyboard-less output.
    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
