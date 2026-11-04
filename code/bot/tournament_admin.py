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
from bot.tournament_user_states import TournamentAdminState
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

logger = logging.getLogger(__name__)
tournament_admin = Router()


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


class TournamentCreationData(TypedDict):
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
        f"Название: {escape(data['description'])}\n"
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
    await state.set_state(TournamentAdminState.create_description)
    await _ask_tournament_creation_field(
        message,
        "Введите название или описание турнира (до 700 символов).",
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
        await message.answer("Введите текст длиной от 1 до 700 символов.")
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


@tournament_admin.callback_query(F.data.startswith("tournament_admin:"))
async def handle_tournament_admin_callback(
    callback: CallbackQuery, state: FSMContext
) -> None:
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
            f"<b>{escape(tournament.description)}</b>\n"
            f"Дата: {tournament.date:%d.%m.%Y %H:%M}\n"
            f"Место: {escape(tournament.place)}\n"
            f"Гости: {guest_count}/{tournament.guest_capacity} "
            f"(общая вместимость: {tournament.capacity})",
            reply_markup=kb.get_admin_tournament_actions_keyboard(tournament_id),
            parse_mode="HTML",
        )
        await callback.answer()
        return

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
            for text in _registration_list_text(tournament.description, registrations):
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
                                    f"{tournament.description}"
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
