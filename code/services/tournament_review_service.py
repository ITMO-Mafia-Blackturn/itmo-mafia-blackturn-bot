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

@dataclass(frozen=True)
class TournamentRegistrationCard:
    registration_id: int
    tournament_id: int
    tournament_date: datetime
    tournament_place: str
    approved: bool
    rejected: bool
    rejection_reason: str | None
    player_id: int
    polemica_id: int | None
    polemica_nickname: str | None
    photo: bytes | None
    user_profile_id: int
    chat_id: int
    profile_polemica_id: int | None
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

async def get_approved_registrations(
    tournament_id: int,
) -> list[TournamentRegistrationCard]:
    async with async_session() as session:
        registration_ids = await session.scalars(
            select(PlayerTournamentRegistration.id)
            .where(
                PlayerTournamentRegistration.tournament_id == tournament_id,
                PlayerTournamentRegistration.approved.is_(True),
                PlayerTournamentRegistration.rejected.is_(False),
            )
            .order_by(PlayerTournamentRegistration.id)
        )
        cards = []
        for registration_id in registration_ids:
            card = await _get_registration_card(session, registration_id)
            if card is not None:
                cards.append(card)
        return cards

async def tournament_passes_sent(tournament_id: int) -> bool:
    async with async_session() as session:
        tournament = await session.get(Tournament, tournament_id)
        return tournament.passes_sent if tournament is not None else False

async def mark_tournament_passes_sent(tournament_id: int) -> bool:
    async with async_session() as session:
        tournament = await session.get(Tournament, tournament_id)
        if tournament is None:
            return False
        tournament.passes_sent = True
        await session.commit()
        return True

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
        tournament_date=tournament.date,
        tournament_place=tournament.place,
        approved=registration.approved,
        rejected=registration.rejected,
        rejection_reason=registration.rejection_reason,
        player_id=player.id,
        polemica_id=player.polemica_id,
        polemica_nickname=player.polemica_nickname,
        photo=player.photo,
        user_profile_id=profile.id,
        chat_id=profile.chat_id,
        profile_polemica_id=profile.polemica_id,
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
