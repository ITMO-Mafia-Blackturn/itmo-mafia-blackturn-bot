from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from bot.tournament_edit_states import TournamentEditState
from bot.tournament_edit_common import _is_admin, _edit_review_text, _advance
from services.tournament_service import edit_tournament, get_tournament
from bot.tournament_edit_fields import router as fields_router

router = Router()

@router.callback_query(F.data.startswith("tournament_admin:edit_start:"))
async def start_tournament_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    try:
        tournament_id = int(callback.data.rsplit(":", 1)[1])
    except (AttributeError, ValueError):
        await callback.answer("Некорректный турнир.", show_alert=True)
        return

    tournament = await get_tournament(tournament_id)
    if tournament is None:
        await callback.answer("Турнир не найден.", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        tournament_edit_id=tournament_id,
        name=tournament.name,
        description=tournament.description,
        place=tournament.place,
        date=tournament.date,
        registry_deadline=tournament.registry_deadline,
        capacity=tournament.capacity,
        guest_capacity=tournament.guest_capacity,
    )
    await callback.message.answer(
        f"Редактирование турнира «{escape(tournament.name)}»."
    )
    await _advance(callback.message, state, 0)
    await callback.answer()

@router.callback_query(F.data == "tournament_admin:edit_cancel")
async def cancel_tournament_edit(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("Редактирование турнира отменено.")
    await callback.answer()

@router.callback_query(F.data == "tournament_admin:edit_confirm")
async def confirm_tournament_edit(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    if await state.get_state() != TournamentEditState.confirmation.state:
        await callback.answer("Редактирование уже завершено.", show_alert=True)
        return

    data = await state.get_data()
    tournament_id = data.get("tournament_edit_id")
    if not isinstance(tournament_id, int):
        await state.clear()
        await callback.answer("Не удалось определить турнир.", show_alert=True)
        return

    try:
        updated = await edit_tournament(
            tournament_id,
            name=data["name"],
            description=data["description"],
            place=data["place"],
            date=data["date"],
            registry_deadline=data["registry_deadline"],
            capacity=data["capacity"],
            guest_capacity=data["guest_capacity"],
        )
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await state.clear()
    if not updated:
        await callback.message.edit_text("Турнир не найден.")
        await callback.answer("Турнир не найден.", show_alert=True)
        return
    await callback.message.edit_text(
        f"Изменения сохранены.\n\n{_edit_review_text(data)}",
        parse_mode="HTML",
    )
    await callback.answer("Турнир обновлён.")

router.include_router(fields_router)
