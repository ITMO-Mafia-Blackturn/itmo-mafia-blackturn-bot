from datetime import datetime
from typing import Optional, Union

from sqlalchemy import Boolean, DateTime, LargeBinary
from sqlalchemy import String, Integer, ForeignKey, TIMESTAMP, BigInteger
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DB_USER, DB_PASSWORD, DB_NAME, DB_PORT, DB_HOST

# Use your PostgreSQL database URL
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаём бд и подключаемся к ней
engine = create_async_engine(url=DATABASE_URL)
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
    description: Mapped[str] = mapped_column(String(700), nullable= False)
    place: Mapped[str] = mapped_column(String(150), nullable = False)
    date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable = False)
    expired: Mapped[bool] = mapped_column(Boolean, nullable = False)
    registry_deadline: Mapped[datetime] = mapped_column(DateTime)
    capacity: Mapped[int] = mapped_column(int, nullable = False)
    
    def is_registration_open(self) -> bool:
        return (
            not self.expired
            and datetime.now() <= self.expired
        )
    
    def is_full(self, registered_users_count: int) -> bool:
        return registered_users_count >= self.capacity

class TournamentPlayer(Base):
    __tablename__ = "tournament_players"
    
    id: Mapped[int] = mapped_column(primary_key = True)
    user_profile_id: Mapped[int] = mapped_column(ForeignKey(UserProfile.id))
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable= True)

class PlayerTournamentRegistrie(Base):
    __tablename__ = "tournament_registries"
    
    id: Mapped[int] = mapped_column(primary_key = True)
    tournament_player_id: Mapped[int] = mapped_column(ForeignKey(TournamentPlayer.id))
    tournament: Mapped[bool] = mapped_column(Boolean, default = False)
    approved: Mapped[bool] = mapped_column(Boolean, default = False)

# При запуске главного файла создаём таблицы


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
