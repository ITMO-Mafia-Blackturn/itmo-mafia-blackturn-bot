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

class TournamentCreationData(TypedDict):
    name: str
    description: str
    place: str
    date: datetime
    registry_deadline: datetime
    capacity: int
    guest_capacity: int

async def _is_admin(user_id: int) -> bool:
    return bool(await check_admin(chat_id=user_id))

async def _is_admin_message(message: Message) -> bool:
    return bool(message.from_user) and await _is_admin(message.from_user.id)

def _tournament_creation_data_text(data: TournamentCreationData) -> str:
    return (
        "<b>Проверьте данные турнира</b>\n"
        f"Название: {escape(data['name'])}\n"
        f"Описание: {escape(data['description'])}\n"
        f"Место: {escape(data['place'])}\n"
        f"Дата: {data['date']:%d.%m.%Y %H:%M}\n"
        f"Дедлайн регистрации: "
        f"{data['registry_deadline']:%d.%m.%Y %H:%M}\n"
        f"Вместимость: {data['capacity']}"
        f"\nВместимость для гостей: {data['guest_capacity']}"
    )

async def _ask_tournament_creation_field(
    message: Message, prompt: str
) -> None:
    await message.answer(
        prompt,
        reply_markup=kb.get_tournament_creation_cancel_keyboard(),
    )

logger = logging.getLogger(__name__)
