from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import anketa
from app.bot.debounce import Debouncer
from app.bot.profile_card import render_profile_card
from app.bot.states import Anketa, CVFlow, Onboarding
from app.core.config import settings
from app.db.models import MessageRole, ScreeningState
from app.schemas.profile import ProfileDraft
from app.services import documents, profile_service
from app.services.screening import ScreeningAgent, history_from_messages

logger = logging.getLogger(__name__)

router = Router()

ONBOARDING_TEXT = (
    "Привіт! Я ICAN \U0001f44b\n\n"
    "Я допоможу знайти роботу, яка підходить саме тобі.\n"
    "Спочатку я дізнаюсь трохи про твій досвід і побажання.\n\n"
    "Це займе приблизно 5-10 хвилин."
)

METHOD_TEXT = "Як тобі зручніше розповісти про себе?"

GREETING = (
    "Розкажи трохи про себе своїми словами: хто ти, де живеш, який досвід і "
    "яку роботу шукаєш. Можна одним повідомленням, я сам розберуся."
)

ALREADY_DONE = "Ви вже проходили скринінг, ваш профіль збережено. Дякую!"

FORCED_WRAP_UP = (
    "Здається, ми довго спілкуємось \U0001f642 Давайте зафіксуємо те, що вже відомо, "
    "а деталі можна буде доуточнити пізніше."
)

TURN_ERROR_REPLY = "Вибачте, сталася технічна помилка. Спробуйте, будь ласка, написати ще раз."

CV_ACK = "Дякую! Я прочитав резюме. Зараз уточню декілька деталей."
CV_PROMPT = "Надішли, будь ласка, файл резюме у форматі PDF або DOCX."
CV_UNSUPPORTED = "Не вдалося прочитати файл. Спробуй PDF або DOCX."
CV_EMPTY = "Не вдалося розпізнати текст у файлі. Спробуй інший файл або обери «Розповісти в чаті» через /start."

ONBOARDING_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f680 Почати", callback_data="onb:start")],
        [InlineKeyboardButton(text="\U0001f4c4 Завантажити резюме", callback_data="onb:cv")],
    ]
)

METHOD_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f4c4 Завантажити резюме", callback_data="method:cv")],
        [InlineKeyboardButton(text="\U0001f4ac Розповісти в чаті", callback_data="method:chat")],
        [InlineKeyboardButton(text="\U0001f4dd Заповнити коротку анкету", callback_data="method:anketa")],
    ]
)

CONFIRM_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Все правильно", callback_data="profile_confirm"),
            InlineKeyboardButton(text="✏️ Змінити", callback_data="profile_edit"),
        ]
    ]
)

RETURNING_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f464 Переглянути профіль", callback_data="returning:profile")],
        [InlineKeyboardButton(text="✏️ Оновити профіль", callback_data="returning:edit")],
    ]
)


async def _run_screening_turn(
    session: AsyncSession, agent: ScreeningAgent, user, user_text: str
) -> tuple[str, bool]:
    """Runs one AI screening turn. Used identically for free-form chat messages
    and for CV text — both are just "a chunk of text describing the candidate"
    from the agent's point of view."""
    await profile_service.record_message(session, user, MessageRole.USER, user_text)

    history = history_from_messages(await profile_service.get_messages(session, user))
    # the message we just recorded is the last item in history already
    history = history[:-1]

    current_profile = await profile_service.get_profile(session, user)
    draft = ProfileDraft(**{f: getattr(current_profile, f) for f in ProfileDraft.model_fields})

    user_turns = sum(1 for m in history if m["role"] == "user") + 1  # +1 for the current message

    if user_turns > settings.max_screening_turns:
        # Hard stop: never call the API past this point for this session, no
        # matter what the agent would have said — bounds worst-case spend per
        # user even if extraction gets stuck in a clarifying-question loop.
        ready = True
        display_text = f"{FORCED_WRAP_UP}\n\n{render_profile_card(draft)}"
    else:
        # Only the most recent messages are sent — current_profile already
        # carries forward everything extracted earlier, so this bounds the
        # token cost of each call instead of letting it grow with the whole
        # conversation.
        windowed_history = history[-settings.history_window :]
        result = await agent.process_message(windowed_history, draft, user_text)
        await profile_service.apply_profile_draft(session, user, result.profile)
        ready = result.ready_for_confirmation
        # All three intake paths (CV / chat / anketa) must converge on the same
        # confirmation view instead of each rendering its own free-text summary.
        display_text = render_profile_card(result.profile) if ready else result.reply_to_user

    await profile_service.record_message(session, user, MessageRole.ASSISTANT, display_text)

    state = ScreeningState.AWAITING_CONFIRMATION if ready else ScreeningState.IN_PROGRESS
    await profile_service.set_state(session, user, state)

    return display_text, ready


async def _finalize_anketa(session: AsyncSession, user, answers: dict[str, str]) -> str:
    draft = anketa.build_profile(answers)
    await profile_service.apply_profile_draft(session, user, draft)

    summary = "; ".join(f"{k}={v}" for k, v in answers.items())
    await profile_service.record_message(session, user, MessageRole.USER, f"[Анкета] {summary}")

    text = render_profile_card(draft)
    await profile_service.record_message(session, user, MessageRole.ASSISTANT, text)
    await profile_service.set_state(session, user, ScreeningState.AWAITING_CONFIRMATION)
    return text


def register_handlers(router_: Router, session_factory, agent: ScreeningAgent) -> None:
    async def _handle_cv_upload(message: Message, state: FSMContext) -> None:
        document = message.document
        filename = document.file_name or "resume"
        if not filename.lower().endswith((".pdf", ".docx")):
            await message.answer(CV_UNSUPPORTED)
            return

        file_info = await message.bot.get_file(document.file_id)
        buffer = await message.bot.download_file(file_info.file_path)

        try:
            cv_text = documents.extract_text(buffer.read(), filename)
        except documents.UnsupportedDocumentError:
            await message.answer(CV_UNSUPPORTED)
            return

        if not cv_text.strip():
            await message.answer(CV_EMPTY)
            return

        await message.answer(CV_ACK)
        await state.clear()

        try:
            async with session_factory() as session:
                user = await profile_service.get_or_create_user(session, message.from_user.id)
                display_text, ready = await _run_screening_turn(session, agent, user, cv_text)
        except Exception:
            logger.exception("CV screening turn failed for telegram_id=%s", message.from_user.id)
            await message.answer(TURN_ERROR_REPLY)
            return

        markup = CONFIRM_KEYBOARD if ready else None
        await message.answer(display_text, reply_markup=markup)

    # ---- Onboarding ----

    @router_.message(CommandStart())
    async def on_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, message.from_user.id)
            if user.screening_state == ScreeningState.CONFIRMED:
                profile = await profile_service.get_profile(session, user)
                card = render_profile_card(profile, title="З поверненням!")
                await message.answer(f"{card}\n\nЩо робимо сьогодні?", reply_markup=RETURNING_KEYBOARD)
                return
        await message.answer(ONBOARDING_TEXT, reply_markup=ONBOARDING_KEYBOARD)

    @router_.callback_query(F.data == "onb:start")
    async def on_onboarding_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(Onboarding.choosing_method)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(METHOD_TEXT, reply_markup=METHOD_KEYBOARD)
        await callback.answer()

    @router_.message(Onboarding.choosing_method)
    async def on_onboarding_stray_text(message: Message) -> None:
        await message.answer("Обери, будь ласка, один із варіантів вище \U0001f642", reply_markup=METHOD_KEYBOARD)

    # ---- Method: CV ----

    @router_.callback_query(F.data.in_({"onb:cv", "method:cv"}))
    async def on_method_cv(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(CVFlow.awaiting_file)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(CV_PROMPT)
        await callback.answer()

    @router_.message(CVFlow.awaiting_file, F.document)
    async def on_cv_document(message: Message, state: FSMContext) -> None:
        await _handle_cv_upload(message, state)

    @router_.message(CVFlow.awaiting_file)
    async def on_cv_awaiting_nudge(message: Message) -> None:
        await message.answer(f"Очікую файл резюме (PDF або DOCX).\n\n{CV_PROMPT}")

    # ---- Method: chat ----

    @router_.callback_query(F.data == "method:chat")
    async def on_method_chat(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, callback.from_user.id)
            await profile_service.set_state(session, user, ScreeningState.IN_PROGRESS)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(GREETING)
        await callback.answer()

    # ---- Method: anketa ----

    @router_.callback_query(F.data == "method:anketa")
    async def on_method_anketa(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(Anketa.city)
        await state.update_data(answers={})
        await callback.message.edit_reply_markup(reply_markup=None)
        text, markup = anketa.prompt_for(Anketa.city)
        await callback.message.answer(text, reply_markup=markup)
        await callback.answer()

    @router_.callback_query(F.data.startswith("anketa:"))
    async def on_anketa_answer(callback: CallbackQuery, state: FSMContext) -> None:
        _, field_key, value = callback.data.split(":", 2)

        if field_key == "city" and value == "Інше":
            await state.set_state(Anketa.city_other)
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("Введи, будь ласка, місто:")
            await callback.answer()
            return

        answer_field = anketa.FIELD_MAP[field_key]
        data = await state.get_data()
        answers = dict(data.get("answers", {}))
        answers[answer_field] = value
        await state.update_data(answers=answers)

        current = await state.get_state()
        next_step = anketa.next_state(current)
        await callback.message.edit_reply_markup(reply_markup=None)
        await _advance_anketa(callback.message, callback.from_user.id, state, answers, next_step)
        await callback.answer()

    @router_.message(StateFilter(Anketa.city_other, Anketa.desired_role, Anketa.income))
    async def on_anketa_text(message: Message, state: FSMContext) -> None:
        if not message.text:
            return

        current = await state.get_state()
        data = await state.get_data()
        answers = dict(data.get("answers", {}))

        if current == Anketa.city_other.state:
            answers["city"] = message.text
            next_step = Anketa.desired_role
        elif current == Anketa.desired_role.state:
            answers["desired_role"] = message.text
            next_step = anketa.next_state(Anketa.desired_role.state)
        else:
            answers["income"] = message.text
            next_step = anketa.next_state(Anketa.income.state)

        await state.update_data(answers=answers)
        await _advance_anketa(message, message.from_user.id, state, answers, next_step)

    @router_.message(StateFilter(Anketa.experience, Anketa.employment_format, Anketa.work_format))
    async def on_anketa_button_only_nudge(message: Message) -> None:
        await message.answer("Обери, будь ласка, один із варіантів на кнопках вище \U0001f642")

    async def _advance_anketa(message: Message, telegram_id: int, state: FSMContext, answers: dict, next_step) -> None:
        if next_step is None:
            await state.clear()
            async with session_factory() as session:
                user = await profile_service.get_or_create_user(session, telegram_id)
                text = await _finalize_anketa(session, user, answers)
            await message.answer(text, reply_markup=CONFIRM_KEYBOARD)
        else:
            await state.set_state(next_step)
            text, markup = anketa.prompt_for(next_step)
            await message.answer(text, reply_markup=markup)

    # ---- Plain chat screening (debounced) — only when no onboarding/CV/anketa step is active ----

    reply_targets: dict[int, tuple[int, Bot]] = {}

    async def _flush_turn(telegram_id: int, texts: list[str]) -> None:
        chat_id, bot = reply_targets.pop(telegram_id)
        combined_text = "\n".join(texts)

        try:
            async with session_factory() as session:
                user = await profile_service.get_or_create_user(session, telegram_id)
                display_text, ready = await _run_screening_turn(session, agent, user, combined_text)
        except Exception:
            logger.exception("Screening turn failed for telegram_id=%s", telegram_id)
            await bot.send_message(chat_id, TURN_ERROR_REPLY)
            return

        markup = CONFIRM_KEYBOARD if ready else None
        await bot.send_message(chat_id, display_text, reply_markup=markup)

    debouncer = Debouncer(delay_seconds=settings.debounce_seconds, flush=_flush_turn)

    @router_.message(StateFilter(None))
    async def on_text(message: Message) -> None:
        if not message.text:
            return

        telegram_id = message.from_user.id

        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, telegram_id)
            if user.screening_state == ScreeningState.CONFIRMED:
                await message.answer(ALREADY_DONE)
                return

        reply_targets[telegram_id] = (message.chat.id, message.bot)
        debouncer.push(telegram_id, message.text)

    # ---- Confirmation ----

    @router_.callback_query(F.data == "profile_confirm")
    async def on_confirm(callback: CallbackQuery) -> None:
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, callback.from_user.id)
            await profile_service.confirm_profile(session, user)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Дякую! Профіль збережено. \U0001f389")
        await callback.answer()

    @router_.callback_query(F.data == "profile_edit")
    async def on_edit(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, callback.from_user.id)
            await profile_service.set_state(session, user, ScreeningState.IN_PROGRESS)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Добре, напишіть що саме виправити.")
        await callback.answer()

    # ---- Returning (already confirmed) user ----

    @router_.callback_query(F.data == "returning:profile")
    async def on_returning_profile(callback: CallbackQuery) -> None:
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, callback.from_user.id)
            profile = await profile_service.get_profile(session, user)
        await callback.message.answer(render_profile_card(profile))
        await callback.answer()

    @router_.callback_query(F.data == "returning:edit")
    async def on_returning_edit(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        async with session_factory() as session:
            user = await profile_service.get_or_create_user(session, callback.from_user.id)
            await profile_service.set_state(session, user, ScreeningState.IN_PROGRESS)
        await callback.message.answer("Розкажи, що змінилося — оновлю профіль.")
        await callback.answer()
