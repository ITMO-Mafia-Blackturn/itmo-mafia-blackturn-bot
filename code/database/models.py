import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, LargeBinary, text
from sqlalchemy import String, Integer, ForeignKey, TIMESTAMP, BigInteger
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DB_USER, DB_PASSWORD, DB_NAME, DB_PORT, DB_HOST

# Use your PostgreSQL database URL
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаём бд и подключаемся к ней
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
engine = create_async_engine(
    url=DATABASE_URL,
    hide_parameters=True,
)
async_session = async_sessionmaker(engine)


# Создаём родительский класс для построения моделей
class Base(AsyncAttrs, DeclarativeBase):
    pass


# Таблица с забаненными пользователями


class BannedUser(Base):
    __tablename__ = "banned_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)


# Таблица с пользователями, которые находятся в рассылке


class UserInMailing(Base):
    __tablename__ = "users_in_mailing"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)


# Таблица с айди чата администраторов


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)


# Таблица для мероприятий


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    date: Mapped[datetime] = mapped_column(TIMESTAMP)  # Using TIMESTAMP for events
    limit: Mapped[int] = mapped_column(Integer, default=40)
    guest_limit: Mapped[int] = mapped_column(Integer, default=20)
    description: Mapped[str] = mapped_column(String(400))
    is_signup_open: Mapped[int] = mapped_column(Integer)
    removed: Mapped[bool] = mapped_column(Boolean)
    passes_sent: Mapped[bool] = mapped_column(Boolean, default=False)


# Таблица для записавшихся на меропрития пользователей


class EventSingUp(Base):
    __tablename__ = "event_singup"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    event_status: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer)
    event_id: Mapped[int] = mapped_column(ForeignKey(Event.id))
    username: Mapped[str] = mapped_column(String(100), nullable=True)


# Таблица профилей


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    polemica_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    nickname: Mapped[str] = mapped_column(String(3))
    is_itmo: Mapped[bool] = mapped_column(Boolean)
    level: Mapped[int] = mapped_column(Integer)
    full_name: Mapped[str] = mapped_column(String(100), nullable=True)
    passport: Mapped[str] = mapped_column(String(10), nullable=True)
    phone: Mapped[str] = mapped_column(String(11), nullable=True)
    personal_data_agreement: Mapped[bool] = mapped_column(Boolean, default=False)
    username: Mapped[str] = mapped_column(String(100), nullable=True)


class Tournament(Base):
    __tablename__ = "tournaments"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(700), nullable=False)
    description: Mapped[str] = mapped_column(String(700), nullable=False)
    place: Mapped[str] = mapped_column(String(150), nullable = False)
    date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable = False)
    expired: Mapped[bool] = mapped_column(Boolean, nullable = False)
    registry_deadline: Mapped[datetime] = mapped_column(DateTime)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    guest_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    passes_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    
    def is_registration_open(self) -> bool:
        return (
            not self.expired
            and datetime.now() <= self.registry_deadline
        )
    
    def is_full(self, registered_users_count: int) -> bool:
        return registered_users_count >= self.capacity

class TournamentPlayer(Base):
    __tablename__ = "tournament_players"
    
    id: Mapped[int] = mapped_column(primary_key = True)
    user_profile_id: Mapped[int] = mapped_column(ForeignKey(UserProfile.id))
    polemica_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    polemica_nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable= True)

class PlayerTournamentRegistration(Base):
    __tablename__ = "tournament_registries"
    
    id: Mapped[int] = mapped_column(primary_key = True)
    tournament_player_id: Mapped[int] = mapped_column(ForeignKey(TournamentPlayer.id))
    tournament_id: Mapped[int | None] = mapped_column(
        ForeignKey(Tournament.id), nullable=True
    )
    approved: Mapped[bool] = mapped_column(Boolean, default = False)
    rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

async def async_main():
    logger = logging.getLogger(__name__)
    logger.info(
        "Connecting to PostgreSQL: host=%s port=%s database=%s",
        DB_HOST,
        DB_PORT,
        DB_NAME,
    )
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT current_database(), inet_server_addr(), inet_server_port()"
            )
        )
        database, server_address, server_port = result.one()
        logger.info(
            "Connected to PostgreSQL: database=%s server=%s:%s",
            database,
            server_address,
            server_port,
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
