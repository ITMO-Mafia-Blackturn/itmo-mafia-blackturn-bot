import logging
import struct
import zlib
import asyncio
from io import BytesIO
from datetime import datetime
from html import escape
from typing import TypedDict
import httpx
import pandas as pd
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram import Bot
from aiogram.types import BufferedInputFile, CallbackQuery, InputMediaPhoto, Message
import bot.keyboards as kb
from bot.tournament_user.states import TournamentAdminState
from database.requests import check_admin
from services.tournament_service import (
    TournamentRegistrationCard,
    archive_tournament,
    approve_registration,
    count_active_guest_registrations,
    get_all_registrations,
    get_approved_registrations,
    get_pending_registration_ids,
    get_registration_card,
    get_tournament,
    get_tournaments,
    create_tournament,
    reject_registration,
    registration_status,
    mark_tournament_passes_sent,
    tournament_passes_sent,
)
from bot.tournament_edit import router as tournament_edit_router

tournament_admin = Router()

from bot.tournament_admin.common import _is_admin
from bot.tournament_admin.review_views import (
    _show_next_pending, _send_registration_card, _notify_applicant,
    _render_registration_card, _finish_registration_review,
)

@tournament_admin.callback_query(F.data.startswith("tournament_admin:"))
async def handle_review_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _is_admin(callback.from_user.id):
            await callback.answer("Нет доступа.", show_alert=True)
            return

        action, *arguments = callback.data.split(":")[1:]

        if action == "review":
            tournament_id = int(arguments[0])
            await state.update_data(
                tournament_admin_id=tournament_id,
                tournament_review_message_id=None,
            )
            await _show_next_pending(callback, state, tournament_id)
            return

        if action in {"previous", "next"}:
            data = await state.get_data()
            queue = data.get("tournament_registration_ids", [])
            index = data.get("tournament_registration_index", 0)
            if not queue:
                await callback.answer("Список заявок пуст.", show_alert=True)
                return
            index += -1 if action == "previous" else 1
            if index < 0:
                await callback.answer("Это первая заявка в очереди.", show_alert=True)
                return
            if index >= len(queue):
                await callback.answer("Все заявки уже просмотрены.", show_alert=True)
                return
            await _send_registration_card(callback, state, queue[index], index, queue)
            return

        if action == "approve":
            registration_id = int(arguments[0])
            chat_id = await approve_registration(registration_id)
            if chat_id is None:
                await callback.answer("Заявка уже обработана или не найдена.", show_alert=True)
                return
            await _notify_applicant(
                callback.bot,
                callback.message,
                chat_id,
                "Ваша заявка на турнир подтверждена.",
            )
            data = await state.get_data()
            tournament_id = data.get("tournament_admin_id")
            if not isinstance(tournament_id, int):
                await callback.answer("Заявка подтверждена.")
                return
            await _show_next_pending(callback, state, tournament_id)
            return

        if action == "reject":
            registration_id = int(arguments[0])
            await state.update_data(tournament_rejection_id=registration_id)
            await state.set_state(TournamentAdminState.rejection_reason)
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption="Отправьте причину отказа отдельным сообщением (до 500 символов).",
                    reply_markup=None,
                )
            else:
                await callback.message.edit_text(
                    "Отправьте причину отказа отдельным сообщением (до 500 символов).",
                    reply_markup=None,
                )
            await callback.answer()

@tournament_admin.message(TournamentAdminState.rejection_reason)
async def receive_rejection_reason(
    message: Message, state: FSMContext
) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        await state.clear()
        return
    reason = (message.text or "").strip()
    if not reason or len(reason) > 500:
        await message.answer("Причина обязательна и должна быть не длиннее 500 символов.")
        return

    data = await state.get_data()
    registration_id = data.get("tournament_rejection_id")
    tournament_id = data.get("tournament_admin_id")
    review_message_id = data.get("tournament_review_message_id")
    review_chat_id = data.get("tournament_review_chat_id")
    if (
        not isinstance(registration_id, int)
        or not isinstance(tournament_id, int)
        or not isinstance(review_message_id, int)
        or not isinstance(review_chat_id, int)
    ):
        await state.clear()
        await message.answer("Не удалось определить заявку. Откройте очередь заново.")
        return

    chat_id = await reject_registration(registration_id, reason)
    if chat_id is None:
        await state.clear()
        await message.answer("Заявка уже обработана или не найдена.")
        return

    await state.set_state(None)
    await _notify_applicant(
        message.bot,
        message,
        chat_id,
        f"Ваша заявка на турнир отклонена.\nПричина: {reason}",
    )
    queue = await get_pending_registration_ids(tournament_id)
    if queue:
        await _render_registration_card(
            message.bot,
            review_chat_id,
            state,
            queue[0],
            0,
            queue,
        )
        return
    await _finish_registration_review(
        message.bot,
        review_chat_id,
        review_message_id,
        state,
        "Заявка отклонена. Неподтверждённых заявок больше нет.",
    )

logger = logging.getLogger(__name__)
