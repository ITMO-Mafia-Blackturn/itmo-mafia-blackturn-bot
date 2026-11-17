from datetime import datetime

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from bot.tournament_edit_states import TournamentEditState
from bot.tournament_edit_common import _FIELDS, _authorize_message, _advance

router = Router()

@router.message(TournamentEditState.name)
async def receive_edit_name(message: Message, state: FSMContext) -> None:
    if not await _authorize_message(message, state):
        return
    value = (message.text or "").strip()
    if value != "/skip" and (not value or len(value) > 700):
        await message.answer("Введите название длиной от 1 до 700 символов.")
        return
    if value != "/skip":
        await state.update_data(name=value)
    await _advance(message, state, 1)

@router.message(TournamentEditState.description)
async def receive_edit_description(message: Message, state: FSMContext) -> None:
    if not await _authorize_message(message, state):
        return
    value = (message.text or "").strip()
    if value != "/skip" and (not value or len(value) > 700):
        await message.answer("Введите описание длиной от 1 до 700 символов.")
        return
    if value != "/skip":
        await state.update_data(description=value)
    await _advance(message, state, 2)

@router.message(TournamentEditState.place)
async def receive_edit_place(message: Message, state: FSMContext) -> None:
    if not await _authorize_message(message, state):
        return
    value = (message.text or "").strip()
    if value != "/skip" and (not value or len(value) > 150):
        await message.answer("Введите место длиной от 1 до 150 символов.")
        return
    if value != "/skip":
        await state.update_data(place=value)
    await _advance(message, state, 3)

@router.message(TournamentEditState.date)
async def receive_edit_date(message: Message, state: FSMContext) -> None:
    if not await _authorize_message(message, state):
        return
    value = (message.text or "").strip()
    if value != "/skip":
        try:
            tournament_date = datetime.strptime(value, "%d.%m.%Y %H:%M")
        except ValueError:
            await message.answer(
                "Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ."
            )
            return
        await state.update_data(date=tournament_date)
    data = await state.get_data()
    if data["registry_deadline"] > data["date"]:
        await message.answer(
            "Текущий дедлайн позже новой даты турнира. Введите более ранний "
            "дедлайн на следующем шаге."
        )
    await _advance(message, state, 4)

@router.message(TournamentEditState.registry_deadline)
async def receive_edit_deadline(message: Message, state: FSMContext) -> None:
    if not await _authorize_message(message, state):
        return
    value = (message.text or "").strip()
    if value != "/skip":
        try:
            deadline = datetime.strptime(value, "%d.%m.%Y %H:%M")
        except ValueError:
            await message.answer(
                "Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ."
            )
            return
        await state.update_data(registry_deadline=deadline)
    data = await state.get_data()
    if data["registry_deadline"] > data["date"]:
        await message.answer("Дедлайн регистрации должен быть не позже даты турнира.")
        return
    await _advance(message, state, 5)

@router.message(TournamentEditState.capacity)
async def receive_edit_capacity(message: Message, state: FSMContext) -> None:
    if not await _authorize_message(message, state):
        return
    value = (message.text or "").strip()
    if value != "/skip":
        if (
            not value.isascii()
            or not value.isdecimal()
            or len(value) > 10
            or not 0 < int(value) <= 2_147_483_647
        ):
            await message.answer(
                "Вместимость должна быть положительным целым числом "
                "не больше 2147483647."
            )
            return
        await state.update_data(capacity=int(value))
    data = await state.get_data()
    if data["guest_capacity"] > data["capacity"]:
        await message.answer(
            "Текущая вместимость для гостей выше общей вместимости. "
            "Введите допустимое значение для гостей на следующем шаге."
        )
    await _advance(message, state, 6)

@router.message(TournamentEditState.guest_capacity)
async def receive_edit_guest_capacity(message: Message, state: FSMContext) -> None:
    if not await _authorize_message(message, state):
        return
    value = (message.text or "").strip()
    data = await state.get_data()
    if value != "/skip":
        if (
            not value.isascii()
            or not value.isdecimal()
            or len(value) > 10
            or int(value) > data["capacity"]
        ):
            await message.answer(
                "Вместимость для гостей должна быть целым числом от 0 "
                "до общей вместимости турнира."
            )
            return
        await state.update_data(guest_capacity=int(value))
    else:
        if data["guest_capacity"] > data["capacity"]:
            await message.answer(
                "Введите вместимость для гостей не выше общей вместимости турнира."
            )
            return
    await _advance(message, state, len(_FIELDS))
