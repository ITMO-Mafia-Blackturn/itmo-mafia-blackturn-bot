import os
import asyncio
from datetime import datetime
from re import search, compile
import pandas as pd
import httpx
from aiogram import Router, F
from aiogram.filters import CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
import bot.keyboards as kb
from database.requests import (check_ban, check_event_by_name, check_admin, add_in_ban,
                               del_from_ban, add_in_admin, del_from_admin, add_event_to_table, check_event_by_id,
                               get_event_name_by_id, get_count_of_signup,
                               get_event_info_by_name, get_signup_people,
                               check_is_signup_open, close_signup_to_event, get_count_of_events,
                               remove_event_from_table, get_unremoved_events, get_chat_ids_for_users_in_mailing,
                               get_guests_for_event, mark_passes_sent, check_passes_sent, get_admins)
from utils import setup_logger

admin = Router()

from bot.admin.states import *
from bot.admin.filters import AdminProtect, EventCheck

@admin.message(AdminProtect(), F.text == "🗣️Сделать рассылку")
async def btn_mailing_click(message: Message, state: FSMContext):
    if await get_count_of_events() > 0:
        events_enumerate: str = ""
        for event in await get_unremoved_events():
            events_enumerate += f"{event.id}. {event.name}\n"
        await message.answer(f"Отправьте номер мероприятия!\n{events_enumerate}", reply_markup=kb.admin_cancel_markup)
    else:
        await message.answer("Нет мероприятий,которые можно удалить!", reply_markup=kb.admin_panel)
        await state.clear()
    await state.set_state(Mailing.choose_event)

@admin.message(Mailing.choose_event)
async def waiting_id_of_event(message: Message, state: FSMContext):
    event_id = message.text
    if event_id is not None and event_id.isdigit():
        if await check_event_by_id(event_id=int(event_id)):
            await state.update_data(event_id=event_id)
            await state.set_state(Mailing.message)
            await message.answer("Отправьте сообщение для рассылки...", reply_markup=kb.admin_cancel_markup)
        else:
            await message.answer("Мероприятия с таким номером не существует!", reply_markup=kb.admin_panel)
            await state.clear()
    else:
        await message.answer("Некорректный номер!\nПопробуйте ещё раз!", reply_markup=kb.admin_cancel_markup)

@admin.message(Mailing.message)
async def wait_mailing_message(message: Message, state: FSMContext):
    if message.text is not None:
        # Сохраняем сообщение и просим подтвердить рассылку
        await state.update_data(message=message.text)
        await message.answer(f"Подтвердите рассылку!\n\n{message.text}",
                             reply_markup=await kb.get_confirm_menu(callback="confirm_mailing"))
        await state.set_state(Mailing.confirm)
    else:
        await message.answer("Некорректное сообщение для рассылки!\nПопробуйте ещё раз!")

@admin.callback_query(Mailing.confirm)
async def confirm_mailing_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    if callback.data == "confirm_mailing":
        # Получаем список пользователей
        # Получаем сообщение админа
        data_from_state: dict = await state.get_data()
        send_for_event_id: int = data_from_state.get("event_id")
        message_from_admin: str = data_from_state.get("message")
        users = await get_chat_ids_for_users_in_mailing(event_id=send_for_event_id)
        for user in users:
            try:
                await callback.bot.send_message(chat_id=user, text=message_from_admin)
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение пользователю {user}: {e}")
        await callback.message.answer("Рассылка завершена!", reply_markup=kb.admin_panel)
        await state.clear()
    else:
        await callback.message.answer("Отменяю рассылку!\nВведите новое сообщение!",
                                      reply_markup=kb.admin_cancel_markup)
        await state.set_state(Mailing.message)

logger = setup_logger()
