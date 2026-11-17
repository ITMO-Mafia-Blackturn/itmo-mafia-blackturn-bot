from sqlalchemy import select

from database.models import Tournament, async_session


async def get_tournaments() -> list[Tournament]:
    async with async_session() as session:
        result = await session.scalars(select(Tournament))
        return list(result.all())


async def get_active_tournaments() -> list[Tournament]:
    async with async_session() as session:
        result = await session.scalars(
            select(Tournament).where(Tournament.expired.is_(False))
        )
        return list(result.all())
