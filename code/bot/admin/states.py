from aiogram.fsm.state import State, StatesGroup

class Mailing(StatesGroup):
    choose_event = State()
    message = State()
    confirm = State()

class BanUser(StatesGroup):
    id = State()

class UnbanUser(StatesGroup):
    id = State()

class AddAdmin(StatesGroup):
    id = State()

class DelAdmin(StatesGroup):
    id = State()

class AddEvent(StatesGroup):
    name = State()
    date = State()
    limit = State()
    description = State()
    confirm = State()

class DelEvent(StatesGroup):
    id = State()
    confirm = State()

class EventChoice(StatesGroup):
    event_name = State()
