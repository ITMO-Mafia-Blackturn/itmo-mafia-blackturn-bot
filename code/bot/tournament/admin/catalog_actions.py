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

from bot.tournament_admin.common import _is_admin, _tournament_creation_data_text


@tournament_admin.callback_query(F.data.startswith("tournament_admin:"))
async def handle_catalog_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if not await _is_admin(callback.from_user.id):
            await callback.answer("Нет доступа.", show_alert=True)
            return

        action, *arguments = callback.data.split(":")[1:]

        if action == "noop":
            await callback.answer()
            return

        if action == "create_cancel":
            await state.clear()
            await callback.message.edit_text("Создание турнира отменено.")
            await callback.answer()
            return

        if action == "archive_cancel":
            await callback.message.edit_text("Архивация турнира отменена.")
            await callback.answer()
            return

        if action == "archive_select":
            try:
                tournament_id = int(arguments[0])
            except (IndexError, ValueError):
                await callback.answer("Некорректный турнир.", show_alert=True)
                return
            tournament = await get_tournament(tournament_id)
            if tournament is None or tournament.expired:
                await callback.answer("Турнир не найден или уже архивирован.", show_alert=True)
                return
            await callback.message.edit_text(
                "<b>Архивировать турнир?</b>\n"
                f"<b>{escape(tournament.name)}</b>\n"
                f"{escape(tournament.description)}\n"
                f"Дата: {tournament.date:%d.%m.%Y %H:%M}\n"
                f"Место: {escape(tournament.place)}\n\n"
                "Регистрация закроется. Заявки и данные турнира останутся в базе.",
                reply_markup=kb.get_tournament_archive_confirmation_keyboard(
                    tournament_id
                ),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        if action == "archive_confirm":
            try:
                tournament_id = int(arguments[0])
            except (IndexError, ValueError):
                await callback.answer("Некорректный турнир.", show_alert=True)
                return
            if not await archive_tournament(tournament_id):
                await callback.answer("Турнир не найден.", show_alert=True)
                return
            await callback.message.edit_text(
                "Турнир архивирован. Регистрация закрыта, заявки сохранены."
            )
            await callback.answer("Турнир перенесён в архив.")
            return

        if action == "create_confirm":
            if await state.get_state() != TournamentAdminState.create_confirmation.state:
                await callback.answer("Создание турнира уже завершено.", show_alert=True)
                return
            data = await state.get_data()
            try:
                tournament_id = await create_tournament(
                    name=data["name"],
                    description=data["description"],
                    place=data["place"],
                    date=data["date"],
                    registry_deadline=data["registry_deadline"],
                    capacity=data["capacity"],
                    guest_capacity=data["guest_capacity"],
                )
            except ValueError as exc:
                await callback.answer(str(exc), show_alert=True)
                return
            await state.clear()
            await callback.message.edit_text(
                f"Турнир создан (№{tournament_id}).\n\n"
                f"{_tournament_creation_data_text(data)}",
                parse_mode="HTML",
            )
            await callback.answer("Турнир сохранён.")
            return

        if action == "select":
            tournament_id = int(arguments[0])
            tournament = next(
                (item for item in await get_tournaments() if item.id == tournament_id),
                None,
            )
            if tournament is None:
                await callback.answer("Турнир не найден.", show_alert=True)
                return
            await state.update_data(tournament_admin_id=tournament_id)
            guest_count = await count_active_guest_registrations(tournament_id)
            await callback.message.edit_text(
                f"<b>{escape(tournament.name)}</b>\n"
                f"{escape(tournament.description)}\n"
                f"Дата: {tournament.date:%d.%m.%Y %H:%M}\n"
                f"Место: {escape(tournament.place)}\n"
                f"Гости: {guest_count}/{tournament.guest_capacity} "
                f"(общая вместимость: {tournament.capacity})",
                reply_markup=kb.get_admin_tournament_actions_keyboard(tournament_id),
                parse_mode="HTML",
            )
            await callback.answer()
            return

logger = logging.getLogger(__name__)
