from aiogram import Router
from bot.user.states import EventSignUp, ProfileEdit, Achievements, PairRating, UpdateProfile
from bot.user.commands import user as commands_router
from bot.user.achievements import user as achievements_router
from bot.user.events import user as events_router
from bot.user.event_signup import user as event_signup_router
from bot.user.profile import user as profile_router
from bot.user.profile_updates import user as profile_updates_router

user = Router()
user.include_routers(
    commands_router,
    achievements_router,
    events_router,
    event_signup_router,
    profile_router,
    profile_updates_router,
)
