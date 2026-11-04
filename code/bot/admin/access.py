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

@admin.message(AdminProtect(), F.text == "🚫Забанить пользователя")
async def btn_ban_user_click(message: Message, state: FSMContext):
    await message.answer("Отправьте айди пользователя...", reply_markup=kb.admin_cancel_markup)
    await state.set_state(BanUser.id)

@admin.message(F.text == "❌Отмена")
async def btn_cancel_action_click(message: Message, state: FSMContext):
    await message.answer("Отменяю действие", reply_markup=kb.admin_panel)
    await state.clear()

@admin.message(BanUser.id)
async def wait_id_to_ban_user(message: Message, state: FSMContext):
    # Проверяем сообщение на корректность
    if message.text is not None and message.text.isdigit():
        await state.clear()
        chat_id = int(message.text)
        if await check_ban(chat_id=chat_id):
            await message.answer("Пользователь уже находиться в бане!", reply_markup=kb.admin_panel)
        elif await check_admin(chat_id=chat_id):
            await message.answer("Нельзя забанить администратора!", reply_markup=kb.admin_panel)
        else:
            await add_in_ban(chat_id=chat_id)
            await message.answer("Пользователь забанен!", reply_markup=kb.admin_panel)
    else:
        await message.answer("Некорректное айди пользователя!\nПопробуйте ещё раз!")

@admin.message(AdminProtect(), F.text == "✅Разбанить пользователя")
async def btn_unban_user_click(message: Message, state: FSMContext):
    await message.answer("Отправьте айди пользователя...", reply_markup=kb.admin_cancel_markup)
    await state.set_state(UnbanUser.id)

@admin.message(UnbanUser.id)
async def wait_id_to_unban(message: Message, state: FSMContext):
    if message.text is not None and message.text.isdigit():
        await state.clear()
        chat_id = int(message.text)
        if await check_ban(chat_id=chat_id):
            await del_from_ban(chat_id=chat_id)
            await message.answer("Пользователь разбанен!", reply_markup=kb.admin_panel)
        else:
            await message.answer("Пользователь никогда не был забанен!", reply_markup=kb.admin_panel)
    else:
        await message.answer("Некорректное айди пользователя!\nПопробуйте ещё раз!")

@admin.message(AdminProtect(), F.text == "➕Добавить админа")
async def btn_add_adm_click(message: Message, state: FSMContext):
    await message.answer("Отправьте айди пользователя...", reply_markup=kb.admin_cancel_markup)
    await state.set_state(AddAdmin.id)

@admin.message(AddAdmin.id)
async def wait_id_to_add_admin(message: Message, state: FSMContext):
    if message.text is not None and message.text.isdigit():
        await state.clear()
        chat_id = int(message.text)
        if await check_admin(chat_id=chat_id):
            await message.answer("Пользователь уже является админом!", reply_markup=kb.admin_panel)
        else:
            await add_in_admin(chat_id=chat_id)
            await message.answer("Администратор добавлен!", reply_markup=kb.admin_panel)
    else:
        await message.answer("Некорректное айди пользователя!\nПопробуйте ещё раз!")

@admin.message(AdminProtect(), F.text == "➖Удалить админа")
async def btn_del_adm_click(message: Message, state: FSMContext):
    admins_ = await get_admins()
    
    admins = admins_.all()
    admins_list = [f"\t\t\t\t{admin.nickname} --- {admin.chat_id}\n" for admin in admins]
    
    await message.answer(
        f"""Список администраторов:

{''.join(admins_list)}
        
        """
    )
    await message.answer("Отправьте айди пользователя...", reply_markup=kb.admin_cancel_markup)
    await state.set_state(DelAdmin.id)

@admin.message(DelAdmin.id)
async def wait_id_to_del_admin(message: Message, state: FSMContext):
    if message.text is not None and message.text.isdigit():
        await state.clear()
        chat_id = int(message.text)
        if await check_admin(chat_id=chat_id):
            await del_from_admin(chat_id=chat_id)
            await message.answer("Администратор удалён!", reply_markup=kb.admin_panel)
        else:
            await message.answer("Такого администратора не существует!", reply_markup=kb.admin_panel)
    else:
        await message.answer("Некорректное айди пользователя!\nПопробуйте ещё раз!")

logger = setup_logger()
