import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import bot.keyboards as kb
from bot.admin.filters import AdminProtect
from bot.admin.states import Mailing
from database.requests import (
    check_admin,
    check_event_by_id,
    get_chat_ids_for_all_users_in_mailing,
    get_chat_ids_for_users_in_mailing,
    get_unremoved_events,
)

admin = Router()
logger = logging.getLogger(__name__)


async def ask_for_message(message: Message, state: FSMContext) -> None:
    await state.set_state(Mailing.message)
    await message.answer(
        "Отправьте текст сообщения для рассылки...",
        reply_markup=kb.admin_cancel_markup,
    )


@admin.message(AdminProtect(), F.text == "🗣️Сделать рассылку")
async def btn_mailing_click(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Mailing.choose_audience)
    await message.answer(
        "Кому отправить рассылку?",
        reply_markup=kb.mailing_audience_markup,
    )


@admin.callback_query(Mailing.choose_audience, F.data.startswith("mailing:"))
async def choose_mailing_audience(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await check_admin(chat_id=callback.from_user.id):
        await state.clear()
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    if callback.data not in {"mailing:all", "mailing:event"}:
        await callback.answer("Некорректный выбор.", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    if callback.data == "mailing:all":
        await state.update_data(audience="all")
        await ask_for_message(callback.message, state)
        return

    events = list(await get_unremoved_events())
    if not events:
        await state.clear()
        await callback.message.answer(
            "Нет мероприятий для рассылки.", reply_markup=kb.admin_panel
        )
        return

    events_enumerate = "".join(f"{event.id}. {event.name}\n" for event in events)
    await state.set_state(Mailing.choose_event)
    await callback.message.answer(
        f"Отправьте номер мероприятия:\n{events_enumerate}",
        reply_markup=kb.admin_cancel_markup,
    )


@admin.message(AdminProtect(), Mailing.choose_event)
async def waiting_id_of_event(message: Message, state: FSMContext) -> None:
    if message.text and message.text.isdecimal():
        event = await check_event_by_id(event_id=int(message.text))
        if event is not None and not event.removed:
            await state.update_data(audience="event", event_id=event.id)
            await ask_for_message(message, state)
            return
        await message.answer(
            "Мероприятия с таким номером не существует!",
            reply_markup=kb.admin_cancel_markup,
        )
        return

    await message.answer(
        "Некорректный номер!\nПопробуйте ещё раз!",
        reply_markup=kb.admin_cancel_markup,
    )


@admin.message(AdminProtect(), Mailing.message)
async def wait_mailing_message(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Для рассылки отправьте текстовое сообщение.")
        return

    await state.update_data(message=message.text)
    await message.answer(
        f"Подтвердите рассылку!\n\n{message.text}",
        reply_markup=await kb.get_confirm_menu(callback="confirm_mailing"),
    )
    await state.set_state(Mailing.confirm)


@admin.callback_query(Mailing.confirm)
async def confirm_mailing_callback(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await check_admin(chat_id=callback.from_user.id):
        await state.clear()
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    if callback.data not in {"confirm_mailing", "unconfirm_mailing"}:
        await callback.answer()
        return

    await callback.answer()
    await callback.message.delete()
    if callback.data == "unconfirm_mailing":
        await state.set_state(Mailing.message)
        await callback.message.answer(
            "Отменяю рассылку!\nВведите новый текст сообщения.",
            reply_markup=kb.admin_cancel_markup,
        )
        return

    data = await state.get_data()
    await state.clear()
    message_text = data["message"]

    if data["audience"] == "all":
        users = await get_chat_ids_for_all_users_in_mailing()
    else:
        users = await get_chat_ids_for_users_in_mailing(event_id=data["event_id"])

    successful_sends = 0
    failed_sends = 0
    for user_id in users:
        try:
            await callback.bot.send_message(chat_id=user_id, text=message_text)
            successful_sends += 1
        except TelegramAPIError as exc:
            failed_sends += 1
            logger.warning(
                "Не удалось отправить рассылку пользователю %s: %s",
                user_id,
                exc,
            )
        await asyncio.sleep(0.05)

    await callback.message.answer(
        f"Рассылка завершена.\n"
        f"Успешно отправлено: {successful_sends}\n"
        f"Не удалось отправить: {failed_sends}",
        reply_markup=kb.admin_panel,
    )
