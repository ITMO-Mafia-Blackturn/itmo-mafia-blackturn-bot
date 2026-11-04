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

@user.message(ProfileEdit.nickname)
async def process_nickname(message: Message, state: FSMContext):
    nickname = message.text.strip()
    
    if 2<=len(nickname)<=167:
        await state.update_data(nickname=nickname)
        await message.answer("Вы из ИТМО?", reply_markup=kb.are_u_from_itmo_keyboard)
        await state.set_state(ProfileEdit.is_itmo)
    else: 
        await message.answer("Я конечно понимаю, буквы бесплатные, но длина не должна превышать 3 символов и должна быть больше 1")
        return

@user.message(ProfileEdit.is_itmo)
async def process_is_itmo(message: Message, state: FSMContext):
    if message.text not in ["Да, я из ИТМО", "Нет, я не из ИТМО"]:
        await message.answer("Пожалуйста, выберите 'Да, я из ИТМО' или 'Нет, я не из ИТМО'.")
        return

    is_itmo = message.text == "Да, я из ИТМО"
    await state.update_data(is_itmo=is_itmo)

    if not is_itmo:
        await message.answer("Для оформления проходки в университет, пожалуйста, введите ваше ФИО:", reply_markup=await kb.get_user_cancel_button())
        await state.set_state(ProfileEdit.full_name)
    else:
        await message.answer(
            'Напиши свой id с сайта Polemica. Если не зарегистрирован, то отправь "-"',
            reply_markup=await kb.get_user_cancel_button(),
            parse_mode="HTML"
        )
        await state.set_state(ProfileEdit.polemica_id)

@user.message(ProfileEdit.full_name)
async def process_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("Введите ваш номер паспорта (10 цифр):", reply_markup=await kb.get_user_cancel_button())
    await state.set_state(ProfileEdit.passport)

@user.message(ProfileEdit.passport)
async def process_passport(message: Message, state: FSMContext):
    ppt = "".join(message.text.split())
    
    if len(ppt) == 10 and message.text.isdigit():
        await state.update_data(passport=message.text)
        await message.answer("Пожалуйста, введите ваш номер телефона (11 цифр, начиная с 8). Он нужен для проходки:", reply_markup=await kb.get_user_cancel_button())
        await state.set_state(ProfileEdit.phone)
    else:
        await message.answer("Неверный формат паспорта. Пожалуйста, введите 10 цифр.")

@user.message(ProfileEdit.phone)
async def process_phone(message: Message, state: FSMContext):
    if len(message.text) == 11 and message.text.isdigit() and message.text.startswith('8'):
        await state.update_data(phone=message.text)
        await message.answer(
            'Даю согласие на обработку своих персональных данных в соответствии с ФЗ-152.',
            reply_markup=await kb.get_personal_data_agreement_keyboard(),
        )
        await state.set_state(ProfileEdit.personal_data_agreement)
    else:
        await message.answer("Неверный формат телефона. Пожалуйста, введите 11 цифр, начиная с 8.")

@user.message(ProfileEdit.personal_data_agreement)
async def process_personal_data_agreement(message: Message, state: FSMContext):
    if message.text == "✅Даю согласие":
        await state.update_data(personal_data_agreement=True)
        await message.answer(
            'Напиши свой id с сайта Polemica. Если не зарегистрирован, то отправь "-"',
            reply_markup=await kb.get_user_cancel_button(),
            parse_mode="HTML"
        )
        await state.set_state(ProfileEdit.polemica_id)
    else:
        await message.answer("Для продолжения необходимо дать согласие на обработку персональных данных. Пожалуйста, начните заново")
        return

@user.message(ProfileEdit.polemica_id)
async def process_polemica_id(message: Message, state: FSMContext):
    if message.text.isdigit():
        await state.update_data(polemica_id=int(message.text))

    await message.answer(
        'Выберите свой уровень. Описание уровней есть в <a href="https://t.me/mafia_itmo/64">посте</a>',
        reply_markup=await kb.get_level_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ProfileEdit.level)

@user.callback_query(ProfileEdit.level)
async def process_level(callback: CallbackQuery, state: FSMContext):
    level_id = int(callback.data.split("_")[1])
    selected_level = next(
        (lvl for lvl in kb.LEVEL_DESCR if lvl["level_id"] == level_id), None)

    if selected_level:
        await state.update_data(level=selected_level)
        data = await state.get_data()

        nickname = data['nickname']
        is_itmo = data['is_itmo']
        level_data = data['level']
        polemica_id = data.get("polemica_id", None)

        full_name = data.get("full_name")
        passport = data.get("passport")
        phone = data.get("phone")
        username = callback.from_user.username

        await save_user_profile(
            chat_id=callback.from_user.id,
            nickname=nickname,
            is_itmo=is_itmo,
            level=level_data['level_id'],
            polemica_id=polemica_id,
            full_name=full_name,
            passport=passport,
            phone=phone,
            username=username
        )
        
        await update_user_signups_profile(
            chat_id=callback.from_user.id,
            nickname=nickname,
            level=level_data['level_id']
        )

        if data.get("tournament_registration_flow"):
            from bot.tournament_user import continue_tournament_setup

            await state.update_data(tournament_registration_flow=False)
            await callback.answer()
            await continue_tournament_setup(callback.message, state, polemica_id, callback.from_user.id)
            return
        
        profile_info = f"""
            Игровой ник: <b>{nickname}</b>
            Уровень: <b>{level_data['level_name']}</b>
            ИТМО: <b>{'Да' if is_itmo else 'Нет'}</b>
            Polemica id: <b>{polemica_id if polemica_id is not None else 'Не указан'}</b>
            """

        if not is_itmo:
            profile_info += f"""
            ФИО: <b>{full_name}</b>
            Паспорт: <b>{passport}</b>
            Телефон: <b>{phone}</b>
            """

        await callback.message.answer(
            f"⭐️ Ваш профиль успешно обновлен!\n{profile_info}",
            parse_mode="HTML",
            reply_markup=await kb.get_start_menu(rights="user")
        )
        await callback.answer()
        await state.clear()
    else:
        await callback.message.answer("Ошибка выбора уровня. Попробуйте снова.")
        await callback.answer()

logger = setup_logger()
