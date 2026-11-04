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

@user.message(F.text == "📝Редактировать профиль")
async def edit_profile(message: Message, state: FSMContext):
    
    user_profile = await get_user_profile(chat_id=message.from_user.id)
    message_to_send = ""
    if user_profile:
        
        await state.update_data(
            chat_id= user_profile.chat_id,
            polemica_id= user_profile.polemica_id,
            nickname= user_profile.nickname,
            is_itmo= user_profile.is_itmo,
            full_name= user_profile.full_name,
            level= user_profile.level,
            passport= user_profile.passport,
            phone= user_profile.phone,
            personal_data_agreement= user_profile.personal_data_agreement,
            username= user_profile.username
         )
         
        profile_text = f"""
        Игровой ник: {user_profile.nickname}
        Уровень: {kb.get_level_info_by_id(user_profile.level)['level_name']}
        Из ИТМО: {"Да" if user_profile.is_itmo else "Нет"}
        Polemica id: {user_profile.polemica_id}
        """
        message_to_send = f"Ваш профиль:\n{profile_text}\nПриступаем к пересозданию профиля...\n\n"
        
        await message.answer(f"""Вы хотите пересоздать профиль с нуля или изменить что-то конкретное?\n"""
                             f"""Чтобы отозвать согласие на обработку персональных данных или ВУЗ (ИТМО / не ИТМО), придется пересоздать профиль""",
                             reply_markup=kb.fields_to_change_keyboard)
        await state.update_data(message_to_send = message_to_send)
        await state.set_state(UpdateProfile.fields)
    else:
        await message.answer(message_to_send + "Введите ваш никнейм:", reply_markup=await kb.get_user_cancel_button())
        await state.set_state(ProfileEdit.nickname)

@user.callback_query(F.data.startswith("fields_"))
async def fields_edit(callback: CallbackQuery, state: FSMContext):
    fields = callback.data.split("_")[1]
    data = await state.get_data()
    user_profile = await get_user_profile(chat_id=callback.from_user.id)
    
    message_to_send = ""
    
    if user_profile:
        message_to_send = (f"""<b>Ваш профиль</b>\n"""
                f"""\tИгровой ник: {user_profile.nickname}\n"""
                f"""\tУровень: {kb.get_level_info_by_id(user_profile.level)['level_name']}\n"""
                f"""\tИз ИТМО: {"Да" if user_profile.is_itmo else "Нет"}\n"""
                f"""\tPolemica id: {user_profile.polemica_id}\n\n""")
    
    if fields == "all":
        
        
        await callback.message.answer(message_to_send + "Введите ваш никнейм:", 
                                      reply_markup=await kb.get_user_cancel_button(), 
                                      parse_mode="HTML")
        await state.set_state(ProfileEdit.nickname)
    else:
        await callback.message.answer(f"""{message_to_send}""" f"""Выберите, что вы хотите изменить:""", 
                                      reply_markup=kb.change_profile_inline_itmo if user_profile.is_itmo else kb.change_profile_inline_not_itmo,
                                      parse_mode="HTML")
        await state.set_state(UpdateProfile.option)
        
    await callback.answer()

@user.callback_query(F.data.startswith("change_"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext):
    
    field_to_change = callback.data.removeprefix("change_")
    
    await state.update_data(field_to_change=field_to_change)

    
    
    ru_fields = {
        "nickname": "новый никнейм",
        "polemica": "новый Polemica ID",
        "FIO": "ФИО",
        "passport": "серию и номер паспорта",
        "telephone_number": "номер телефона"}
    if field_to_change in ["nickname", "polemica", "FIO", "telephone_number", "passport"]:
        await callback.message.edit_text(f"Введите {ru_fields.get(field_to_change, 'поля')}:")
        await state.set_state(UpdateProfile.waiting_for_value)
        
    elif field_to_change == "level":
            await callback.message.answer(
                    'Выберите свой уровень. Описание уровней есть в <a href="https://t.me/mafia_itmo/64">посте</a>',
                    reply_markup=await kb.get_level_keyboard(),
                    parse_mode="HTML"
                )
            await state.set_state(ProfileEdit.level)
    
    await callback.answer()

@user.message(UpdateProfile.waiting_for_value)
async def capture_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field_to_change")
    new_value = message.text

    # Получаем актуальный профиль из БД
    profile = await get_user_profile(chat_id=message.from_user.id)

    if not profile:
        await message.answer("Профиль не найден. Попробуйте создать его заново.")
        await state.clear()
        return

    # Сохраняем прежние значения для всех полей,
    # кроме того, которое пользователь редактирует
    nickname = new_value if field == "nickname" else profile.nickname
    polemica_id = profile.polemica_id
    full_name = profile.full_name
    passport = profile.passport
    phone = profile.phone

    value = (message.text or "").strip()

    if field == "polemica":
        if value == "-":
            polemica_id = None
        elif value.isdigit():
            polemica_id = int(value)
        else:
            await message.answer(
                "Polemica ID должен содержать только цифры. "
                "Если ID отсутствует, отправьте '-'."
            )
            return

        nickname = profile.nickname
        full_name = profile.full_name
        passport = profile.passport
        phone = profile.phone

    elif field == "FIO":
        if len(value) > 150 or len(value.split()) < 2:
            await message.answer(
                "Введите ФИО: минимум имя и фамилию."
            )
            return

        if not re.fullmatch(r"[А-Яа-яЁёA-Za-z-]+(?:\s+[А-Яа-яЁёA-Za-z-]+)+", value):
            await message.answer(
                "ФИО должно содержать только буквы, пробелы и дефисы. "
                "Введите имя и фамилию."
            )
            return

        nickname = profile.nickname
        polemica_id = profile.polemica_id
        full_name = value
        passport = profile.passport
        phone = profile.phone

    elif field == "passport":
        if not re.fullmatch(r"\d{10}", value):
            await message.answer(
                "Серия и номер паспорта должны состоять ровно из 10 цифр."
            )
            return

        nickname = profile.nickname
        polemica_id = profile.polemica_id
        full_name = profile.full_name
        passport = value
        phone = profile.phone

    elif field == "telephone_number":
        if not re.fullmatch(r"8\d{10}", value):
            await message.answer(
                "Введите номер телефона: 11 цифр, начиная с 8."
            )
            return

        nickname = profile.nickname
        polemica_id = profile.polemica_id
        full_name = profile.full_name
        passport = profile.passport
        phone = value
    elif field == "nickname":
        if not 2 <= len(value) <= 167:
            await message.answer(
                "Никнейм должен содержать от 2 до 167 символов. Попробуйте ещё раз."
            )
            return

        nickname = value
        polemica_id = profile.polemica_id
        full_name = profile.full_name
        passport = profile.passport
        phone = profile.phone
    else:
        await message.answer("Неизвестное поле для редактирования.")
        await state.clear()
        return

    await save_user_profile(
        chat_id=profile.chat_id,
        nickname=nickname,
        polemica_id=polemica_id,
        is_itmo=profile.is_itmo,
        level=profile.level,
        full_name=full_name,
        passport=passport,
        phone=phone,
        username=profile.username,
        personal_data_agreement=profile.personal_data_agreement,
    )

    await update_user_signups_profile(
        chat_id=profile.chat_id,
        nickname=nickname,
        level=profile.level,
    )

    # Обновляем FSM, чтобы в нём тоже были актуальные значения
    await state.update_data(
        nickname=nickname,
        polemica_id=polemica_id,
        full_name=full_name,
        passport=passport,
        phone=phone,
        is_itmo=profile.is_itmo,
        level=profile.level,
        username=profile.username,
        personal_data_agreement=profile.personal_data_agreement,
    )
    
    data = await state.get_data()

    profile_info = f"""
                Игровой ник: <b>{nickname}</b>
                Уровень: <b>{kb.get_level_info_by_id(data.get('level'))['level_name']}</b>
                ИТМО: <b>{'Да' if data.get("is_itmo") else 'Нет'}</b>
                Polemica id: <b>{polemica_id if polemica_id is not None else 'Не указан'}</b>
                """
    
    if not data.get('is_itmo'):
            profile_info += f"""
            ФИО: <b>{full_name}</b>
            Паспорт: <b>{passport}</b>
            Телефон: <b>{phone}</b>
    """
    
    await message.answer(
        "Данные успешно обновлены!\n"
        f"{profile_info}",
        parse_mode="HTML"
    )
    print(data.get("is_itmo"))
    await state.clear()

logger = setup_logger()
