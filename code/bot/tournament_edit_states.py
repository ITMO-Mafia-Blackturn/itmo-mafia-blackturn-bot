from aiogram.fsm.state import State, StatesGroup


class TournamentEditState(StatesGroup):
    name = State()
    description = State()
    place = State()
    date = State()
    registry_deadline = State()
    capacity = State()
    guest_capacity = State()
    confirmation = State()
