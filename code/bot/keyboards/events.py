from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from database.requests import get_unremoved_events

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

async def get_events_names_buttons():
    keyboard = ReplyKeyboardBuilder()
    for event in await get_unremoved_events():
        keyboard.add(KeyboardButton(text=f"{event.name}"))
    keyboard.add(KeyboardButton(text="👈Назад"))
    return keyboard.adjust(1).as_markup(resize_keyboard=True, input_field_placeholder="Выберите пункт меню...")
