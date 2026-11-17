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

async def create_tournament(
    *,
    name: str,
    description: str,
    place: str,
    date: datetime,
    registry_deadline: datetime,
    capacity: int,
    guest_capacity: int,
) -> int:
    if not name.strip() or len(name) > 700:
        raise ValueError("Название турнира должно содержать от 1 до 700 символов.")
    if not description.strip() or len(description) > 700:
        raise ValueError("Описание турнира должно содержать от 1 до 700 символов.")
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
        name=name,
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

def _validate_tournament_edit(
    *,
    name: str,
    description: str,
    place: str,
    date: datetime,
    registry_deadline: datetime,
    capacity: int,
    guest_capacity: int,
) -> dict[str, object]:
    name = name.strip()
    description = description.strip()
    place = place.strip()
    if not name or len(name) > 700:
        raise ValueError("Название турнира должно содержать от 1 до 700 символов.")
    if not description or len(description) > 700:
        raise ValueError("Описание турнира должно содержать от 1 до 700 символов.")
    if not place or len(place) > 150:
        raise ValueError("Место проведения должно содержать от 1 до 150 символов.")
    if not isinstance(date, datetime) or not isinstance(registry_deadline, datetime):
        raise ValueError("Укажите корректные дату турнира и дедлайн регистрации.")
    if registry_deadline > date:
        raise ValueError("Дедлайн регистрации не может быть позже даты турнира.")
    if type(capacity) is not int or not 0 < capacity <= 2_147_483_647:
        raise ValueError(
            "Вместимость должна быть положительным целым числом не больше 2147483647."
        )
    if (
        type(guest_capacity) is not int
        or not 0 <= guest_capacity <= capacity
    ):
        raise ValueError(
            "Вместимость для гостей должна быть от 0 до общей вместимости турнира."
        )
    return {
        "name": name,
        "description": description,
        "place": place,
        "date": date,
        "registry_deadline": registry_deadline,
        "capacity": capacity,
        "guest_capacity": guest_capacity,
    }

async def edit_tournament(
    tournament_id: int,
    *,
    name: str,
    description: str,
    place: str,
    date: datetime,
    registry_deadline: datetime,
    capacity: int,
    guest_capacity: int,
) -> bool:
    """Validate and atomically update a tournament's editable fields.

    The tournament row lock is shared with ``apply_for_tournament`` so an
    application cannot race a capacity reduction between its count and insert.
    """
    values = _validate_tournament_edit(
        name=name,
        description=description,
        place=place,
        date=date,
        registry_deadline=registry_deadline,
        capacity=capacity,
        guest_capacity=guest_capacity,
    )

    async with async_session() as session:
        async with session.begin():
            repository = TournamentRepository(session)
            tournament = await repository.get_by_id_for_update(tournament_id)
            if tournament is None:
                return False

            active_count = await session.scalar(
                select(func.count(PlayerTournamentRegistration.id)).where(
                    PlayerTournamentRegistration.tournament_id == tournament_id,
                    PlayerTournamentRegistration.rejected.is_(False),
                )
            ) or 0
            active_guest_count = await session.scalar(
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
            ) or 0

            if values["capacity"] < active_count:
                raise ValueError(
                    "Общая вместимость не может быть меньше количества действующих "
                    f"заявок (минимум {active_count})."
                )
            if values["guest_capacity"] < active_guest_count:
                raise ValueError(
                    "Вместимость для гостей не может быть меньше количества "
                    f"действующих заявок от гостей (минимум {active_guest_count})."
                )

            await repository.update(tournament_id, **values)
        return True
