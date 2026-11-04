from aiogram.filters import Filter
from aiogram.types import Message
from database.requests import check_ban, check_event_by_name

class BannedProtect(Filter):
    async def __call__(self, message: Message):
        return await check_ban(chat_id=message.from_user.id)

class EventCheck(Filter):
    async def __call__(self, message: Message):
        return await check_event_by_name(event_name=message.text)
