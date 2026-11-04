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


async def create_tournament(
    *,
    description: str,
    place: str,
    date: datetime,
    registry_deadline: datetime,
    capacity: int,
    guest_capacity: int,
) -> int:
    if not description.strip() or len(description) > 700:
        raise ValueError("Название турнира должно содержать от 1 до 700 символов.")
    if not place.strip() or len(place) > 150:
        raise ValueError("Место проведения должно содержать от 1 до 150 символов.")
    if registry_deadline > date:
        raise ValueError("Дедлайн регистрации не может быть позже даты турнира.")
    if not 0 < capacity <= 2_147_483_647:
        raise ValueError(
            "Вместимость должна быть положительным целым числом не больше 2147483647."
        )
    if not 0 <= guest_capacity <= capacity:
        raise ValueError(
            "Вместимость для гостей должна быть от 0 до общей вместимости турнира."
        )

    tournament = Tournament(
        description=description,
        place=place,
        date=date,
        registry_deadline=registry_deadline,
        capacity=capacity,
        guest_capacity=guest_capacity,
        expired=registry_deadline < datetime.now(),
    )
    async with async_session() as session:
        async with session.begin():
            await TournamentRepository(session).create(tournament)
            return tournament.id


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


async def archive_tournament(tournament_id: int) -> bool:
    async with async_session() as session:
        async with session.begin():
            repository = TournamentRepository(session)
            tournament = await repository.get_by_id(tournament_id)
            if tournament is None or tournament.expired:
                return False
            await repository.mark_as_expired(tournament_id)
            return True


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
