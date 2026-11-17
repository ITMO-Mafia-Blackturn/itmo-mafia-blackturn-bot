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

@admin.message(AdminProtect(), F.text == "👈Назад")
async def btn_back_click(message: Message, state: FSMContext):
    await message.answer("Открываю меню", reply_markup=await kb.get_start_menu(rights="admin"))
    await state.clear()

@admin.message(AdminProtect(), EventCheck())
async def btn_event_name_click(message: Message, state: FSMContext):
    await state.update_data(event_name=message.text)
    await message.answer_sticker("CAACAgIAAxkBAAEDpPBl1WcOfjU0kJaSf9y882BG36ONiwACMw4AApVxCUiC2Rae9Yv1wzQE")
    event_info = await get_event_info_by_name(event_name=message.text)
    is_open = await check_is_signup_open(event_name=message.text)
    is_open_str = "открыта" if is_open is not None else "закрыта"
    await message.answer(f"🎉Название мероприятия : {message.text}"
                         f"\n📆Дата и время проведения: {event_info.date}"
                         f"\n🎊Описание: {event_info.description} "
                         f"\n✏️Запись: {is_open_str}",
                         reply_markup=await kb.get_event_menu(rights="admin"))
    await state.set_state(EventChoice.event_name)

@admin.message(AdminProtect(), EventChoice.event_name, F.text == "❌Закрыть запись")
async def btn_close_signup_event(message: Message, state: FSMContext):
    data_from_state: dict = await state.get_data()
    event_name: str = data_from_state.get("event_name")
    if await check_is_signup_open(event_name=event_name) is not None:
        await message.answer(f"Подтвердите закрытие записи на мероприятие: {event_name}\nУчтите, что"
                             " в дальнейшем будет невозможно открыть запись!",
                             reply_markup=await kb.get_confirm_menu("confirm_close_event"))
    else:
        await message.answer("Мероприятие уже закрыто!")

@admin.callback_query(EventChoice.event_name)
async def confirm_close_event_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    if callback.data == "confirm_close_event":
        data_from_state: dict = await state.get_data()
        event_name: str = data_from_state.get("event_name")
        await close_signup_to_event(event_name=event_name)
        await callback.message.answer("Запись закрыта!", reply_markup=await kb.get_event_menu(rights="admin"))
    else:
        await callback.message.answer("Отменяю закрытие!", reply_markup=await kb.get_event_menu(rights="admin"))

@admin.message(AdminProtect(), EventChoice.event_name, F.text == "👥Записавшиеся")
async def btn_signup_click(message: Message, state: FSMContext):
    data_from_state: dict = await state.get_data()
    event_name: str = data_from_state.get("event_name")
    if await get_count_of_signup(event_name=event_name) == 0:
        await message.answer("На мероприятие никто не записался!")
    else:
        # Приводим данные в объект класса DataFrame
        table = pd.DataFrame(await get_signup_people(event_name=event_name))
        # Создаём excel файл с нашими данными в текущей папке проекта
        table.to_excel(f"{event_name}.xlsx",
                       sheet_name="Записавшиеся", index=False)
        # Отправляем файл с данными
        await message.answer_document(document=FSInputFile(path=os.path.join(os.getcwd(), f"{event_name}.xlsx")))
        # Удаляем файл из текущей директории
        os.remove(os.path.join(os.getcwd(), f"{event_name}.xlsx"))

@admin.message(AdminProtect(), EventChoice.event_name, F.text == "📬Отправить проходки")
async def btn_send_passes_click(message: Message, state: FSMContext):
    data_from_state: dict = await state.get_data()
    event_name: str = data_from_state.get("event_name")
    
    # Проверить, не отправлены ли уже проходки
    if await check_passes_sent(event_name=event_name):
        await message.answer("Проходки для этого мероприятия уже были отправлены.")
        return
    
    guests = await get_guests_for_event(event_name)
    event_info = await get_event_info_by_name(event_name=event_name)
    if not guests:
        await message.answer("На мероприятие не записан ни один гость.")
        return

    successful_sends = 0
    failed_sends = 0

    await message.answer(
        f"Началась отправка сообщений для {len(guests)} гостей. Это займет примерно {len(guests) * 6} секунд")

    async with httpx.AsyncClient() as client:
        for guest in guests:
            payload = {
                "fio": guest.full_name,
                "contacts": f"t.me/{guest.username}",
                "from_itmo": ["114298929"],
                "occupation": ["114298576"],
                "occupation_custom": "Игрок в мафию",
                "phone": guest.phone,
                "passport": guest.passport,
                "citizenship": ["114299256"],
                "corpus": ["114300051"],
                "has_pass": ["114300643"],
                "event": ["114305512"],
                "date": event_info.date.strftime('%Y-%m-%d'),
                "personal_data": True
            }
            try:
                # Вставить URL
                response = await client.post(
                    "https://api.forms.yandex.net/v1/surveys/66f6cb8773cee77dbdffbd87/form?dry_run=false",
                    json=payload
                )
                if response.status_code == 200:
                    successful_sends += 1
                    try:
                        await message.bot.send_message(
                            chat_id=guest.chat_id,
                            text=f"Вам оформлена проходка на мероприятие {event_name}",
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление пользователю {guest.chat_id}: {e}")
                else:
                    failed_sends += 1
                    logger.error(
                        f"Failed to send pass for {guest.full_name}. Status: {response.status_code}, Body: {response.text}")
            except httpx.RequestError as e:
                failed_sends += 1
                logger.error(f"Error sending request for {guest.full_name}: {e}")
            await asyncio.sleep(5)

    if failed_sends == 0:
        await mark_passes_sent(event_name=event_name)
    
    await message.answer(
        f"Отправка проходок завершена.\nУспешно: {successful_sends}\nНеудачно: {failed_sends}\n"
        f"{'⚠️ Запись новых гостей на мероприятие заблокирована.' if failed_sends == 0 else 'Проверьте ошибки и повторите отправку.'}")

logger = setup_logger()
