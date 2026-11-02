from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Tournament


class TournamentRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    ALLOWED_FIELDS = {
        "description",
        "place",
        "date",
        "registry_deadline",
        "capacity",
    }

    async def get_by_id(self, id: int) -> Tournament | None:
        return await self.session.get(Tournament, id)

    async def get_all(self) -> list[Tournament]:
        result = await self.session.execute(
            select(Tournament)
        )
        return list(result.scalars().all())


    async def create(self, tournament: Tournament) -> Tournament:
        self.session.add(tournament)
        await self.session.flush()
        return tournament

    async def update(
        self,
        id: int,
        **kwargs
    ) -> Tournament | None:
        if not kwargs.keys() <= self.ALLOWED_FIELDS:
            raise ValueError("Недопустимые атрибуты")

        tournament = await self.get_by_id(id)
        if tournament is None:
            return None

        for attr, value in kwargs.items():
            setattr(tournament, attr, value)

        if "registry_deadline" in kwargs:
            tournament.expired = datetime.now() > tournament.registry_deadline

        await self.session.flush()
        return tournament

    async def delete(self, id: int) -> Tournament | None:
        tournament = await self.get_by_id(id)
        if tournament is None:
            return None

        await self.session.delete(tournament)
        await self.session.flush()
        return tournament

    async def mark_as_active(self, id: int) -> Tournament | None:
        tournament = await self.get_by_id(id)
        if tournament is None:
            return None

        tournament.expired = False
        await self.session.flush()
        return tournament

    async def mark_as_expired(self, id: int) -> Tournament | None:
        tournament = await self.get_by_id(id)
        if tournament is None:
            return None

        tournament.expired = True
        await self.session.flush()
        return tournament