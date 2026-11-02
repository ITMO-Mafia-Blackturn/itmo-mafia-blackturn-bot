import logging
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram import Bot
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import bot.keyboards as kb
from bot.tournament_user_states import TournamentAdminState
from database.requests import check_admin
from services.tournament_service import (
    TournamentRegistrationCard,
    approve_registration,
    get_all_registrations,
    get_pending_registration_ids,
    get_registration_card,
    get_tournaments,
    reject_registration,
    registration_status,
)

logger = logging.getLogger(__name__)
tournament_admin = Router()


async def _is_admin(user_id: int) -> bool:
    return bool(await check_admin(chat_id=user_id))


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
        f"Игровой ник: {escape(registration.bot_nickname)}",
        f"Уровень: {level}",
        f"ИТМО: {'да' if registration.is_itmo else 'нет'}",
        f"Telegram ID: {registration.chat_id}",
        f"Telegram username: @{escape(registration.telegram_username or 'не указан')}",
        f"ФИО: {escape(registration.full_name or 'не указано')}",
        f"Паспорт: {escape(registration.passport or 'не указан')}",
        f"Телефон: {escape(registration.phone or 'не указан')}",
        "Согласие на обработку данных: "
        f"{'да' if registration.personal_data_agreement else 'нет'}",
    ]
    return "\n".join(lines)


async def _send_registration_card(
    callback: CallbackQuery,
    state: FSMContext,
    registration_id: int,
    queue_index: int,
    queue: list[int],
) -> None:
    registration = await get_registration_card(registration_id)
    if registration is None:
        await callback.answer("Заявка или профиль не найдены.", show_alert=True)
        return

    text = _review_text(registration)
    markup = kb.get_registration_review_keyboard(
        registration_id,
        previous=queue_index > 0,
        following=queue_index < len(queue) - 1,
    )
    await callback.message.delete()
    if registration.photo:
        await callback.message.answer_photo(
            BufferedInputFile(registration.photo, filename="profile.jpg"),
            caption=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
    else:
        await callback.message.answer(
            text,
            reply_markup=markup,
            parse_mode="HTML",
        )
    await state.update_data(
        tournament_registration_ids=queue,
        tournament_registration_index=queue_index,
    )
    await callback.answer()


async def _show_next_pending(
    callback: CallbackQuery, state: FSMContext, tournament_id: int
) -> None:
    queue = await get_pending_registration_ids(tournament_id)
    if not queue:
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("Неподтверждённых заявок больше нет.")
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


@tournament_admin.message(F.text == "🏆Турниры")
async def open_admin_tournaments(message: Message, state: FSMContext) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    await state.clear()
    tournaments = await get_tournaments()
    if not tournaments:
        await message.answer("Турниров пока нет.")
        return
    await message.answer(
        "Выберите турнир:",
        reply_markup=kb.get_admin_tournament_keyboard(tournaments),
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
        await callback.message.edit_text(
            f"<b>{escape(tournament.description)}</b>\n"
            f"Дата: {tournament.date:%d.%m.%Y %H:%M}\n"
            f"Место: {escape(tournament.place)}",
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

    if action == "review":
        tournament_id = int(arguments[0])
        await state.update_data(tournament_admin_id=tournament_id)
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
        if index < 0 or index >= len(queue):
            await callback.answer()
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
    if not isinstance(registration_id, int):
        await state.clear()
        await message.answer("Не удалось определить заявку. Откройте список заново.")
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
    if isinstance(tournament_id, int):
        queue = await get_pending_registration_ids(tournament_id)
        if queue:
            await state.update_data(
                tournament_admin_id=tournament_id,
                tournament_registration_ids=queue,
                tournament_registration_index=0,
            )
            card = await get_registration_card(queue[0])
            if card is not None:
                text = _review_text(card)
                markup = kb.get_registration_review_keyboard(
                    queue[0], previous=False, following=len(queue) > 1
                )
                if card.photo:
                    await message.answer_photo(
                        BufferedInputFile(card.photo, filename="profile.jpg"),
                        caption=text,
                        reply_markup=markup,
                        parse_mode="HTML",
                    )
                else:
                    await message.answer(
                        text, reply_markup=markup, parse_mode="HTML"
                    )
                return
    await state.clear()
    await message.answer("Заявка отклонена. Неподтверждённых заявок больше нет.")
