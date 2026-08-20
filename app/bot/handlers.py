from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MessageRole, ScreeningState
from app.schemas.profile import ProfileDraft
from app.services import profile_service
from app.services.screening import ScreeningAgent, history_from_messages

router = Router()

GREETING = (
    "Привіт! Я ICAN — допоможу швидко зібрати ваш профіль для пошуку роботи.\n\n"
    "Розкажіть трохи про себе вільним текстом: хто ви, де живете, який досвід і "
    "яку роботу шукаєте. Можна одним повідомленням, я сам розберуся."
)

ALREADY_DONE = "Ви вже проходили скринінг, ваш профіль збережено. Дякую!"

CONFIRM_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Все правильно", callback_data="profile_confirm"),
            InlineKeyboardButton(text="✏️ Хочу виправити", callback_data="profile_edit"),
        ]
    ]
)


async def _run_screening_turn(
    session: AsyncSession, agent: ScreeningAgent, user, user_text: str
) -> tuple[str, bool]:
    await profile_service.record_message(session, user, MessageRole.USER, user_text)

    history = history_from_messages(await profile_service.get_messages(session, user))
    # the message we just recorded is the last item in history already
    history = history[:-1]

    current_profile = await profile_service.get_profile(session, user)
    draft = ProfileDraft(**{f: getattr(current_profile, f) for f in ProfileDraft.model_fields})

    result = await agent.process_message(history, draft, user_text)

    await profile_service.apply_profile_draft(session, user, result.profile)
    await profile_service.record_message(session, user, MessageRole.ASSISTANT, result.reply_to_user)

    state = ScreeningState.AWAITING_CONFIRMATION if result.ready_for_confirmation else ScreeningState.IN_PROGRESS
    await profile_service.set_state(session, user, state)

    return result.reply_to_user, result.ready_for_confirmation


def register_handlers(router_: Router, session_factory, agent: ScreeningAgent) -> None:
    @router_.message(CommandStart())
    async def on_start(message: Message) -> None:
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, message.from_user.id)
            if user.screening_state == ScreeningState.CONFIRMED:
                await message.answer(ALREADY_DONE)
                return
            await profile_service.set_state(session, user, ScreeningState.IN_PROGRESS)
            await message.answer(GREETING)

    @router_.message()
    async def on_text(message: Message) -> None:
        if not message.text:
            return
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, message.from_user.id)

            if user.screening_state == ScreeningState.CONFIRMED:
                await message.answer(ALREADY_DONE)
                return

            reply, ready = await _run_screening_turn(session, agent, user, message.text)

            if ready:
                await message.answer(reply, reply_markup=CONFIRM_KEYBOARD)
            else:
                await message.answer(reply)

    @router_.callback_query(lambda c: c.data == "profile_confirm")
    async def on_confirm(callback: CallbackQuery) -> None:
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, callback.from_user.id)
            await profile_service.confirm_profile(session, user)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Дякую! Профіль збережено. \U0001f389")
        await callback.answer()

    @router_.callback_query(lambda c: c.data == "profile_edit")
    async def on_edit(callback: CallbackQuery) -> None:
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, callback.from_user.id)
            await profile_service.set_state(session, user, ScreeningState.IN_PROGRESS)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Добре, напишіть що саме виправити.")
        await callback.answer()
