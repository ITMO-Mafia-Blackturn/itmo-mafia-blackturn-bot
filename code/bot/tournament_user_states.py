from aiogram.fsm.state import State, StatesGroup


class TournamentUserState(StatesGroup):
    polemica_id = State()
    photo = State()


class TournamentAdminState(StatesGroup):
    rejection_reason = State()
