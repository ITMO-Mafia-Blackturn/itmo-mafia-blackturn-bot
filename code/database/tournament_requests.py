from datetime import datetime
from logging import exception
from typing import Optional

from sqlalchemy import and_
from sqlalchemy import select, delete, update, func, text

from config import ADMIN_CHATS_INFO
from database.models import Admin, BannedUser, UserInMailing, Event, EventSingUp, UserProfile,\
                            Tournaments, TournamentPlayers, PlayerTournamentRegistries
from database.models import async_session
from utils import setup_logger

logger = setup_logger()

async def get_tournaments():
    with async_session() as session:
        return session.scalars(select(Tournaments))

async def get_active_tournaments():
    with async_session() as session:
        return session.scalars(select(Tournaments).where((Tournaments.expired == False)))

