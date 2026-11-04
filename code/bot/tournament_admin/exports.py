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
from bot.tournament_admin.review_views import _registration_list_text

@tournament_admin.callback_query(F.data.startswith("tournament_admin:"))
async def handle_export_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _is_admin(callback.from_user.id):
            await callback.answer("Нет доступа.", show_alert=True)
            return

        action, *arguments = callback.data.split(":")[1:]

        if action == "registrations":
            tournament_id = int(arguments[0])
            tournament = next(
                (item for item in await get_tournaments() if item.id == tournament_id),
                None,
            )
            if tournament is None:
                await callback.answer("Турнир не найден.", show_alert=True)
                return
            registrations = await get_all_registrations(tournament_id)
            if not registrations:
                await callback.message.answer("На этот турнир пока никто не записался.")
            else:
                for text in _registration_list_text(tournament.name, registrations):
                    await callback.message.answer(text, parse_mode="HTML")
            await callback.answer()
            return

        if action == "guests":
            tournament_id = int(arguments[0])
            tournament = await get_tournament(tournament_id)
            if tournament is None:
                await callback.answer("Турнир не найден.", show_alert=True)
                return
            guests = await get_approved_registrations(tournament_id)
            if not guests:
                await callback.answer("Подтверждённых гостей пока нет.", show_alert=True)
                return

            rows = [
                {
                    "ФИО": guest.full_name or "",
                    "Telegram ID": guest.chat_id,
                    "Уровень": (
                        level["level_name"]
                        if (level := kb.get_level_info_by_id(guest.bot_level))
                        else str(guest.bot_level)
                    ),
                    "Игровой ник": guest.bot_nickname,
                    "Из ИТМО": "Да" if guest.is_itmo else "Нет",
                    "Polemica ник": guest.polemica_nickname or "",
                    "Polemica ID": guest.polemica_id or "",
                }
                for guest in guests
            ]
            workbook = BytesIO()
            pd.DataFrame(rows).to_excel(workbook, sheet_name="Гости", index=False)
            await callback.message.answer_document(
                BufferedInputFile(
                    workbook.getvalue(),
                    filename=f"Гости_турнир_{tournament_id}.xlsx",
                )
            )
            await callback.answer()
            return

        if action == "passes":
            tournament_id = int(arguments[0])
            tournament = await get_tournament(tournament_id)
            if tournament is None:
                await callback.answer("Турнир не найден.", show_alert=True)
                return
            if await tournament_passes_sent(tournament_id):
                await callback.answer(
                    "Проходки для этого турнира уже были отправлены.", show_alert=True
                )
                return

            approved_guests = await get_approved_registrations(tournament_id)
            guests = [guest for guest in approved_guests if not guest.is_itmo]
            if not guests:
                await callback.answer(
                    "Нет подтверждённых гостей вне ИТМО для оформления проходок.",
                    show_alert=True,
                )
                return

            await callback.answer()
            progress = await callback.message.answer(
                f"Началась отправка проходок для {len(guests)} гостей."
            )
            successful_sends = 0
            failed_sends = 0
            async with httpx.AsyncClient(timeout=30.0) as client:
                for guest in guests:
                    payload = {
                        "fio": guest.full_name,
                        "contacts": f"t.me/{guest.telegram_username}",
                        "from_itmo": ["114298929"],
                        "occupation": ["114298576"],
                        "occupation_custom": "Игрок в мафию",
                        "phone": guest.phone,
                        "passport": guest.passport,
                        "citizenship": ["114299256"],
                        "corpus": ["114300051"],
                        "has_pass": ["114300643"],
                        "event": ["114305512"],
                        "date": tournament.date.strftime("%Y-%m-%d"),
                        "personal_data": True,
                    }
                    try:
                        response = await client.post(
                            "https://api.forms.yandex.net/v1/surveys/"
                            "66f6cb8773cee77dbdffbd87/form?dry_run=false",
                            json=payload,
                        )
                    except httpx.RequestError:
                        failed_sends += 1
                        logger.exception(
                            "Could not request pass for tournament %s, user %s",
                            tournament_id,
                            guest.chat_id,
                        )
                    else:
                        if response.status_code == 200:
                            successful_sends += 1
                            try:
                                await callback.bot.send_message(
                                    chat_id=guest.chat_id,
                                    text=(
                                        "Вам оформлена проходка на турнир "
                                        f"{tournament.name}"
                                    ),
                                )
                            except TelegramAPIError:
                                logger.exception(
                                    "Could not notify tournament guest %s",
                                    guest.chat_id,
                                )
                        else:
                            failed_sends += 1
                            logger.error(
                                "Pass form rejected tournament %s guest %s: "
                                "status=%s body=%s",
                                tournament_id,
                                guest.chat_id,
                                response.status_code,
                                response.text,
                            )
                    await asyncio.sleep(5)

            passes_marked = (
                await mark_tournament_passes_sent(tournament_id)
                if failed_sends == 0
                else False
            )
            await progress.edit_text(
                "Отправка проходок завершена.\n"
                f"Успешно: {successful_sends}\n"
                f"Неудачно: {failed_sends}\n"
                + (
                    "Повторная отправка заблокирована."
                    if passes_marked
                    else (
                        "Турнир не найден, статус отправки не сохранён."
                        if failed_sends == 0
                        else "Исправьте ошибки перед повторной отправкой."
                    )
                )
            )
            return

logger = logging.getLogger(__name__)
