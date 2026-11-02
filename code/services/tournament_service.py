from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    PlayerTournamentRegistration,
    Tournament,
    TournamentPlayer,
    UserProfile,
    async_session,
)


@dataclass(frozen=True)
class TournamentRegistrationCard:
    registration_id: int
    tournament_id: int
    tournament_description: str
    tournament_date: datetime
    tournament_place: str
    approved: bool
    rejected: bool
    rejection_reason: str | None
    player_id: int
    polemica_id: int | None
    polemica_nickname: str | None
    photo: bytes | None
    chat_id: int
    telegram_username: str | None
    bot_nickname: str
    bot_level: int
    is_itmo: bool
    full_name: str | None
    passport: str | None
    phone: str | None
    personal_data_agreement: bool


def registration_status(
    registration: PlayerTournamentRegistration | TournamentRegistrationCard | None,
) -> str:
    if registration is None:
        return "Не записан"
    if registration.rejected:
        return "Отклонена"
    if registration.approved:
        return "Подтверждена"
    return "Ожидает подтверждения"


async def get_tournaments(*, active_only: bool = False) -> list[Tournament]:
    async with async_session() as session:
        query = select(Tournament)
        if active_only:
            query = query.where(
                Tournament.expired.is_(False),
                Tournament.registry_deadline >= datetime.now(),
            )
        result = await session.scalars(query.order_by(Tournament.date))
        return list(result.all())


async def get_tournament(tournament_id: int) -> Tournament | None:
    async with async_session() as session:
        return await session.get(Tournament, tournament_id)


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


async def apply_for_tournament(
    tournament_id: int, user_profile_id: int
) -> str:
    async with async_session() as session:
        tournament = await session.get(Tournament, tournament_id)
        player = await session.scalar(
            select(TournamentPlayer).where(
                TournamentPlayer.user_profile_id == user_profile_id
            )
        )
        if tournament is None or player is None:
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


async def get_all_registrations(
    tournament_id: int,
) -> list[TournamentRegistrationCard]:
    async with async_session() as session:
        registration_ids = await session.scalars(
            select(PlayerTournamentRegistration.id)
            .where(PlayerTournamentRegistration.tournament_id == tournament_id)
            .order_by(PlayerTournamentRegistration.id)
        )
        cards = []
        for registration_id in registration_ids:
            card = await _get_registration_card(session, registration_id)
            if card is not None:
                cards.append(card)
        return cards


async def get_pending_registration_ids(tournament_id: int) -> list[int]:
    async with async_session() as session:
        result = await session.scalars(
            select(PlayerTournamentRegistration.id)
            .where(
                PlayerTournamentRegistration.tournament_id == tournament_id,
                PlayerTournamentRegistration.approved.is_(False),
                PlayerTournamentRegistration.rejected.is_(False),
            )
            .order_by(PlayerTournamentRegistration.id)
        )
        return list(result.all())


async def get_registration_card(
    registration_id: int,
) -> TournamentRegistrationCard | None:
    async with async_session() as session:
        return await _get_registration_card(session, registration_id)


async def _get_registration_card(
    session: AsyncSession, registration_id: int
) -> TournamentRegistrationCard | None:
    registration = await session.get(PlayerTournamentRegistration, registration_id)
    if registration is None:
        return None

    player = await session.get(TournamentPlayer, registration.tournament_player_id)
    tournament = await session.get(Tournament, registration.tournament_id)
    if player is None or tournament is None:
        return None
    profile = await session.get(UserProfile, player.user_profile_id)
    if profile is None:
        return None

    return TournamentRegistrationCard(
        registration_id=registration.id,
        tournament_id=tournament.id,
        tournament_description=tournament.description,
        tournament_date=tournament.date,
        tournament_place=tournament.place,
        approved=registration.approved,
        rejected=registration.rejected,
        rejection_reason=registration.rejection_reason,
        player_id=player.id,
        polemica_id=player.polemica_id,
        polemica_nickname=player.polemica_nickname,
        photo=player.photo,
        chat_id=profile.chat_id,
        telegram_username=profile.username,
        bot_nickname=profile.nickname,
        bot_level=profile.level,
        is_itmo=profile.is_itmo,
        full_name=profile.full_name,
        passport=profile.passport,
        phone=profile.phone,
        personal_data_agreement=profile.personal_data_agreement,
    )


async def approve_registration(registration_id: int) -> int | None:
    async with async_session() as session:
        registration = await session.get(
            PlayerTournamentRegistration, registration_id
        )
        if registration is None or registration.approved or registration.rejected:
            return None
        player = await session.get(TournamentPlayer, registration.tournament_player_id)
        profile = await session.get(UserProfile, player.user_profile_id) if player else None
        if profile is None:
            return None
        chat_id = profile.chat_id
        registration.approved = True
        await session.commit()
        return chat_id


async def reject_registration(registration_id: int, reason: str) -> int | None:
    async with async_session() as session:
        registration = await session.get(
            PlayerTournamentRegistration, registration_id
        )
        if registration is None or registration.approved or registration.rejected:
            return None
        player = await session.get(TournamentPlayer, registration.tournament_player_id)
        profile = await session.get(UserProfile, player.user_profile_id) if player else None
        if profile is None:
            return None
        chat_id = profile.chat_id
        registration.rejected = True
        registration.rejection_reason = reason
        await session.commit()
        return chat_id
