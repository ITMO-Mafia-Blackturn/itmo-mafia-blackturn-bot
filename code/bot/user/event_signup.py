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

@user.message(F.text == "❌Я не приду", EventSignUp.event_name)
async def btn_dont_go_to_the_event_click(message: Message, state: FSMContext):
    data_from_state: dict = await state.get_data()
    event_name: str = data_from_state.get("event_name")
    chat_id = message.from_user.id
    if await check_signup(event_name=event_name, chat_id=chat_id) is None:
        await message.answer("Для начала запишитесь на мероприятие!")
    else:
        if await check_go_to_event(event_name=event_name, chat_id=chat_id) is not None:
            await state.update_data(id=chat_id)
            await message.answer("Вы точно не пойдёте на мероприятие?",
                                 #  "\nПримечание: после подтверждения вы больше не сможете"
                                 #  " записаться на это мероприятие!",
                                 reply_markup=await kb.get_confirm_menu("cofirm_dont_go_to_event"))
        else:
            await message.answer("Вы уже отменили запись!")

@user.callback_query(EventSignUp.event_name)
async def confirm_signup_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    if callback.data == "cofirm_dont_go_to_event":
        data_from_state: dict = await state.get_data()
        event_name: str = data_from_state.get("event_name")
        chat_id: str = data_from_state.get("id")
        # Предполагается, что эта функция обновляет статус до 0 (отменено)
        await change_signup_status(event_name=event_name, chat_id=chat_id)
        await callback.message.answer("Вы успешно отменили запись!", reply_markup=await kb.get_events_names_buttons())
        await state.clear()
    else:
        await callback.message.answer("Отменяю действие!",
                                      reply_markup=await kb.get_event_menu(rights="user", event_status="signed"))

@user.message(F.text == "🔙Назад")
async def btn_exit_from_events_click(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Перехожу назад", reply_markup=await kb.get_events_names_buttons())

@user.message(F.text == "📝Записаться", EventSignUp.event_name)
async def btn_signup_click(message: Message, state: FSMContext):
    data_from_state: dict = await state.get_data()
    event_name: str = data_from_state.get("event_name")
    # Проверка открыта-ли запись
    if await check_is_signup_open(event_name=event_name) is not None:
        # Проверка записи на мерпориятие
        if await check_signup(event_name=event_name, chat_id=message.from_user.id) is None:
            signuped_users = await get_signup_people(event_name=event_name)
            current_signups = len(signuped_users["Полное имя"])
            event_info = await get_event_info_by_name(event_name=event_name)
            user_profile = await get_user_profile(chat_id=message.from_user.id)
            if not user_profile:
                await message.answer(
                    "Заполните профиль, прежде чем записываться на мероприятие. Используйте кнопку '📝Редактировать профиль'",
                    reply_markup=await kb.get_start_menu(rights="user")
                )
            elif not user_profile.is_itmo:
                # Проверить, отправлены ли уже проходки
                if await check_passes_sent(event_name=event_name):
                    await message.answer("Запись гостей на это мероприятие закрыта - проходки уже отправлены.")
                    return
                
                if not all([user_profile.full_name, user_profile.passport, user_profile.phone]):
                    await message.answer("Для записи на мероприятие, пожалуйста, заполните ФИО, паспорт и телефон в вашем профиле. "
                                         "Эти данные необходимы для оформления проходки в университет.")
                    return

                guest_count = await get_guest_count_for_event(event_name)
                if guest_count >= event_info.guest_limit:
                    await message.answer("К сожалению, достигнут лимит гостей для этого мероприятия.")
                    return

            if current_signups >= event_info.limit:
                await message.answer("К сожалению, достигнут лимит участников для этого мероприятия.")

            # получим данные пользователя
            user_profile = await get_user_profile(chat_id=message.from_user.id)
            # print(user_profile.__dict__, '\n\n')
            await state.update_data(full_name=user_profile.nickname,
                                    id=message.from_user.id,
                                    level=user_profile.level,
                                    username=message.from_user.username)
            level_symbol = kb.get_level_info_by_id(
                user_profile.level)['level_symbol']
            await message.answer(f"Подтвердите запись на мероприятие!"
                                 f"\n🎉Название мероприятия : {event_name}"
                                 f"\n📒Ваши данные : "
                                 f"\n👤Игровой ник : {user_profile.nickname}"
                                 f"\n👤Уровень : {level_symbol}"
                                 f"\n👤Ваш Telegram ник : @{message.from_user.username}",
                                 reply_markup=await kb.get_confirm_menu("confirm_signup"))
            await state.set_state(EventSignUp.confirm)

        else:
            await message.answer("Вы уже записались на это мерпориятие!")
    else:
        await message.answer("Запись на мероприятие уже закрыта!")

@user.callback_query(EventSignUp.confirm)
async def confirm_signup_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    if callback.data == "confirm_signup":
        data_from_state: dict = await state.get_data()
        event_name: str = data_from_state.get("event_name")
        user_full_name: str = data_from_state.get("full_name")
        username: str = data_from_state.get("username")

        user_chat_id: str = data_from_state.get("id")
        user_level = data_from_state.get("level")
        user = await get_user_profile(chat_id=int(user_chat_id))

        await add_signup_user(
            event_name=event_name,
            full_name=user_full_name,
            chat_id=user_chat_id,
            username=username,
            level=user_level
        )
        await callback.message.answer("Вы успешно записались!", reply_markup=await kb.get_events_names_buttons())
        await state.clear()
    else:
        await callback.message.answer("Отменяю запись!\nВведите ник снова.",
                                      reply_markup=await kb.get_user_cancel_button())
        await state.set_state(EventSignUp.full_name)

logger = setup_logger()
