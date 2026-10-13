from logging import exception
from unicodedata import category

from aiogram import Router, F
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from time import perf_counter
import asyncio

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

logger = setup_logger()

# Чтобы не писать dispatcher 2-й раз заменим его на роутер
user = Router()


# Создаём класс (фильтр) для того, чтобы проверить забанен-ли пользователь


class BannedProtect(Filter):
    async def __call__(self, message: Message):
        return await check_ban(chat_id=message.from_user.id)


# Создаём класс (фильтр) для проверки является-ли сообщение названием мероприятия


class EventCheck(Filter):
    async def __call__(self, message: Message):
        return await check_event_by_name(event_name=message.text)


# Создаём класс (состояние) для записи на мероприятие


class EventSignUp(StatesGroup):
    event_name = State()
    full_name = State()
    id = State()
    level = State()
    username = State()
    confirm = State()


#  Состояние для создания профиля пользователя


class ProfileEdit(StatesGroup):
    nickname = State()
    level = State()
    polemica_id = State()
    is_itmo = State()
    full_name = State()
    passport = State()
    phone = State()
    personal_data_agreement = State()


class Achievements(StatesGroup):
    submenu = State()
    category = State()


class PairRating(StatesGroup):
    choose = State()


# Обработаем команду айди


@user.message(Command("id"))
async def id_command(message: Message):
    await message.answer(f"Ваш айди: {message.from_user.id}")


# Обработка сообщений от забаненного пользователя


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

    help_message += '\n\nРазработчики:\n🦋 <a href="https://t.me/high_fly_bird">госпожа Фиалка</a>\n🚴‍♂️ <a href="https://t.me/MrAlex18">господин Велосипедостроитель</a>\n <a href="https://t.me/n3s0strl">господин Несострел</a>'

    await message.answer(help_message,
                         parse_mode="HTML",
                         reply_markup=await kb.get_start_menu(rights="user"))


@user.message(F.text == "🚫Отмена")
async def btn_cancel_click(message: Message, state: FSMContext):
    await state.set_state(EventSignUp.event_name)
    await message.answer("Отменяю действие", reply_markup=await kb.get_start_menu(rights="user"))


@user.message(F.text == "👤Наши контакты")
async def btn_contacts_click(message: Message):
    await message.answer("Наши контакты:", reply_markup=kb.our_contacts)


@user.message(F.text == "💻Тех поддержка")
async def btn_support_click(message: Message):
    await message.answer("Техническая поддержка:", reply_markup=kb.tech_support)


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


# Обработка нажатий кнопок с названием мероприятий


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
            ) + registered_users_str + grouped_by_level_str,
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
                registered_users_str + grouped_by_level_str,
                parse_mode="HTML",
                reply_markup=await kb.get_event_menu(rights="user", event_status="signed", event_name=event_name)
            )
        else:
            await message.answer(
                event_info_for_message.format(event_name=event_name, event_date=event_date, event_desc=event_desc,
                                              is_signup_open_str=is_signup_open_str, event_limit=event_limit) +
                user_data_str.format(signup_user_full_name=signup_user_full_name) +
                f"\n🛎Статус : не пойду"
                f"\n\n{registered_users_str}"
                f"\n{grouped_by_level_str}",
                parse_mode="HTML",
                reply_markup=await kb.get_event_menu(rights="user", event_name=event_name)
            )
    print(perf_counter()-t)


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


# Обработаем нажатие кнопок для отмены записи на мероприятие


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


# Обработаем кнопку выхода из мероприятия


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


# Обработаем кнопку для подтверждения/отмены удаления мероприятия
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


# Обработка заполнения профиля


@user.message(F.text == "📝Редактировать профиль")
async def edit_profile(message: Message, state: FSMContext):
    user_profile = await get_user_profile(chat_id=message.from_user.id)
    message_to_send = ""
    if user_profile:
        profile_text = f"""Игровой ник: {user_profile.nickname}
        Уровень: {kb.get_level_info_by_id(user_profile.level)['level_name']}
        Из ИТМО: {user_profile.is_itmo}
        Polemica id: {user_profile.polemica_id}
        """
        message_to_send = f"Ваш профиль:\n{profile_text}\nПриступаем к пересозданию профиля...\n\n"
    await message.answer(message_to_send + "Введите ваш никнейм:", reply_markup=await kb.get_user_cancel_button())
    await state.set_state(ProfileEdit.nickname)


@user.message(ProfileEdit.nickname)
async def process_nickname(message: Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Вы из ИТМО?", reply_markup=kb.are_u_from_itmo_keyboard)
    await state.set_state(ProfileEdit.is_itmo)


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
    if len(message.text) == 10 and message.text.isdigit():
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
        await message.answer("Для продолжения необходимо дать согласие на обработку персональных данных.")


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

# старый сценарий – заполнение ника на каждое мероприятие

# @user.message(EventSignUp.full_name)
# async def wait_full_name(message: Message, state: FSMContext):
#     if message.text is not None:
#         await state.update_data(full_name=message.text)
#         await message.answer(
#             'Выберите свой уровень. Описание уровней есть в <a href="https://t.me/mafia_itmo/64">посте</a>',
#             reply_markup=await kb.get_level_keyboard(),
#             parse_mode="HTML"
#         )
#         await state.set_state(EventSignUp.level)
#     else:
#         await message.answer("Некорректный ник! Попробуйте ещё раз!")


# @ user.callback_query(EventSignUp.level)
# async def level_selection_callback(callback: CallbackQuery, state: FSMContext):
#     # Получаем выбранный уровень
#     level_id = int(callback.data.split("_")[1])
#     selected_level = next(
#         (lvl for lvl in kb.LEVEL_DESCR if lvl["level_id"] == level_id), None)

#     if selected_level:
#         await state.update_data(level=selected_level)
#         await state.update_data(id=callback.from_user.id)
#         data_from_state: dict = await state.get_data()
#         event_name: str = data_from_state.get("event_name")
#         username = callback.from_user.username if callback.from_user.username else "No username"
#         await state.update_data(username=username)
#         full_name: str = data_from_state.get("full_name")
#         user_level_dict: dict = data_from_state.get("level")
#         await callback.message.answer(f"Подтвердите запись на мероприятие!"
#                                       f"\n🎉Название мероприятия : {event_name}"
#                                       f"\n📒Ваши данные : "
#                                       f"\n👤Игровой ник : {full_name}"
#                                       f"\n👤Уровень : {user_level_dict['level_symbol']}"
#                                       f"\n👤Ваш Telegram ник : @{username}",
#                                       reply_markup=await kb.get_confirm_menu("confirm_signup"))
#         await state.set_state(EventSignUp.confirm)
#     else:
#         await callback.message.answer("Ошибка выбора уровня. Попробуйте снова.")
