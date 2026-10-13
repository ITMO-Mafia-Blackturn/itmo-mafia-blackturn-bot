from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from database.requests import get_unremoved_events

CLUB_RATING_BUTTON_DATA = "club_rating"
PAIR_RATING_BUTTON_DATA = "pair_rating"

STARS_BUTTON_DATA = "stars"

MY_ACHIEVMENTS_BUTTON_DATA = "my_achievements"

ACHIEVEMENT_CATEGORIES = [{
    "category_id": "common",
    "category_symbol": "⚪",
    "category_name": "Общие",
},
    {
        "category_id": "red",
        "category_symbol": "🔴",
        "category_name": "Мирный и шериф",
    },
    {
        "category_id": "black",
        "category_symbol": "⚫",
        "category_name": "Мафия и дон",
    },

]

LEVEL_DESCR = [
    {
            "level_id": 0,
            "level_symbol": "⚪",
            "level_name": "o iia io iii ai",
            "hidden": True
        },
    {
        "level_id": 1,
        "level_symbol": "🟢",
        "level_name": "Новичок",
    },
    {
        "level_id": 2,
        "level_symbol": "🟡",
        "level_name": "База",
    },
    {
        "level_id": 3,
        "level_symbol": "🔵",
        "level_name": "Уверенная база",
    },
    {
        "level_id": 4,
        "level_symbol": "🟠",
        "level_name": "Опытный, уровень 1"
    },
    {
        "level_id": 5,
        "level_symbol": "🟣",
        "level_name": "Условно эксперт (выше 4)",
    }
]


def get_level_info_by_id(level_id: int):
    for level in LEVEL_DESCR:
        if level["level_id"] == level_id:
            return level


async def get_level_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{level['level_symbol']} {level['level_name']}", callback_data=f"level_{level['level_id']}")]
        for level in LEVEL_DESCR if "hidden" not in level.keys() or not level["hidden"]
    ])


# Кнопки со ссылками на контакты
our_contacts = InlineKeyboardMarkup(inline_keyboard=[
    # [InlineKeyboardButton(
    #     text="ВКонтакте", url="https://vk.com/progressor45")],
    [InlineKeyboardButton(
        text="Телеграм канал", url="t.me/mafia_itmo")],
    [InlineKeyboardButton(
        text="Телеграм чат", url="https://t.me/+5imdCNlmHW05Njdi")],
    [InlineKeyboardButton(
        text="Главный организатор", url="https://t.me/high_fly_bird")],
])

# Кнопки со ссылками на техническую поддержку
tech_support = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(
        text="Все баги описывайте в чате", url="https://t.me/+5imdCNlmHW05Njdi")]
])

# Панель администратора
admin_panel = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🎇Создать мероприятие"), KeyboardButton(
        text="🎆Удалить мероприятие")],
    [KeyboardButton(text="🚫Забанить пользователя"), KeyboardButton(
        text="✅Разбанить пользователя")],
    [KeyboardButton(text="➕Добавить админа"), KeyboardButton(
        text="➖Удалить админа")],
    [KeyboardButton(text="🗣️Сделать рассылку")],
    [KeyboardButton(text="🤖Назад")],
], input_field_placeholder="Выберите пункт меню...", resize_keyboard=True)

achivement_rating_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Мои достижения", callback_data=MY_ACHIEVMENTS_BUTTON_DATA)],
        [InlineKeyboardButton(text="Зал славы", callback_data=STARS_BUTTON_DATA)],
        [InlineKeyboardButton(text="Рейтинг клуба", callback_data=CLUB_RATING_BUTTON_DATA)],
        [InlineKeyboardButton(text="Парные", callback_data=PAIR_RATING_BUTTON_DATA)],
    ]
)

# Кнопка для отмены действия админа
admin_cancel_markup = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="❌Отмена")]
], input_field_placeholder="Нажмите кнопку,если передумаете...",
    resize_keyboard=True)


async def get_user_cancel_button(*, addition: str = ""):
    keyboard = ReplyKeyboardBuilder()
    if addition == "phone":
        keyboard.add(KeyboardButton(text="📞Отправить", request_contact=True))
    keyboard.add(KeyboardButton(text="🚫Отмена"))
    return keyboard.adjust(1).as_markup(resize_keyboard=True,
                                        input_field_placeholder="Нажмите на кнопку,если передумаете...")


async def get_start_menu(*, rights: str):
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text="🎉Мероприятия"))
    keyboard.add(KeyboardButton(text="📝Редактировать профиль"))
    # keyboard.add(KeyboardButton(text="🌟Достижения и рейтинг"))
    if rights == "admin":
        keyboard.add(KeyboardButton(text=f"⚙️Админ панель"))
    else:
        keyboard.add(KeyboardButton(text="👤Наши контакты"))
    keyboard.add(KeyboardButton(text="💻Тех поддержка"))
    keyboard.add(KeyboardButton(text="/help"))
    return keyboard.adjust(1).as_markup(resize_keyboard=True, input_field_placeholder="Выберите пункт меню...")


async def get_achievement_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{category['category_symbol']} {category['category_name']}", callback_data=category['category_id'])]
        for category in ACHIEVEMENT_CATEGORIES
    ])


def get_achievement_rating_ment():
    return


async def get_event_menu(*, rights: str, event_status: str = "", event_name: str = ""):
    keyboard = ReplyKeyboardBuilder()
    if rights == "admin":
        keyboard.add(KeyboardButton(text="👥Записавшиеся"))
        keyboard.add(KeyboardButton(text="❌Закрыть запись"))
        keyboard.add(KeyboardButton(text="📬Отправить проходки"))
    else:
        if event_status == "unsigned":
            keyboard.add(KeyboardButton(text=f"📝Записаться"))
        elif event_status == "signed":
            keyboard.add(KeyboardButton(text="❌Я не приду"))
    keyboard.add(KeyboardButton(text="🔄Обновить список"))
    keyboard.add(KeyboardButton(text="🔙Назад"))

    return keyboard.adjust(1).as_markup(resize_keyboard=True, input_field_placeholder="Выберите пункт меню...")


async def get_confirm_menu(callback: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅Подтвердить", callback_data=f"{callback}")],
        [InlineKeyboardButton(
            text="❌Отменить", callback_data='un' + callback)]
    ])
    return keyboard


# Создаём меню с мероприятиями

async def get_events_names_buttons():
    keyboard = ReplyKeyboardBuilder()
    for event in await get_unremoved_events():
        keyboard.add(KeyboardButton(text=f"{event.name}"))
    keyboard.add(KeyboardButton(text="👈Назад"))
    return keyboard.adjust(1).as_markup(resize_keyboard=True, input_field_placeholder="Выберите пункт меню...")


are_u_from_itmo_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Да, я из ИТМО"),
     KeyboardButton(text="Нет, я не из ИТМО")]],
    resize_keyboard=True
)


async def get_personal_data_agreement_keyboard():
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text="✅Даю согласие"))
    return keyboard.adjust(1).as_markup(resize_keyboard=True)
