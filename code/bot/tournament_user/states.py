from aiogram.fsm.state import State, StatesGroup


class TournamentUserState(StatesGroup):
    polemica_id = State()
    photo = State()


class TournamentAdminState(StatesGroup):
    rejection_reason = State()
    create_name = State()
    create_description = State()
    create_place = State()
    create_date = State()
    create_registry_deadline = State()
    create_capacity = State()
    create_guest_capacity = State()
    create_confirmation = State()
