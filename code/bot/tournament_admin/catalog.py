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

from bot.tournament_admin.common import (
    TournamentCreationData, _is_admin, _is_admin_message,
    _tournament_creation_data_text, _ask_tournament_creation_field,
)

@tournament_admin.message(F.text == "🏆Турниры", _is_admin_message)
async def open_admin_tournaments(message: Message, state: FSMContext) -> None:
    await state.clear()
    tournaments = await get_tournaments()
    if not tournaments:
        await message.answer("Турниров пока нет.")
        return
    await message.answer(
        "Выберите турнир:",
        reply_markup=kb.get_admin_tournament_keyboard(tournaments),
    )

@tournament_admin.message(F.text == "📦Архивировать турнир")
async def start_tournament_archiving(
    message: Message, state: FSMContext
) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    await state.clear()
    tournaments = [
        tournament
        for tournament in await get_tournaments()
        if not tournament.expired
    ]
    if not tournaments:
        await message.answer("Нет турниров, которые можно архивировать.")
        return
    await message.answer(
        "Выберите турнир. Архивация закроет запись, но сохранит все заявки.",
        reply_markup=kb.get_admin_tournament_archive_keyboard(tournaments),
    )

@tournament_admin.message(F.text == "➕Добавить турнир")
async def start_tournament_creation(message: Message, state: FSMContext) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    await state.clear()
    await state.set_state(TournamentAdminState.create_name)
    await _ask_tournament_creation_field(
        message,
        "Введите название турнира (до 700 символов).",
    )

@tournament_admin.message(TournamentAdminState.create_name)
async def receive_tournament_name(
    message: Message, state: FSMContext
) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        await state.clear()
        return
    name = (message.text or "").strip()
    if not name or len(name) > 700:
        await message.answer("Введите название длиной от 1 до 700 символов.")
        return

    await state.update_data(name=name)
    await state.set_state(TournamentAdminState.create_description)
    await _ask_tournament_creation_field(
        message, "Введите описание турнира (от 1 до 700 символов)."
    )

@tournament_admin.message(TournamentAdminState.create_description)
async def receive_tournament_description(
    message: Message, state: FSMContext
) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        await state.clear()
        return
    description = (message.text or "").strip()
    if not description or len(description) > 700:
        await message.answer("Введите описание длиной от 1 до 700 символов.")
        return

    await state.update_data(description=description)
    await state.set_state(TournamentAdminState.create_place)
    await _ask_tournament_creation_field(
        message, "Введите место проведения (до 150 символов)."
    )

@tournament_admin.message(TournamentAdminState.create_place)
async def receive_tournament_place(message: Message, state: FSMContext) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        await state.clear()
        return
    place = (message.text or "").strip()
    if not place or len(place) > 150:
        await message.answer("Введите место длиной от 1 до 150 символов.")
        return

    await state.update_data(place=place)
    await state.set_state(TournamentAdminState.create_date)
    await _ask_tournament_creation_field(
        message, "Введите дату и время турнира в формате ДД.ММ.ГГГГ ЧЧ:ММ."
    )

@tournament_admin.message(TournamentAdminState.create_date)
async def receive_tournament_date(message: Message, state: FSMContext) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        await state.clear()
        return
    try:
        tournament_date = datetime.strptime(
            (message.text or "").strip(), "%d.%m.%Y %H:%M"
        )
    except ValueError:
        await message.answer(
            "Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ."
        )
        return

    await state.update_data(date=tournament_date)
    await state.set_state(TournamentAdminState.create_registry_deadline)
    await _ask_tournament_creation_field(
        message,
        "Введите дедлайн регистрации в формате ДД.ММ.ГГГГ ЧЧ:ММ. "
        "Он должен быть не позже даты турнира.",
    )

@tournament_admin.message(TournamentAdminState.create_registry_deadline)
async def receive_tournament_registry_deadline(
    message: Message, state: FSMContext
) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        await state.clear()
        return
    try:
        deadline = datetime.strptime(
            (message.text or "").strip(), "%d.%m.%Y %H:%M"
        )
    except ValueError:
        await message.answer(
            "Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ."
        )
        return

    data = await state.get_data()
    tournament_date = data.get("date")
    if not isinstance(tournament_date, datetime) or deadline > tournament_date:
        await message.answer("Дедлайн регистрации должен быть не позже даты турнира.")
        return

    await state.update_data(registry_deadline=deadline)
    await state.set_state(TournamentAdminState.create_capacity)
    await _ask_tournament_creation_field(
        message, "Введите вместимость турнира — положительное целое число."
    )

@tournament_admin.message(TournamentAdminState.create_capacity)
async def receive_tournament_capacity(
    message: Message, state: FSMContext
) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        await state.clear()
        return
    capacity_text = (message.text or "").strip()
    if (
        not capacity_text.isdigit()
        or len(capacity_text) > 10
        or int(capacity_text) <= 0
        or int(capacity_text) > 2_147_483_647
    ):
        await message.answer("Вместимость должна быть положительным целым числом.")
        return

    await state.update_data(capacity=int(capacity_text))
    await state.set_state(TournamentAdminState.create_guest_capacity)
    await _ask_tournament_creation_field(
        message,
        "Введите вместимость для гостей (не из ИТМО), от 0 до общей вместимости.",
    )

@tournament_admin.message(TournamentAdminState.create_guest_capacity)
async def receive_tournament_guest_capacity(
    message: Message, state: FSMContext
) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        await state.clear()
        return
    guest_capacity_text = (message.text or "").strip()
    data = await state.get_data()
    capacity = data.get("capacity")
    if (
        not guest_capacity_text.isdigit()
        or len(guest_capacity_text) > 10
        or not isinstance(capacity, int)
        or int(guest_capacity_text) > capacity
    ):
        await message.answer(
            "Вместимость для гостей должна быть целым числом от 0 "
            "до общей вместимости турнира."
        )
        return

    await state.update_data(guest_capacity=int(guest_capacity_text))
    data = await state.get_data()
    await state.set_state(TournamentAdminState.create_confirmation)
    await message.answer(
        _tournament_creation_data_text(data),
        reply_markup=kb.get_tournament_creation_confirmation_keyboard(),
        parse_mode="HTML",
    )

logger = logging.getLogger(__name__)
