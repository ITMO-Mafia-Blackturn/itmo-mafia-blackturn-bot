from database.models import TournamentPlayer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class TournamentPlayerRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    ALLOWED_FIELDS = {
        "photo",
        "polemica_id",
        "polemica_nickname",
    }

    async def get_by_id(self, id: int) -> TournamentPlayer | None:
        return await self.session.get(TournamentPlayer, id)

    async def get_all(self) -> list[TournamentPlayer]:
        result = await self.session.execute(
            select(TournamentPlayer)
        )
        return list(result.scalars().all())


    async def create(self, player: TournamentPlayer) -> TournamentPlayer:
        self.session.add(player)
        await self.session.flush()
        return player

    async def update(
        self,
        id: int,
        **kwargs
    ) -> TournamentPlayer | None:
        if not kwargs.keys() <= self.ALLOWED_FIELDS:
            raise ValueError("Недопустимые атрибуты")

        player = await self.get_by_id(id)
        if player is None:
            return None

        for attr, value in kwargs.items():
            setattr(player, attr, value)

        await self.session.flush()
        return player

    async def delete(self, id: int) -> TournamentPlayer | None:
        player = await self.get_by_id(id)
        if player is None:
            return None

        await self.session.delete(player)
        await self.session.flush()
        return player
    