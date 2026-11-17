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

@user.message(F.text == "🎉Мероприятия")
async def btn_events_click(message: Message):
    # Проверяем количество существующих мероприятий
    if await get_count_of_events() == 0:
        await message.answer("Нет мероприятий на которые можно записаться!")
    else:
        await message.answer("Выберите интересующее вас мероприятие!",
                             reply_markup=await kb.get_events_names_buttons())

@user.message(F.text == "👈Назад")
async def btn_back_click(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Открываю меню", reply_markup=await kb.get_start_menu(rights="user"))

@user.message(F.text == "🔄Обновить список")
async def refresh_registered_users(message: Message, state: FSMContext):
    data = await state.get_data()
    event_name = data.get('event_name')
    if event_name:
        await btn_event_name_click(message, state, event_name)
    else:
        await message.answer("Извините, не удалось обновить список. Пожалуйста, выберите мероприятие заново.")

@user.message(EventCheck())
async def btn_event_name_click(message: Message, state: FSMContext, event_name: str = None):
    t = perf_counter()
    event_info_for_message = '''🎉Название мероприятия: {event_name}
📆Дата и время проведения: <b>{event_date}</b>
🎊Описание: {event_desc}
👤Ограничение: <b>{event_limit} игроков</b>
✏️Запись: <b>{is_signup_open_str}</b>\n'''

    user_data_str = '''
📁Ваши данные :
👤Ник: {signup_user_full_name}\n
'''
    
    registered_users_str = "\nСписок зарегистрированных пользователей:\n{registered_users_list}\n"
    grouped_by_level_str = "\n"
    
    
    if event_name is None:
        event_name = message.text
        await state.set_state(EventSignUp.event_name)
        await state.update_data(event_name=event_name)
        # await message.answer_sticker("CAACAgIAAxkBAAEDpPBl1WcOfjU0kJaSf9y882BG36ONiwACMw4AApVxCUiC2Rae9Yv1wzQE")

    await state.set_state(EventSignUp.event_name)
    chat_id = message.from_user.id
    event_info, is_signup_open, guest_count, passes_sent, registered_users, signup = await asyncio.gather(
    get_event_info_by_name(event_name=event_name),
    check_is_signup_open(event_name=event_name),
    get_guest_count_for_event(event_name=event_name),
    check_passes_sent(event_name=event_name),
    get_signup_people(event_name=event_name),
    check_signup(event_name=event_name, chat_id=chat_id),
    )
    # event_info = await get_event_info_by_name(event_name=event_name)
    event_date = event_info.date
    event_desc = event_info.description
    event_limit = event_info.limit
    # is_signup_open = await check_is_signup_open(event_name=event_name)
    is_signup_open_str = "открыта" if is_signup_open is not None else "закрыта"
    event_status = 'unsigned' if is_signup_open is not None else ''
    # guest_count = await get_guest_count_for_event(event_name=event_name)
    event_info_for_message += f"👥Гостей: {guest_count}/{event_info.guest_limit}\n"
    
    # Добавить информацию о статусе проходок
    # passes_sent = await check_passes_sent(event_name=event_name)
    if passes_sent:
        event_info_for_message += "🚫 Запись гостей закрыта (проходки отправлены)\n"

    # Get the list of registered users
    # registered_users = await get_signup_people(event_name=event_name)
    
    # print("EVENT:", repr(event_name))
    # print("REGISTERED USERS:")
    # print(registered_users)

    # Create a string with the list of registered users
    registered_users_list = []
    # print(registered_users)
    nicks = registered_users['Полное имя']
    tgs = registered_users['Никнейм']
    levels = registered_users['Уровень']
    colleges = registered_users['вуз']
    is_signup_open_str = "открыта" if len(nicks) < event_limit else "закрыта"
    level_dict: dict = {level['level_id']: level['level_symbol'] for level in kb.LEVEL_DESCR 
                        }
        
    for i, (nick, level_id, username, college) in enumerate(zip(nicks, levels, tgs, colleges), start=1):
        level_symbol = level_dict.get(level_id, '')

        registered_users_list.append(f"{i}. {level_symbol} {nick} - @{username} - <i>{college}</i>")

    registered_users_str = '\n'.join(registered_users_list)


    # print("LEVEL_DESCR:", kb.LEVEL_DESCR)
    # print("levels:", levels)

    reg_dict = {
    level['level_symbol']: 0
    for level in kb.LEVEL_DESCR
    if not level.get("hidden", False)
    }

    for level_id in levels:
        symbol = level_dict.get(level_id)

        if symbol in reg_dict:
            reg_dict[symbol] += 1

    grouped_by_level_str = "\n".join(
        f"{symbol}: 👤{count}"
        for symbol, count in reg_dict.items()
    )
    
    if signup is None:
        # Пользователь не записан или запись отменена
        await message.answer(
            event_info_for_message.format(
                event_name=event_name,
                event_date=event_date,
                event_desc=event_desc,
                is_signup_open_str=is_signup_open_str,
                event_limit=event_limit
            ) + registered_users_str + "\n\n" + grouped_by_level_str,
            parse_mode="HTML",
            reply_markup=await kb.get_event_menu(rights="user", event_status="unsigned", event_name=event_name)
        )
    else:
        full_info_about_signup_user = await get_full_info_about_singup_user(event_name=event_name, chat_id=chat_id)
        signup_user_full_name = full_info_about_signup_user.full_name

        if await check_go_to_event(event_name=event_name, chat_id=chat_id) is not None:
            await message.answer(
                event_info_for_message.format(event_name=event_name, event_date=event_date, event_desc=event_desc,
                                              is_signup_open_str=is_signup_open_str, event_limit=event_limit) +
                "🛎Статус : пойду\n" +
                registered_users_str + "\n\n" + grouped_by_level_str,
                parse_mode="HTML",
                reply_markup=await kb.get_event_menu(rights="user", event_status="signed", event_name=event_name)
            )
        else:
            await message.answer(
                event_info_for_message.format(event_name=event_name, event_date=event_date, event_desc=event_desc,
                                              is_signup_open_str=is_signup_open_str, event_limit=event_limit) +
                user_data_str.format(signup_user_full_name=signup_user_full_name) +
                f"\n🛎Статус : не пойду"
                f"\n\n{registered_users_str}\n\n"
                f"\n{grouped_by_level_str}",
                parse_mode="HTML",
                reply_markup=await kb.get_event_menu(rights="user", event_name=event_name)
            )
    print(perf_counter()-t)

logger = setup_logger()
