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

@user.message(Command("id"))
async def id_command(message: Message):
    await message.answer(f"Ваш айди: {message.from_user.id}")

@user.message(BannedProtect())
async def show_message_to_ban_user(message: Message):
    await message.answer("Вы забанены за плохое поведение!")

@user.message(CommandStart())
async def start_command(message: Message):
    await add_in_mailing(chat_id=message.from_user.id)
    sticker_id = "CAACAgIAAxkBAAEuSs5nBl1rNuFirPiPXjRVrUDOwTuMBgAClCEAApog6Ep3hdlbdFG1aTYE"
    await message.answer_sticker(sticker_id)
    await message.answer(f"Добро пожаловать, {message.from_user.first_name}!",
                         reply_markup=await kb.get_start_menu(rights="user"))

@user.message(Command("help"))
async def help_command(message: Message):
    links = [
        {
            'text': 'Как зарегистрироваться в клубе в приложении Polemica?',
            'link': 'https://t.me/mafia_itmo/54',
        },
        {
            'text': 'Информация об уровнях игры',
            'link': 'https://t.me/mafia_itmo/64'
        }

    ]

    help_message = """<b>Добро пожаловать в раздел помощи!</b>
    Для того, чтоб записаться на вечер, заполните профиль по кнопке "Редактировать профиль", нажмите "Мероприятия" и выберите интересующий вас вечер. Если вы не пойдёте на вечер, то отмените запись, чтобы другие игроки могли записаться. Ждём вас на играх!
    \nПолезные ссылки:
    """
    for link in links:
        help_message += f"\n\t- <a href='{link['link']}'>{link['text']}</a>"
    help_message += """\nГостям необходимо заполнять форму на каждый вечер <b>до 11 утра среды.</b>
    Внимание: форма переехала на яндекс!
    """

    help_message += '\n\nРазработчики:\n🦋 <a href="https://t.me/high_fly_bird">госпожа Фиалка</a>\n🚴‍♂️ <a href="https://t.me/MrAlex18">господин Велосипедостроитель</a>\n ⚔️<a href="https://t.me/n3s0str3l">господин Несострел</a>'

    await message.answer(help_message,
                         parse_mode="HTML",
                         reply_markup=await kb.get_start_menu(rights="user"))

@user.message(F.text == "🚫Отмена")
async def btn_cancel_click(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменяю действие", reply_markup=await kb.get_start_menu(rights="user"))

@user.message(F.text == "👤Наши контакты")
async def btn_contacts_click(message: Message):
    await message.answer("Наши контакты:", reply_markup=kb.our_contacts)

@user.message(F.text == "💻Тех поддержка")
async def btn_support_click(message: Message):
    await message.answer("Техническая поддержка:", reply_markup=kb.tech_support)

logger = setup_logger()
