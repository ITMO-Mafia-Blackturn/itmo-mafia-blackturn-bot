from aiogram import Router
from bot.tournament_admin.catalog import tournament_admin as catalog_router
from bot.tournament_admin.catalog_actions import tournament_admin as catalog_actions_router
from bot.tournament_admin.exports import tournament_admin as exports_router
from bot.tournament_admin.review_actions import tournament_admin as review_router
from bot.tournament_edit import router as edit_router

tournament_admin = Router()
tournament_admin.include_routers(
    edit_router,
    catalog_router,
    catalog_actions_router,
    exports_router,
    review_router,
)
