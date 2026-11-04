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

async def get_registration(
    tournament_id: int, user_profile_id: int
) -> PlayerTournamentRegistration | None:
    async with async_session() as session:
        player = await session.scalar(
            select(TournamentPlayer).where(
                TournamentPlayer.user_profile_id == user_profile_id
            )
        )
        if player is None:
            return None
        return await session.scalar(
            select(PlayerTournamentRegistration).where(
                PlayerTournamentRegistration.tournament_id == tournament_id,
                PlayerTournamentRegistration.tournament_player_id == player.id,
            )
        )

async def count_active_registrations(tournament_id: int) -> int:
    async with async_session() as session:
        result = await session.scalar(
            select(func.count(PlayerTournamentRegistration.id)).where(
                PlayerTournamentRegistration.tournament_id == tournament_id,
                PlayerTournamentRegistration.rejected.is_(False),
            )
        )
        return result or 0

async def count_active_guest_registrations(tournament_id: int) -> int:
    async with async_session() as session:
        result = await session.scalar(
            select(func.count(PlayerTournamentRegistration.id))
            .join(
                TournamentPlayer,
                TournamentPlayer.id
                == PlayerTournamentRegistration.tournament_player_id,
            )
            .join(UserProfile, UserProfile.id == TournamentPlayer.user_profile_id)
            .where(
                PlayerTournamentRegistration.tournament_id == tournament_id,
                PlayerTournamentRegistration.rejected.is_(False),
                UserProfile.is_itmo.is_(False),
            )
        )
        return result or 0

async def apply_for_tournament(
    tournament_id: int, user_profile_id: int
) -> str:
    async with async_session() as session:
        tournament = await session.scalar(
            select(Tournament)
            .where(Tournament.id == tournament_id)
            .with_for_update()
        )
        player = await session.scalar(
            select(TournamentPlayer).where(
                TournamentPlayer.user_profile_id == user_profile_id
            )
        )
        profile = await session.get(UserProfile, user_profile_id)
        if tournament is None or player is None or profile is None:
            return "not_found"
        if tournament.expired or tournament.registry_deadline < datetime.now():
            return "closed"

        registration = await session.scalar(
            select(PlayerTournamentRegistration).where(
                PlayerTournamentRegistration.tournament_id == tournament_id,
                PlayerTournamentRegistration.tournament_player_id == player.id,
            )
        )
        if registration is not None and not registration.rejected:
            return "already_registered"

        count_result = await session.scalar(
            select(func.count(PlayerTournamentRegistration.id)).where(
                PlayerTournamentRegistration.tournament_id == tournament_id,
                PlayerTournamentRegistration.rejected.is_(False),
            )
        )
        if (count_result or 0) >= tournament.capacity:
            return "full"

        if not profile.is_itmo:
            guest_count_result = await session.scalar(
                select(func.count(PlayerTournamentRegistration.id))
                .join(
                    TournamentPlayer,
                    TournamentPlayer.id
                    == PlayerTournamentRegistration.tournament_player_id,
                )
                .join(
                    UserProfile,
                    UserProfile.id == TournamentPlayer.user_profile_id,
                )
                .where(
                    PlayerTournamentRegistration.tournament_id == tournament_id,
                    PlayerTournamentRegistration.rejected.is_(False),
                    UserProfile.is_itmo.is_(False),
                )
            )
            if (guest_count_result or 0) >= tournament.guest_capacity:
                return "guest_full"

        if registration is None:
            session.add(
                PlayerTournamentRegistration(
                    tournament_id=tournament_id,
                    tournament_player_id=player.id,
                    approved=False,
                    rejected=False,
                )
            )
        else:
            registration.approved = False
            registration.rejected = False
            registration.rejection_reason = None
        await session.commit()
        return "created"

async def withdraw_from_tournament(tournament_id: int, user_profile_id: int) -> bool:
    async with async_session() as session:
        player = await session.scalar(
            select(TournamentPlayer).where(
                TournamentPlayer.user_profile_id == user_profile_id
            )
        )
        if player is None:
            return False
        registration = await session.scalar(
            select(PlayerTournamentRegistration).where(
                PlayerTournamentRegistration.tournament_id == tournament_id,
                PlayerTournamentRegistration.tournament_player_id == player.id,
            )
        )
        if registration is None:
            return False
        await session.delete(registration)
        await session.commit()
        return True
