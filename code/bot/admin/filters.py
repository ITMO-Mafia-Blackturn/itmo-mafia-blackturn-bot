from aiogram.filters import Filter
from aiogram.types import Message
from database.requests import check_admin, check_event_by_name

class AdminProtect(Filter):
    async def __call__(self, message: Message):
        return await check_admin(chat_id=message.from_user.id)

class EventCheck(Filter):
    async def __call__(self, message: Message):
        return await check_event_by_name(event_name=message.text)
