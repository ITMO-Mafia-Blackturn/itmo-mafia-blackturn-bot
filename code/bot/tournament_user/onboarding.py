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



from bot.user.states import ProfileEdit


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
