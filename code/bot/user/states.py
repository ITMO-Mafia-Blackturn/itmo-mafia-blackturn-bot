from aiogram.fsm.state import State, StatesGroup

class EventSignUp(StatesGroup):
    event_name = State()
    full_name = State()
    id = State()
    level = State()
    username = State()
    confirm = State()

class ProfileEdit(StatesGroup):
    nickname = State()
    level = State()
    polemica_id = State()
    is_itmo = State()
    full_name = State()
    passport = State()
    phone = State()
    personal_data_agreement = State()

class Achievements(StatesGroup):
    submenu = State()
    category = State()

class PairRating(StatesGroup):
    choose = State()

class UpdateProfile(StatesGroup):
    fields = State()
    option = State()
    waiting_for_value = State()
