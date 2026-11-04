from datetime import datetime
from html import escape
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import bot.keyboards as kb
from bot.tournament_edit_states import TournamentEditState
from database.requests import check_admin


_FIELDS = (
    ("name", TournamentEditState.name, "Введите название турнира (1–700 символов)."),
    (
        "description",
        TournamentEditState.description,
        "Введите описание турнира (1–700 символов).",
    ),
    ("place", TournamentEditState.place, "Введите место проведения (1–150 символов)."),
    (
        "date",
        TournamentEditState.date,
        "Введите дату и время турнира в формате ДД.ММ.ГГГГ ЧЧ:ММ.",
    ),
    (
        "registry_deadline",
        TournamentEditState.registry_deadline,
        "Введите дедлайн регистрации в формате ДД.ММ.ГГГГ ЧЧ:ММ. "
        "Он должен быть не позже даты турнира.",
    ),
    (
        "capacity",
        TournamentEditState.capacity,
        "Введите общую вместимость — положительное целое число.",
    ),
    (
        "guest_capacity",
        TournamentEditState.guest_capacity,
        "Введите вместимость для гостей (не из ИТМО), от 0 до общей вместимости.",
    ),
)


async def _is_admin(user_id: int) -> bool:
    return bool(await check_admin(chat_id=user_id))

async def _authorize_message(message: Message, state: FSMContext) -> bool:
    if message.from_user is None or not await _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        await state.clear()
        return False
    return True

def _edit_review_text(data: dict) -> str:
    return (
        "<b>Проверьте изменения турнира</b>\n"
        f"Название: {escape(data['name'])}\n"
        f"Описание: {escape(data['description'])}\n"
        f"Место: {escape(data['place'])}\n"
        f"Дата: {data['date']:%d.%m.%Y %H:%M}\n"
        f"Дедлайн регистрации: "
        f"{data['registry_deadline']:%d.%m.%Y %H:%M}\n"
        f"Вместимость: {data['capacity']}\n"
        f"Вместимость для гостей: {data['guest_capacity']}"
    )

async def _ask_current_field(message: Message, state: FSMContext, index: int) -> None:
    name, next_state, prompt = _FIELDS[index]
    data = await state.get_data()
    value = data[name]
    if isinstance(value, datetime):
        value = value.strftime("%d.%m.%Y %H:%M")
    await state.set_state(next_state)
    await message.answer(
        f"{prompt}\nТекущее значение: {value}\n"
        "Отправьте /skip, чтобы оставить его без изменений."
    )

async def _advance(message: Message, state: FSMContext, index: int) -> None:
    if index < len(_FIELDS):
        await _ask_current_field(message, state, index)
        return
    await state.set_state(TournamentEditState.confirmation)
    await message.answer(
        _edit_review_text(await state.get_data()),
        reply_markup=kb.get_tournament_edit_confirmation_keyboard(),
        parse_mode="HTML",
    )
