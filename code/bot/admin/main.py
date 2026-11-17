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

@admin.message(AdminProtect(), CommandStart())
async def start_command(message: Message):
    await message.answer_sticker("CAACAgIAAxkBAAEuTUVnBrozLFYSUZMvbHFKt2wY4tPUggAC-AgAAlwCZQPhVpkp0NcHSTYE")
    await message.answer(f"Добро пожаловать, {message.from_user.first_name}!",
                         reply_markup=await kb.get_start_menu(rights="admin"))

@admin.message(AdminProtect(), F.text == "⚙️Админ панель")
async def btn_admin_panel_click(message: Message):
    await message.answer("Открываю админ.панель", reply_markup=kb.admin_panel)

@admin.message(AdminProtect(), F.text == "🤖Назад")
async def btn_back_to_start_menu_click(message: Message):
    await message.answer("Открываю меню", reply_markup=await kb.get_start_menu(rights="admin"))

@admin.message(AdminProtect(), F.text == "🚫Забанить пользователя")
async def btn_ban_user_click(message: Message, state: FSMContext):
    await message.answer("Отправьте айди пользователя...", reply_markup=kb.admin_cancel_markup)
    await state.set_state(BanUser.id)

logger = setup_logger()
