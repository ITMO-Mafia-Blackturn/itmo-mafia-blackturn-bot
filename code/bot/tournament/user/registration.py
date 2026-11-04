import logging
from html import escape
from datetime import datetime
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
import httpx
import bot.keyboards as kb
from bot.tournament_user.states import TournamentUserState
from services.polemica_service import PolemicaProfileError, get_polemica_nickname
from services.tournament_service import (
    TournamentRegistrationCard,
    apply_for_tournament,
    count_active_registrations,
    count_active_guest_registrations,
    get_registration,
    get_approved_registrations,
    get_tournament,
    get_tournaments,
    get_user_profile,
    registration_status,
    save_player_photo,
    save_tournament_player,
    update_user_polemica_id,
    withdraw_from_tournament,
)


tournament_user = Router()



from bot.tournament_user.onboarding import show_active_tournaments


def _confirmed_roster_text(
    players: list[TournamentRegistrationCard],
) -> str:
    lines = [f"Подтверждённый состав ({len(players)}):"]
    roster_length = len(lines[0])
    for index, player in enumerate(players):
        line = (
            f"• {escape(player.polemica_nickname or 'Ник Polemica не указан')} "
            f"({escape(player.bot_nickname)})"
        )
        if roster_length + len(line) + 1 > 2800:
            lines.append(f"… и ещё {len(players) - index} участников.")
            break
        lines.append(line)
        roster_length += len(line) + 1
    if not players:
        lines.append("Пока нет подтверждённых участников.")
    return "\n".join(lines)

@tournament_user.callback_query(F.data == "tournament:list")
async def return_to_tournament_list(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await callback.answer()
    await show_active_tournaments(callback.message, state, edit=True)

async def show_tournament_details(
    callback: CallbackQuery, tournament_id: int
) -> None:
    tournament = await get_tournament(tournament_id)
    profile = await get_user_profile(callback.from_user.id)
    if tournament is None or profile is None:
        await callback.answer("Регистрация на этот турнир закрыта.", show_alert=True)
        return

    registration = await get_registration(tournament.id, profile.id)
    confirmed_players = await get_approved_registrations(tournament.id)
    registered = registration is not None and not registration.rejected
    active_guest_count = await count_active_guest_registrations(tournament.id)
    can_register = (
        not registered
        and not tournament.expired
        and tournament.registry_deadline >= datetime.now()
        and (await count_active_registrations(tournament.id)) < tournament.capacity
    )
    can_guest_register = profile.is_itmo or active_guest_count < tournament.guest_capacity
    details = "\n".join(
        [
            f"<b>{escape(tournament.name)}</b>",
            "",
            f"{escape(tournament.description)}",
            "",
            f"Дата: {tournament.date:%d.%m.%Y %H:%M}",
            f"Место: {escape(tournament.place)}",
            "",
            f"Регистрация до: {tournament.registry_deadline:%d.%m.%Y %H:%M}",
            "",
            f"Гости: {active_guest_count}/{tournament.guest_capacity}",
            "",
            _confirmed_roster_text(confirmed_players),
            "",
            f"Статус вашей заявки: {escape(registration_status(registration))}",
        ]
    )
    if registration and registration.rejected and registration.rejection_reason:
        details += f"\nПричина отказа: {escape(registration.rejection_reason)}"
    if not registered and not can_register:
        details += "\nРегистрация закрыта или все места заняты."
    elif not registered and not can_guest_register:
        details += "\nМеста для гостей закончились."

    await callback.message.edit_text(
        details,
        reply_markup=kb.get_tournament_actions_keyboard(
            tournament.id,
            registered=registered,
            can_register=can_register,
            can_guest_register=can_guest_register,
        ),
        parse_mode="HTML",
    )
    await callback.answer()

@tournament_user.callback_query(F.data.startswith("tournament:select:"))
async def select_tournament(callback: CallbackQuery) -> None:
    await show_tournament_details(
        callback, int(callback.data.rsplit(":", maxsplit=1)[1])
    )

@tournament_user.callback_query(F.data.startswith("tournament:apply:"))
async def apply_for_selected_tournament(callback: CallbackQuery) -> None:
    tournament_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    profile = await get_user_profile(callback.from_user.id)
    if profile is None:
        await callback.answer("Сначала создайте профиль бота.", show_alert=True)
        return

    result = await apply_for_tournament(tournament_id, profile.id)
    messages = {
        "created": "Заявка отправлена и ожидает подтверждения администратора.",
        "already_registered": "Вы уже записаны на этот турнир.",
        "closed": "Регистрация на турнир закрыта.",
        "full": "Свободных мест на турнире больше нет.",
        "guest_full": "Свободных мест для гостей больше нет.",
        "not_found": "Турнир или профиль игрока не найден.",
    }
    if result == "created":
        await show_tournament_details(callback, tournament_id)
    else:
        await callback.answer(messages[result], show_alert=True)

@tournament_user.callback_query(F.data.startswith("tournament:withdraw:"))
async def ask_withdrawal_confirmation(callback: CallbackQuery) -> None:
    tournament_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    await callback.message.edit_text(
        "Вы уверены, что хотите сняться с турнира?",
        reply_markup=kb.get_withdraw_confirmation_keyboard(tournament_id),
    )
    await callback.answer()

@tournament_user.callback_query(F.data.startswith("tournament:withdraw_confirm:"))
async def confirm_withdrawal(callback: CallbackQuery) -> None:
    tournament_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    profile = await get_user_profile(callback.from_user.id)
    withdrawn = (
        await withdraw_from_tournament(tournament_id, profile.id)
        if profile is not None
        else False
    )
    await callback.answer(
        "Вы сняты с турнира." if withdrawn else "Активная заявка не найдена.",
        show_alert=not withdrawn,
    )
    if withdrawn:
        await show_tournament_details(callback, tournament_id)
