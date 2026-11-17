from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import PlayerTournamentRegistration


class PlayerTournamentRegistrationRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self, tournament_id: int) -> list[PlayerTournamentRegistration]:
        result = await self.session.execute(
            select(PlayerTournamentRegistration).where(
                PlayerTournamentRegistration.tournament_id == tournament_id
            )
        )
        return list(result.scalars().all())
