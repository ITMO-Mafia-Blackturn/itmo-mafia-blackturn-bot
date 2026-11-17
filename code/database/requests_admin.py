from datetime import datetime
from logging import exception
from typing import Optional
from sqlalchemy import and_
from sqlalchemy import select, delete, update, func, text
from config import ADMIN_CHATS_INFO
from database.models import Admin, BannedUser, UserInMailing, Event, EventSingUp, UserProfile
from database.models import async_session
from utils import setup_logger

async def add_in_ban(*, chat_id: int):
    async with async_session() as session:
        session.add(BannedUser(chat_id=chat_id))
        await session.commit()

async def del_from_ban(*, chat_id: int):
    async with async_session() as session:
        await session.execute(delete(BannedUser).where(BannedUser.chat_id == chat_id))
        await session.commit()

async def add_in_admin(*, chat_id: int):
    async with async_session() as session:
        session.add(Admin(chat_id=chat_id))
        await session.commit()

async def del_from_admin(*, chat_id: int):
    async with async_session() as session:
        await session.execute(delete(Admin).where(Admin.chat_id == chat_id))
        await session.commit()

async def check_ban(*, chat_id: int):
    async with async_session() as session:
        return await session.scalar(select(BannedUser).where(BannedUser.chat_id == chat_id))

async def check_admin(*, chat_id: int):
    async with async_session() as session:
        if str(chat_id) in ADMIN_CHATS_INFO:
            return True
        else:
            return await session.scalar(select(Admin).where(Admin.chat_id == chat_id))

async def get_admins():
    async with async_session() as session:
        return await session.scalars(select(UserProfile).where(UserProfile.chat_id.in_(select(Admin.chat_id))))
