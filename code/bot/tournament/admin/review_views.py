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

def _missing_photo_png() -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        content = name + data
        return (
            struct.pack(">I", len(data))
            + content
            + struct.pack(">I", zlib.crc32(content) & 0xFFFFFFFF)
        )

    width = height = 100
    pixels = b"".join(b"\x00" + b"\xe8\xe8\xe8" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )

def _registration_list_text(
    tournament_name: str, registrations: list[TournamentRegistrationCard]
) -> list[str]:
    lines = [f"<b>{escape(tournament_name)}</b>", "Записи на турнир:"]
    for number, registration in enumerate(registrations, start=1):
        lines.append(
            f"{number}. {escape(registration.polemica_nickname or 'не указан')}, "
            f"Polemica ID: {registration.polemica_id or 'не указан'} — "
            f"{escape(registration_status_from_card(registration))}"
        )
    text = "\n".join(lines)
    if len(text) <= 4000:
        return [text]

    chunks = [lines[:2]]
    for line in lines[2:]:
        current = "\n".join(chunks[-1])
        if len(current) + len(line) + 1 > 4000:
            chunks.append([])
        chunks[-1].append(line)
    return ["\n".join(chunk) for chunk in chunks]

def registration_status_from_card(registration: TournamentRegistrationCard) -> str:
    if registration.rejected:
        reason = registration.rejection_reason or "причина не указана"
        return f"отклонена: {reason}"
    return "подтверждена" if registration.approved else "не подтверждена"

def _review_text(registration: TournamentRegistrationCard) -> str:
    level_info = kb.get_level_info_by_id(registration.bot_level)
    level = level_info["level_name"] if level_info else str(registration.bot_level)
    level_symbol = level_info.get("level_symbol", "") if level_info else ""
    lines = [
        f"<b>Заявка на турнир</b>",
        f"Турнир №{registration.tournament_id}",
        f"Дата: {registration.tournament_date:%d.%m.%Y %H:%M}",
        f"Место: {escape(registration.tournament_place)}",
        f"Статус: {escape(registration_status(registration))}",
        "",
        "<b>Профиль Polemica</b>",
        f"Ник: {escape(registration.polemica_nickname or 'не указан')}",
        f"Polemica ID: {registration.polemica_id or 'не указан'}",
        "",
        "<b>Профиль бота</b>",
        f"ID профиля: {registration.user_profile_id}",
        f"Игровой ник: {escape(registration.bot_nickname)}",
        f"Уровень: {level_symbol} {level}",
        f"ИТМО: {'да' if registration.is_itmo else 'нет'}",
        f"Polemica ID в профиле: {registration.profile_polemica_id or 'не указан'}",
        f"Telegram ID: {registration.chat_id}",
        f"Telegram username: @{escape(registration.telegram_username or 'не указан')}",
        f"ФИО: {escape(registration.full_name or 'не указано')}",
        f"Паспорт: {escape(registration.passport or 'не указан')}",
        f"Телефон: {escape(registration.phone or 'не указан')}",
        "Согласие на обработку данных: "
        f"{'да' if registration.personal_data_agreement else 'нет'}",
    ]
    return "\n".join(lines)

async def _render_registration_card(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    registration_id: int,
    queue_index: int,
    queue: list[int],
) -> bool:
    registration = await get_registration_card(registration_id)
    if registration is None:
        return False

    text = _review_text(registration)
    data = await state.get_data()
    message_id = data.get("tournament_review_message_id")
    markup = kb.get_registration_review_keyboard(
        registration_id,
        can_decide=not registration.approved and not registration.rejected,
    )
    photo = registration.photo or _missing_photo_png()
    media = InputMediaPhoto(
        media=BufferedInputFile(
            photo,
            filename="profile.jpg" if registration.photo else "profile.png",
        ),
        caption=text,
        parse_mode="HTML",
    )
    if isinstance(message_id, int):
        await bot.edit_message_media(
            chat_id=chat_id,
            message_id=message_id,
            media=media,
            reply_markup=markup,
        )
    else:
        photo_message = await bot.send_photo(
            chat_id=chat_id,
            photo=media.media,
            caption=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
        message_id = photo_message.message_id
    await state.update_data(
        tournament_registration_ids=queue,
        tournament_registration_index=queue_index,
        tournament_review_message_id=message_id,
        tournament_review_chat_id=chat_id,
    )
    return True

async def _send_registration_card(
    callback: CallbackQuery,
    state: FSMContext,
    registration_id: int,
    queue_index: int,
    queue: list[int],
) -> None:
    data = await state.get_data()
    is_new_card = not isinstance(data.get("tournament_review_message_id"), int)
    rendered = await _render_registration_card(
        callback.bot,
        callback.message.chat.id,
        state,
        registration_id,
        queue_index,
        queue,
    )
    if not rendered:
        await callback.answer("Заявка или профиль не найдены.", show_alert=True)
        return
    if is_new_card:
        await callback.message.delete()
    await callback.answer()

async def _finish_registration_review(
    bot: Bot,
    chat_id: int,
    message_id: int,
    state: FSMContext,
    text: str,
) -> None:
    data = await state.get_data()
    if isinstance(data.get("tournament_review_message_id"), int):
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text,
            reply_markup=None,
        )
    else:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=None,
        )
    await state.clear()

async def _show_next_pending(
    callback: CallbackQuery, state: FSMContext, tournament_id: int
) -> None:
    queue = await get_pending_registration_ids(tournament_id)
    if not queue:
        await _finish_registration_review(
            callback.bot,
            callback.message.chat.id,
            callback.message.message_id,
            state,
            "Неподтверждённых заявок больше нет.",
        )
        await callback.answer()
        return
    await _send_registration_card(callback, state, queue[0], 0, queue)

async def _notify_applicant(
    bot: Bot, admin_message: Message, chat_id: int, text: str
) -> None:
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except TelegramAPIError as exc:
        logger.warning("Could not notify tournament applicant %s: %s", chat_id, exc)
        await admin_message.answer(
            "Статус заявки сохранён, но отправить уведомление пользователю не удалось."
        )

logger = logging.getLogger(__name__)
