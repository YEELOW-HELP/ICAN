"""Thin Telegram adapter for the Stage 1 Hybrid assessment flow (Section
17: "no core business logic in the adapter"). Every handler here does the
same three things -- receive a Telegram update, resolve/invoke a
channel-agnostic domain command from app.services.*, render the result --
and nothing else. State transitions, access checks, and question
selection all live in the domain layer; this module never mutates an
InterviewSession's status directly and never decides what to ask next.

Registered only when settings.bot_flow == "v1" (see app/bot/main.py) --
the legacy flow in app/bot/handlers.py is untouched and keeps working
until a separately reviewed cutover.
"""

from __future__ import annotations

import logging
import uuid
from typing import Awaitable, Callable

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.states import V1Flow
from app.db.models_assessment import AssessmentStatus, CVExtractionStatus
from app.db.models_identity import IdentityUser
from app.services.assessment.content import get_choice_label, get_message, get_question_prompt
from app.services.assessment.cv import upload_cv
from app.services.assessment.extraction import AnswerExtractor
from app.services.assessment.question_bank import Question
from app.services.assessment.sessions import (
    complete_assessment,
    get_next_question_for_session,
    get_unfinished_session_for_user,
    pause_assessment,
    resume_assessment,
    start_assessment,
    submit_answer,
)
from app.services.consent import ASSESSMENT_PURPOSE, grant_consent, has_active_consent
from app.services.exceptions import (
    CVFileTooLargeError,
    PromoAllocationExhaustedError,
    PromoCodeInvalidError,
    UnfinishedAssessmentExistsError,
)
from app.services.identity import resolve_identity
from app.services.product_access import get_any_active_entitlement, redeem_promo_code

logger = logging.getLogger(__name__)

Send = Callable[..., Awaitable[None]]


def _consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_message("consent_confirm_button"), callback_data="v1consent:agree")]]
    )


def _cv_offer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_message("cv_offer_upload_button"), callback_data="v1cv:upload")],
            [InlineKeyboardButton(text=get_message("cv_offer_skip_button"), callback_data="v1cv:skip")],
        ]
    )


def _structured_keyboard(question: Question) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_choice_label(c), callback_data=f"v1c:{c}")] for c in question.choices or ()]
    )


def register_handlers_v1(
    router_: Router,
    session_factory,
    extractor_factory: Callable[[], AnswerExtractor] | None = None,
) -> None:
    def _extractor() -> AnswerExtractor | None:
        return extractor_factory() if extractor_factory is not None else None

    async def _resolve(session, telegram_id: int, username: str | None) -> IdentityUser:
        return await resolve_identity(session, provider="telegram", provider_subject=str(telegram_id), provider_username=username)

    async def _advance(session, *, session_id: uuid.UUID, user_id: uuid.UUID, state: FSMContext, send: Send) -> None:
        """Ask the next adaptive question, or finalize the assessment if the
        minimum-data rule is already satisfied. The single place both the
        onboarding path and every answer handler call after progressing the
        session, so "what happens next" is decided in exactly one spot."""
        result = await get_next_question_for_session(session, session_id=session_id, user_id=user_id)
        if result.ready_for_completion:
            await complete_assessment(session, session_id=session_id, user_id=user_id)
            await state.clear()
            await send(get_message("completed"))
            return

        question = result.question
        await state.update_data(question_id=question.question_id, session_id=str(session_id))
        if question.kind == "structured":
            await state.set_state(V1Flow.awaiting_structured_answer)
            await send(get_question_prompt(question.question_id), reply_markup=_structured_keyboard(question))
        else:
            await state.set_state(V1Flow.awaiting_open_answer)
            await send(get_question_prompt(question.question_id))

    async def _start_and_offer_cv(session, user: IdentityUser, entitlement, state: FSMContext, send: Send) -> None:
        try:
            interview_session = await start_assessment(
                session, user_id=user.id, plan_code=entitlement.plan_code, entitlement_id=entitlement.id
            )
        except UnfinishedAssessmentExistsError:
            interview_session = await get_unfinished_session_for_user(session, user.id)
        await state.update_data(session_id=str(interview_session.id))
        await state.set_state(V1Flow.awaiting_cv_decision)
        await send(get_message("cv_offer"), reply_markup=_cv_offer_keyboard())

    async def _proceed_after_consent(session, user: IdentityUser, state: FSMContext, send: Send) -> None:
        entitlement = await get_any_active_entitlement(session, user_id=user.id)
        if entitlement is None:
            await state.set_state(V1Flow.awaiting_promo)
            await send(get_message("no_access"))
            return
        await _start_and_offer_cv(session, user, entitlement, state, send)

    # ---- Entry point ----

    @router_.message(CommandStart())
    async def on_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        async with session_factory() as session:
            user = await _resolve(session, message.from_user.id, message.from_user.username)

            unfinished = await get_unfinished_session_for_user(session, user.id)
            if unfinished is not None:
                if unfinished.status == AssessmentStatus.PAUSED:
                    await resume_assessment(session, session_id=unfinished.id, user_id=user.id)
                    await message.answer(get_message("resumed"))
                await _advance(session, session_id=unfinished.id, user_id=user.id, state=state, send=message.answer)
                return

            if not await has_active_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE):
                await state.set_state(V1Flow.awaiting_consent)
                await message.answer(get_message("onboarding"))
                await message.answer(get_message("consent_prompt"), reply_markup=_consent_keyboard())
                return

            await _proceed_after_consent(session, user, state, message.answer)

    @router_.message(V1Flow.awaiting_consent)
    async def on_consent_stray_text(message: Message) -> None:
        await message.answer(get_message("consent_prompt"), reply_markup=_consent_keyboard())

    # ---- Explicit pause -- registered before the state-scoped catch-all
    # text handlers below, since aiogram tries message handlers in
    # registration order: a state-scoped `@router_.message(V1Flow.X)` with
    # no command filter would otherwise swallow "/pause" as if it were the
    # candidate's answer to the current question.

    @router_.message(Command("pause"))
    async def on_pause(message: Message, state: FSMContext) -> None:
        async with session_factory() as session:
            user = await _resolve(session, message.from_user.id, message.from_user.username)
            unfinished = await get_unfinished_session_for_user(session, user.id)
            if unfinished is None or unfinished.status != AssessmentStatus.ACTIVE:
                return
            await pause_assessment(session, session_id=unfinished.id, user_id=user.id)
        await state.clear()
        await message.answer(get_message("paused"))

    @router_.callback_query(F.data == "v1consent:agree", StateFilter(V1Flow.awaiting_consent))
    async def on_consent_agree(callback: CallbackQuery, state: FSMContext) -> None:
        async with session_factory() as session:
            user = await _resolve(session, callback.from_user.id, callback.from_user.username)
            await grant_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE, source="telegram")
            await callback.message.edit_reply_markup(reply_markup=None)
            await _proceed_after_consent(session, user, state, callback.message.answer)
        await callback.answer()

    # ---- Product access / promo ----

    @router_.message(V1Flow.awaiting_promo)
    async def on_promo_code(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        async with session_factory() as session:
            user = await _resolve(session, message.from_user.id, message.from_user.username)
            try:
                entitlement = await redeem_promo_code(session, code=message.text.strip(), user_id=user.id)
            except (PromoCodeInvalidError, PromoAllocationExhaustedError):
                await message.answer(get_message("promo_invalid"))
                return
            await message.answer(get_message("promo_success"))
            await _start_and_offer_cv(session, user, entitlement, state, message.answer)

    # ---- Optional CV ----

    @router_.callback_query(F.data == "v1cv:upload", StateFilter(V1Flow.awaiting_cv_decision))
    async def on_cv_offer_upload(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(V1Flow.awaiting_cv_file)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(get_message("cv_upload_prompt"))
        await callback.answer()

    @router_.callback_query(F.data == "v1cv:skip", StateFilter(V1Flow.awaiting_cv_decision))
    async def on_cv_offer_skip(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.message.edit_reply_markup(reply_markup=None)
        data = await state.get_data()
        session_id = uuid.UUID(data["session_id"])
        async with session_factory() as session:
            user = await _resolve(session, callback.from_user.id, callback.from_user.username)
            await _advance(session, session_id=session_id, user_id=user.id, state=state, send=callback.message.answer)
        await callback.answer()

    @router_.message(V1Flow.awaiting_cv_file, F.document)
    async def on_cv_document(message: Message, state: FSMContext) -> None:
        document = message.document
        filename = document.file_name or "resume"
        file_info = await message.bot.get_file(document.file_id)
        buffer = await message.bot.download_file(file_info.file_path)
        content_bytes = buffer.read()

        data = await state.get_data()
        session_id = uuid.UUID(data["session_id"])
        async with session_factory() as session:
            user = await _resolve(session, message.from_user.id, message.from_user.username)
            try:
                cv_upload = await upload_cv(
                    session, session_id=session_id, user_id=user.id, filename=filename,
                    content_bytes=content_bytes, extractor=_extractor(),
                )
            except CVFileTooLargeError:
                await message.answer(get_message("cv_too_large"))
                return

            if cv_upload.extraction_status == CVExtractionStatus.UNSUPPORTED:
                await message.answer(get_message("cv_unsupported"))
            elif cv_upload.extraction_status == CVExtractionStatus.EMPTY:
                await message.answer(get_message("cv_empty"))
            else:
                await message.answer(get_message("cv_ack"))

            await _advance(session, session_id=session_id, user_id=user.id, state=state, send=message.answer)

    @router_.message(V1Flow.awaiting_cv_file)
    async def on_cv_file_nudge(message: Message) -> None:
        await message.answer(get_message("cv_upload_prompt"))

    # ---- Adaptive question loop ----

    @router_.message(V1Flow.awaiting_open_answer)
    async def on_open_answer(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        data = await state.get_data()
        question_id = data["question_id"]
        session_id = uuid.UUID(data["session_id"])
        async with session_factory() as session:
            user = await _resolve(session, message.from_user.id, message.from_user.username)
            try:
                await submit_answer(
                    session, session_id=session_id, user_id=user.id, question_id=question_id,
                    raw_text=message.text, idempotency_key=f"tg-msg-{message.message_id}",
                    source="telegram", extractor=_extractor(),
                )
            except Exception:
                logger.exception("submit_answer failed for user_id=%s session_id=%s", user.id, session_id)
                await message.answer(get_message("turn_error"))
                return
            await _advance(session, session_id=session_id, user_id=user.id, state=state, send=message.answer)

    @router_.callback_query(F.data.startswith("v1c:"), StateFilter(V1Flow.awaiting_structured_answer))
    async def on_structured_answer(callback: CallbackQuery, state: FSMContext) -> None:
        _, choice = callback.data.split(":", 1)
        data = await state.get_data()
        question_id = data["question_id"]
        session_id = uuid.UUID(data["session_id"])
        await callback.message.edit_reply_markup(reply_markup=None)
        async with session_factory() as session:
            user = await _resolve(session, callback.from_user.id, callback.from_user.username)
            try:
                await submit_answer(
                    session, session_id=session_id, user_id=user.id, question_id=question_id,
                    raw_text=choice, idempotency_key=f"tg-cb-{callback.id}", source="telegram",
                )
            except Exception:
                logger.exception("submit_answer failed for user_id=%s session_id=%s", user.id, session_id)
                await callback.message.answer(get_message("turn_error"))
                await callback.answer()
                return
            await _advance(session, session_id=session_id, user_id=user.id, state=state, send=callback.message.answer)
        await callback.answer()

    @router_.message(V1Flow.awaiting_structured_answer)
    async def on_structured_stray_text(message: Message) -> None:
        await message.answer(get_message("structured_nudge"))
