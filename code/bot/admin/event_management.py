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

@admin.message(AdminProtect(), F.text == "🎇Создать мероприятие")
async def btn_create_event_click(message: Message, state: FSMContext):
    await state.set_state(AddEvent.name)
    await message.answer("Отправьте название!", reply_markup=kb.admin_cancel_markup)

@admin.message(AddEvent.name)
async def waiting_event_name(message: Message, state: FSMContext):
    event_name = message.text
    if event_name is not None:
        if await check_event_by_name(event_name=event_name) is None:
            await state.update_data(name=event_name)
            await message.answer("Введите дату и время мероприятия!\nПример: 12.02.2024 15:00",
                                 reply_markup=kb.admin_cancel_markup)
            await state.set_state(AddEvent.date)
        else:
            await message.answer("Мероприятие с таким названием уже существует!", reply_markup=kb.admin_panel)
            await state.clear()
    else:
        await message.answer("Некорректное название!\nПопробуйте ещё раз!", reply_markup=kb.admin_cancel_markup)

@admin.message(AddEvent.date)
async def waiting_date_of_event(message: Message, state: FSMContext):
    # Проверка на соответствие сообщения шаблону дд.мм.гггг чч.мм
    reg_exp = "^(0[1-9]|[12][0-9]|3[01]).(0[1-9]|1[0-2]).20([2][4]|[2-9][0-9]) ([0-1][0-9]|[2][0-3]):[0-5][0-9]$"
    date = message.text
    if date is not None and search(compile(reg_exp), date):
        last_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        data_from_admin = date.split()[0]
        day = int(data_from_admin[:2])
        month = int(data_from_admin[3:5])
        year = int(data_from_admin[6:])
        # Проверка года на високосность
        if (year % 4 == 0 and year % 100 != 0 or year % 400 == 0):
            last_days_in_month[1] = 29
        # Проверяем введённую дату на корректность
        if (day <= last_days_in_month[month - 1]):
            await state.update_data(date=date)
            await message.answer("Введите описание мероприятия!", reply_markup=kb.admin_cancel_markup)
            await state.set_state(AddEvent.description)
        else:
            await message.answer("Некорректная дата!", reply_markup=kb.admin_cancel_markup)
    else:
        await message.answer("Некорректная дата и время!\nПопробуйте ещё раз!", reply_markup=kb.admin_cancel_markup)

@admin.message(AddEvent.description)
async def waiting_event_desc(message: Message, state: FSMContext):
    description = message.text
    if description is not None:
        await state.update_data(description=description)
        await message.answer("Введите лимит участников для мероприятия (целое число):",
                             reply_markup=kb.admin_cancel_markup)
        await state.set_state(AddEvent.limit)
    else:
        await message.answer("Некорректное описание!\nПопробуйте ещё раз!", reply_markup=kb.admin_cancel_markup)

@admin.message(AddEvent.limit)
async def waiting_event_limit(message: Message, state: FSMContext):
    try:
        limit = int(message.text)
        if limit > 0:
            await state.update_data(limit=limit)
            data_from_state: dict = await state.get_data()
            event_name: str = data_from_state.get("name")
            event_date: str = data_from_state.get("date")
            event_description: str = data_from_state.get("description")
            await message.answer(f"Подтвердите создание мероприятия!"
                                 f"\nНазвание: {event_name}"
                                 f"\nДата и время: {event_date}"
                                 f"\nОписание: {event_description}"
                                 f"\nЛимит участников: {limit}",
                                 reply_markup=await kb.get_confirm_menu(callback="confirm_add_event"))
            await state.set_state(AddEvent.confirm)
        else:
            await message.answer("Лимит должен быть положительным числом!\nПопробуйте ещё раз!",
                                 reply_markup=kb.admin_cancel_markup)
    except ValueError:
        await message.answer("Некорректный лимит!\nВведите целое число!", reply_markup=kb.admin_cancel_markup)

@admin.callback_query(AddEvent.confirm)
async def confirm_create_event_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    if callback.data == "confirm_add_event":
        data_from_state: dict = await state.get_data()
        event_name: str = data_from_state.get("name")
        event_date: datetime = datetime.strptime(data_from_state.get("date"), "%d.%m.%Y %H:%M")
        event_description: str = data_from_state.get("description")
        event_limit: int = data_from_state.get("limit")
        await add_event_to_table(event_name=event_name, event_description=event_description, event_date=event_date,
                                 event_limit=event_limit)
        await callback.message.answer("Мероприятие добавлено!", reply_markup=kb.admin_panel)
        await state.clear()
    else:
        await callback.message.answer("Отменяю создание!\nВведите название мероприятия!",
                                      reply_markup=kb.admin_cancel_markup)
        await state.set_state(AddEvent.name)

@admin.message(AdminProtect(), F.text == "🎆Удалить мероприятие")
async def btn_delete_event_click(message: Message, state: FSMContext):
    if await get_count_of_events() > 0:
        events_enumerate: str = ""
        for event in await get_unremoved_events():
            events_enumerate += f"{event.id}. {event.name}\n"
        await message.answer(f"Отправьте номер мероприятия!\n{events_enumerate}", reply_markup=kb.admin_cancel_markup)
        await state.set_state(DelEvent.id)
    else:
        await message.answer("Нет мероприятий,которые можно удалить!", reply_markup=kb.admin_panel)
        await state.clear()

@admin.message(DelEvent.id)
async def waiting_id_of_event(message: Message, state: FSMContext):
    event_id = message.text
    if event_id is not None and event_id.isdigit():
        if await check_event_by_id(event_id=int(event_id)):
            await state.update_data(id=event_id)
            await message.answer(f"Подтвердите удаление мероприятия!\n{event_id}. "
                                 f"{(await get_event_name_by_id(event_id=int(event_id))).name}",
                                 reply_markup=await kb.get_confirm_menu(callback="confirm_del_event"))
            await state.set_state(DelEvent.confirm)
        else:
            await message.answer("Мероприятия с таким номером не существует!", reply_markup=kb.admin_panel)
            await state.clear()
    else:
        await message.answer("Некорректный номер!\nПопробуйте ещё раз!", reply_markup=kb.admin_cancel_markup)

@admin.callback_query(DelEvent.confirm)
async def confirm_del_event_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    if callback.data == "confirm_del_event":
        data_from_state: dict = await state.get_data()
        event_id: str = data_from_state.get("id")
        await remove_event_from_table(event_id=int(event_id))
        await callback.message.answer("Мероприятие удалено!", reply_markup=kb.admin_panel)
        await state.clear()
    else:
        await callback.message.answer("Отменяю удаление!\nВведите другой порядковый номер!",
                                      reply_markup=kb.admin_cancel_markup)
        await state.set_state(DelEvent.id)

logger = setup_logger()
