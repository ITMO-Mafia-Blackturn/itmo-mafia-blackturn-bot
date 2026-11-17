from logging import exception
from unicodedata import category
from aiogram import Router, F
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from time import perf_counter
import asyncio
import re
import bot.keyboards as kb
from bot.keyboards import CLUB_RATING_BUTTON_DATA, STARS_BUTTON_DATA, MY_ACHIEVMENTS_BUTTON_DATA, \
    PAIR_RATING_BUTTON_DATA
from database.requests import (check_ban, check_event_by_name, add_in_mailing, get_event_info_by_name, check_signup,
                               check_go_to_event, get_full_info_about_singup_user, change_signup_status,
                               add_signup_user,
                               get_count_of_events, check_is_signup_open, get_signup_people, get_user_profile,
                               save_user_profile, get_users_with_polemica_id, get_guest_count_for_event,
                               check_passes_sent, update_user_signups_profile)
from plugins.achievements import get_user_achievements_text, get_club_stars_achievements_text
from plugins.rating import get_club_rating
from plugins.research import get_pair_stat_text
from utils import setup_logger

user = Router()

from bot.user.states import EventSignUp, ProfileEdit, Achievements, PairRating, UpdateProfile
from bot.user.filters import BannedProtect, EventCheck

@user.message(F.text == "🌟Достижения и рейтинг")
async def btn_my_achievements(message: Message):
    await message.answer("Выберите подменю",
                         parse_mode="HTML",
                         reply_markup=kb.achivement_rating_menu)
    return

@user.callback_query(F.data == MY_ACHIEVMENTS_BUTTON_DATA)
async def btn_my_achievements(callback_query: CallbackQuery, state: FSMContext):
    message = callback_query.message
    await message.chat.do("typing")
    usr = await get_user_profile(message.chat.id)
    if usr is None or usr.polemica_id is None:
        await message.answer("Незарегистрированный пользователь или нет polemica id",
                             reply_markup=await kb.get_start_menu(rights="user"))
    else:
        await message.answer("Выберите категорию достижений", parse_mode="HTML",
                             reply_markup=await kb.get_achievement_category_keyboard())
        await state.set_state(Achievements.category)
        await message.delete()
    return

@user.callback_query(Achievements.category)
async def btn_my_achievements_with_category(callback_query: CallbackQuery, state: FSMContext):
    message = callback_query.message
    await message.chat.do("typing")
    usr = await get_user_profile(message.chat.id)
    achievements_category = callback_query.data
    await message.answer(get_user_achievements_text(usr.polemica_id, achievements_category, True), parse_mode="HTML",
                         reply_markup=await kb.get_start_menu(rights="user"))
    await message.delete()
    await state.clear()
    return

@user.callback_query(F.data == STARS_BUTTON_DATA)
async def btn_stars(callback_query: CallbackQuery):
    message = callback_query.message
    await message.chat.do("typing")
    text = get_club_stars_achievements_text(list(await get_users_with_polemica_id()))
    await message.answer("".join(text), parse_mode="HTML",
                         reply_markup=await kb.get_start_menu(rights="user"))
    await message.delete()
    return

@user.callback_query(F.data == CLUB_RATING_BUTTON_DATA)
async def btn_rating(callback_query: CallbackQuery):
    message = callback_query.message
    await message.chat.do("typing")
    await message.answer(await get_club_rating(), parse_mode="HTML",
                         reply_markup=await kb.get_start_menu(rights="user"))
    await message.delete()
    return

@user.callback_query(F.data == PAIR_RATING_BUTTON_DATA)
async def btn_pair_rating(callback_query: CallbackQuery, state: FSMContext):
    message = callback_query.message
    await message.chat.do("typing")
    await message.answer("Введите polemica id двух пользователей через запятую для просмотра совместной статистики",
                         parse_mode="HTML",
                         reply_markup=None)
    await state.set_state(PairRating.choose)
    await message.delete()
    return

@user.message(PairRating.choose)
async def pair_rating(message: Message, state: FSMContext):
    await message.chat.do("typing")
    try:
        first_id, second_id = map(lambda it: int(it.strip()), message.text.split(","))
        logger.info(f"Pair rating req for {first_id}, {second_id} from {message.chat.id}")
        await message.answer(get_pair_stat_text(first_id, second_id),
                             parse_mode="HTML",
                             reply_markup=await kb.get_start_menu(rights="user"))
    except Exception as e:
        print(e)
        await message.answer("Ошибка при вводе id", reply_markup=await kb.get_start_menu(rights="user"))
    await state.clear()
    return

logger = setup_logger()
