from aiogram import Router
from bot.admin.states import *
from bot.admin.main import admin as main_router
from bot.admin.access import admin as access_router
from bot.admin.mailing import admin as mailing_router
from bot.admin.event_management import admin as event_management_router
from bot.admin.event_delivery import admin as event_delivery_router

admin = Router()
admin.include_routers(main_router, access_router, mailing_router, event_management_router, event_delivery_router)
