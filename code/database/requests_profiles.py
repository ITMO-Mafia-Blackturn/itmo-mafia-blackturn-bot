from datetime import datetime
from logging import exception
from typing import Optional
from sqlalchemy import and_
from sqlalchemy import select, delete, update, func, text
from config import ADMIN_CHATS_INFO
from database.models import Admin, BannedUser, UserInMailing, Event, EventSingUp, UserProfile
from database.models import async_session
from utils import setup_logger

async def update_user_signups_profile(
    chat_id: int, nickname: str, level: int
) -> None:
  async with async_session() as session:
    stmt = (
        update(EventSingUp)
        .where(EventSingUp.chat_id == chat_id)
        .values(full_name=nickname, level=level)
    )
    await session.execute(stmt)
    await session.commit()

async def save_user_profile(chat_id: int,
                            nickname: str,
                            is_itmo: bool,
                            level: int,
                            polemica_id: Optional[int],
                            full_name: Optional[str] = None,
                            passport: Optional[str] = None,
                            phone: Optional[str] = None,
                            username: Optional[str] = None,
                            personal_data_agreement: bool = False):
    async with async_session() as session:
        profile = await session.scalar(select(UserProfile).where(UserProfile.chat_id == chat_id))
        if profile:
            profile.nickname = nickname
            profile.level = level
            profile.is_itmo = is_itmo
            profile.polemica_id = polemica_id
            profile.full_name = full_name
            profile.passport = passport
            profile.phone = phone
            profile.username = username
            profile.personal_data_agreement = personal_data_agreement
        else:
            session.add(UserProfile(chat_id=chat_id,
                                    nickname=nickname,
                                    is_itmo=is_itmo,
                                    level=level,
                                    polemica_id=polemica_id,
                                    full_name=full_name,
                                    passport=passport,
                                    phone=phone,
                                    username=username,
                                    personal_data_agreement=personal_data_agreement
                                    ))
        await session.commit()

async def get_user_profile(chat_id: int) -> Optional[UserProfile]:
    async with async_session() as session:
        return await session.scalar(select(UserProfile).where(UserProfile.chat_id == chat_id))

async def get_users_with_polemica_id() -> list[UserProfile]:
    async with async_session() as session:
        return await session.scalars(select(UserProfile).where(UserProfile.polemica_id != None))
