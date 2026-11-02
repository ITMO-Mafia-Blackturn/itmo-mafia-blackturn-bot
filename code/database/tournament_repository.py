from datetime import datetime
from typing import Literal

from sqlalchemy import select

from models import Tournament
from database import async_session
from sqlalchemy.ext.asyncio import AsyncSession

class TournamentRepository:
    
    def __init__(self):
        with async_session() as session:
            self.session: AsyncSession = session
    
    async def get_by_id(self, id: int) -> Tournament | None:
        return await self.session.get(Tournament, id)
    
    async def get_all(self) -> list[Tournament] | None:
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

        tournament = await self.get_by_id(id)

        ALLOWED_FIELDS = {
            "description",
            "place",
            "date",
            "registry_deadline",
            "capacity"
        }
        
        if not kwargs.keys() <= self.ALLOWED_FIELDS:
            raise ValueError("Недопустимые атрибуты")
        
        if tournament is None:
            return None

        for attr, value in kwargs.items():
            if hasattr(tournament, attr):
                setattr(tournament, attr, value)

        if attr == "date" or attr == "registry_deadline":
            if datetime.now() >= tournament.registry_deadline: 
                self.mark_as_expired(tournament.id)
        
        
        await self.session.flush()

        return tournament
    
    async def delete(self, id: int) -> Tournament:
        return await self.session.delete(
            select(Tournament)
            .where(Tournament.id == id)
            )
        
    async def mark_as_active(self, id: id) -> Tournament:
        tournament: Tournament = await self.get_by_id(id)
        
        setattr(tournament, "expired", False)
        await self.session.flush()
        
        return tournament

    async def mark_as_expired(self, id: id) -> Tournament:
        tournament: Tournament = await self.get_by_id(id)
        
        setattr(tournament, "expired", True)
        await self.session.flush()
        
        return tournament