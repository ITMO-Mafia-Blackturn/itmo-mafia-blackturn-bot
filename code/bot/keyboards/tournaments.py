from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from database.requests import get_unremoved_events

def get_polemica_profile_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Использовать ID профиля", callback_data="tournament:use_profile_id")],
            [InlineKeyboardButton(text="Ввести другой ID", callback_data="tournament:enter_id")],
        ]
    )

def get_tournament_selection_keyboard(tournaments) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🏆 {tournament.date:%d.%m.%Y} — {tournament.place[:35]}",
                    callback_data=f"tournament:select:{tournament.id}",
                )
            ]
            for tournament in tournaments
        ]
    )

def get_tournament_actions_keyboard(
    tournament_id: int,
    *,
    registered: bool,
    can_register: bool,
    can_guest_register: bool,
) -> InlineKeyboardMarkup:
    buttons = []
    if registered:
        buttons.append(
            [InlineKeyboardButton(text="Сняться с турнира", callback_data=f"tournament:withdraw:{tournament_id}")]
        )
    elif can_register and can_guest_register:
        buttons.append(
            [InlineKeyboardButton(text="Записаться", callback_data=f"tournament:apply:{tournament_id}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="К списку турниров", callback_data="tournament:list")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_withdraw_confirmation_keyboard(tournament_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, сняться",
                    callback_data=f"tournament:withdraw_confirm:{tournament_id}",
                ),
                InlineKeyboardButton(
                    text="Нет",
                    callback_data=f"tournament:select:{tournament_id}",
                ),
            ]
        ]
    )

def get_admin_tournament_keyboard(tournaments) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'📦' if tournament.expired else '🏆'} "
                    f"{tournament.date:%d.%m.%Y} — {tournament.place[:35]}",
                    callback_data=f"tournament_admin:select:{tournament.id}",
                )
            ]
            for tournament in tournaments
        ]
    )

def get_admin_tournament_archive_keyboard(tournaments) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📦 {tournament.date:%d.%m.%Y} — {tournament.place[:35]}",
                    callback_data=f"tournament_admin:archive_select:{tournament.id}",
                )
            ]
            for tournament in tournaments
        ]
    )

def get_tournament_archive_confirmation_keyboard(
    tournament_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Архивировать",
                    callback_data=f"tournament_admin:archive_confirm:{tournament_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="tournament_admin:archive_cancel",
                ),
            ]
        ]
    )

def get_admin_tournament_actions_keyboard(tournament_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать турнир",
                    callback_data=f"tournament_admin:edit_start:{tournament_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Записи",
                    callback_data=f"tournament_admin:registrations:{tournament_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Список гостей",
                    callback_data=f"tournament_admin:guests:{tournament_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Подтверждение записей",
                    callback_data=f"tournament_admin:review:{tournament_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📬 Отправить проходки",
                    callback_data=f"tournament_admin:passes:{tournament_id}",
                )
            ],
        ]
    )

def get_tournament_edit_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Сохранить",
                    callback_data="tournament_admin:edit_confirm",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="tournament_admin:edit_cancel",
                ),
            ]
        ]
    )

def get_tournament_creation_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="tournament_admin:create_cancel",
                )
            ]
        ]
    )

def get_tournament_creation_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Создать",
                    callback_data="tournament_admin:create_confirm",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="tournament_admin:create_cancel",
                ),
            ]
        ]
    )

def get_registration_review_keyboard(
    registration_id: int,
    *,
    can_decide: bool = True,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="⬅️ Предыдущая",
                callback_data="tournament_admin:previous",
            ),
            InlineKeyboardButton(
                text="➡️ Следующая",
                callback_data="tournament_admin:next",
            ),
        ],
    ]
    if can_decide:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"tournament_admin:approve:{registration_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"tournament_admin:reject:{registration_id}",
                ),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
