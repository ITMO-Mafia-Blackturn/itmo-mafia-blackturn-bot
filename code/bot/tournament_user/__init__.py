from aiogram import Router
from bot.tournament_user.onboarding import tournament_user as onboarding_router
from bot.tournament_user.registration import tournament_user as registration_router

tournament_user = Router()
tournament_user.include_routers(onboarding_router, registration_router)
