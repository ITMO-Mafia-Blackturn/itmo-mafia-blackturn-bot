from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from database.tournament_repository import TournamentRepository
from database.models import (
    PlayerTournamentRegistration,
    Tournament,
    TournamentPlayer,
    UserProfile,
    async_session,
)

async def save_tournament_player(
    *,
    user_profile_id: int,
    polemica_id: int,
    polemica_nickname: str,
    photo: bytes | None = None,
) -> bool:
    async with async_session() as session:
        player = await session.scalar(
            select(TournamentPlayer).where(
                TournamentPlayer.user_profile_id == user_profile_id
            )
        )
        if player is None:
            player = TournamentPlayer(
                user_profile_id=user_profile_id,
                polemica_id=polemica_id,
                polemica_nickname=polemica_nickname,
                photo=photo,
            )
            session.add(player)
        else:
            player.polemica_id = polemica_id
            player.polemica_nickname = polemica_nickname
            if photo is not None:
                player.photo = photo

        has_photo = player.photo is not None
        await session.commit()
        return has_photo

async def save_player_photo(user_profile_id: int, photo: bytes) -> bool:
    async with async_session() as session:
        player = await session.scalar(
            select(TournamentPlayer).where(
                TournamentPlayer.user_profile_id == user_profile_id
            )
        )
        if player is None:
            return False
        player.photo = photo
        await session.commit()
        return True

async def get_user_profile(chat_id: int) -> UserProfile | None:
    async with async_session() as session:
        return await session.scalar(
            select(UserProfile).where(UserProfile.chat_id == chat_id)
        )

async def update_user_polemica_id(chat_id: int, polemica_id: int) -> bool:
    async with async_session() as session:
        profile = await session.scalar(
            select(UserProfile).where(UserProfile.chat_id == chat_id)
        )
        if profile is None:
            return False
        profile.polemica_id = polemica_id
        await session.commit()
        return True
