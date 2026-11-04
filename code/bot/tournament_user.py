import logging
from html import escape
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
import httpx

import bot.keyboards as kb
from bot.tournament_user_states import TournamentUserState
from bot.user import ProfileEdit
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

logger = logging.getLogger(__name__)
tournament_user = Router()


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


async def continue_tournament_setup(
    message: Message,
    state: FSMContext,
    polemica_id: int | None,
    *,
    user_id: int,
) -> None:
    if polemica_id is None:
        await state.set_state(TournamentUserState.polemica_id)
        await message.answer(
            "Профиль бота создан. Введите числовой ID профиля на Polemica:"
        )
        return

    try:
        polemica_nickname = await get_polemica_nickname(polemica_id)
    except (PolemicaProfileError, httpx.HTTPError, OSError) as exc:
        logger.warning(
            "Polemica profile lookup failed for id %s (%s): %s",
            polemica_id,
            type(exc).__name__,
            exc,
        )
        await state.set_state(TournamentUserState.polemica_id)
        await message.answer(
            "Не удалось получить ник с Polemica. Проверьте ID и отправьте его ещё раз:"
        )
        return

    profile = await get_user_profile(user_id)
    if profile is None:
        await state.clear()
        await message.answer(
            "Профиль бота не найден. Создайте его через «📝Редактировать профиль»."
        )
        return

    has_photo = await save_tournament_player(
        user_profile_id=profile.id,
        polemica_id=polemica_id,
        polemica_nickname=polemica_nickname,
    )
    await state.update_data(tournament_profile_id=profile.id)
    if not has_photo:
        await state.set_state(TournamentUserState.photo)
        await message.answer(
            "Чтобы отправить заявку, пришлите фотографию профиля в сообщении."
        )
    else:
        await show_active_tournaments(message, state)


async def show_active_tournaments(
    message: Message, state: FSMContext, *, edit: bool = False
) -> None:
    tournaments = await get_tournaments(active_only=True)
    await state.set_state(None)
    if not tournaments:
        text = "Сейчас нет турниров с открытой регистрацией."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text, reply_markup=await kb.get_start_menu(rights="user"))
        return

    text = "Выберите турнир, чтобы посмотреть информацию и записаться:"
    markup = kb.get_tournament_selection_keyboard(tournaments)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@tournament_user.message(F.text.in_({"Турниры", "🏆Турниры"}))
async def open_tournaments(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    await state.clear()
    profile = await get_user_profile(message.from_user.id)
    if profile is None:
        await state.update_data(tournament_registration_flow=True)
        await state.set_state(ProfileEdit.nickname)
        await message.answer(
            "Для записи на турнир сначала создайте профиль бота.\n"
            "Введите игровой ник (2–3 символа):",
            reply_markup=await kb.get_user_cancel_button(),
        )
        return

    if profile.polemica_id is None:
        await state.update_data(tournament_profile_id=profile.id)
        await state.set_state(TournamentUserState.polemica_id)
        await message.answer(
            "В профиле бота не указан Polemica ID. Введите ID вашего профиля на сайте:"
        )
        return

    await message.answer(
        "Использовать Polemica ID из профиля бота?",
        reply_markup=kb.get_polemica_profile_choice_keyboard(),
    )


@tournament_user.callback_query(F.data == "tournament:use_profile_id")
async def use_profile_polemica_id(
    callback: CallbackQuery, state: FSMContext
) -> None:
    profile = await get_user_profile(callback.from_user.id)
    if profile is None or profile.polemica_id is None:
        await callback.answer("В профиле не найден Polemica ID.", show_alert=True)
        return
    await callback.answer()
    await continue_tournament_setup(
        callback.message,
        state,
        profile.polemica_id,
        user_id=callback.from_user.id,
    )


@tournament_user.callback_query(F.data == "tournament:enter_id")
async def request_polemica_id(callback: CallbackQuery, state: FSMContext) -> None:
    profile = await get_user_profile(callback.from_user.id)
    if profile is None:
        await callback.answer("Сначала создайте профиль бота.", show_alert=True)
        return
    await state.update_data(tournament_profile_id=profile.id)
    await state.set_state(TournamentUserState.polemica_id)
    await callback.message.answer("Введите числовой ID профиля на Polemica:")
    await callback.answer()


@tournament_user.message(TournamentUserState.polemica_id)
async def receive_polemica_id(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isdecimal():
        await message.answer("ID должен состоять только из цифр. Попробуйте ещё раз:")
        return

    polemica_id = int(message.text)
    if not await update_user_polemica_id(message.from_user.id, polemica_id):
        await state.clear()
        await message.answer(
            "Профиль бота не найден. Создайте его через «📝Редактировать профиль»."
        )
        return
    await continue_tournament_setup(
        message, state, polemica_id, user_id=message.from_user.id
    )


@tournament_user.message(TournamentUserState.photo, F.photo)
async def receive_tournament_photo(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    downloaded = await message.bot.download(photo.file_id)
    if downloaded is None:
        await message.answer("Не удалось загрузить фото. Отправьте его ещё раз.")
        return

    data = await state.get_data()
    profile_id = data.get("tournament_profile_id")
    if not isinstance(profile_id, int):
        await state.clear()
        await message.answer("Не найден профиль игрока. Начните запись на турнир заново.")
        return

    if not await save_player_photo(profile_id, downloaded.getvalue()):
        await state.clear()
        await message.answer("Не удалось сохранить фото. Попробуйте начать заново.")
        return
    await show_active_tournaments(message, state)


@tournament_user.message(TournamentUserState.photo)
async def invalid_tournament_photo(message: Message) -> None:
    await message.answer("Отправьте фотографию профиля сообщением.")


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
    details = (
        f"<b>{escape(tournament.name)}</b>\n",
        f"\n",
        f"{escape(tournament.description)}\n"
        f"\n",
        f"\n",
        f"Дата: {tournament.date:%d.%m.%Y %H:%M}\n"
        f"Место: {escape(tournament.place)}\n"
        f"\n",
        f"Регистрация до: {tournament.registry_deadline:%d.%m.%Y %H:%M}\n"
        f"\n",
        f"Гости: {active_guest_count}/{tournament.guest_capacity}\n"
        f"\n",
        f"{_confirmed_roster_text(confirmed_players)}\n"
        f"\n",
        f"\n",
        f"Статус вашей заявки: {escape(registration_status(registration))}"
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
