from datetime import datetime
from logging import exception
from typing import Optional
from sqlalchemy import and_
from sqlalchemy import select, delete, update, func, text
from config import ADMIN_CHATS_INFO
from database.models import Admin, BannedUser, UserInMailing, Event, EventSingUp, UserProfile
from database.models import async_session
from utils import setup_logger

async def add_in_mailing(*, chat_id: int):
    async with async_session() as session:
        # Проверяем находиться-ли пользователь в рассылке
        user = await session.scalar(select(UserInMailing).where(UserInMailing.chat_id == chat_id))
        # Если пользователя нет в таблице, то добавляем его
        if not user:
            session.add(UserInMailing(chat_id=chat_id))
            await session.commit()

async def del_from_mailing(*, chat_id: int):
    async with async_session() as session:
        await session.execute(delete(UserInMailing).where(UserInMailing.chat_id == chat_id))
        await session.commit()

async def get_users_from_mailing():
    async with async_session() as session:
        return await session.scalars(select(UserInMailing))

async def get_chat_ids_for_users_in_mailing(event_id: int) -> list[int]:
    async with async_session() as session:
        # Define the query
        query = (select(UserInMailing.chat_id)
                 .join(EventSingUp, UserInMailing.chat_id == EventSingUp.chat_id)
                 .where(EventSingUp.event_id == int(event_id))
                 .where(EventSingUp.event_status == 1))

        # Execute and fetch the results
        try:
            result = await session.execute(query)
        except exception as e:
            print(e)

        chat_ids = result.scalars().all()

        return chat_ids
