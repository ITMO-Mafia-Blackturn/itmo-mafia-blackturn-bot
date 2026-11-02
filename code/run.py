# Импортируем недостающие модули
import logging
from asyncio import run

from aiogram import Bot, Dispatcher

from bot.admin import admin
from bot.user import user
from bot.tournament_admin import tournament_admin
from bot.tournament_user import tournament_user
from config import BOT_API, ENV
import os
from database.models import async_main

# Запуск бота

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await async_main()
    from aiogram.client.session.aiohttp import AiohttpSession
    
    if ENV == "test":
        PROXY_URL = os.getenv("PROXY_URL", "socks5://127.0.0.1:10808")

        # Передаем сессию с прокси, если PROXY_URL задан
        session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None

        bot = Bot(token=BOT_API, 
                session=session)
        dp = Dispatcher()  # Получение обновлений бота
        dp.include_routers(admin, user, tournament_admin, tournament_user)
        
        await bot.delete_webhook(drop_pending_updates=True)
        
        await dp.start_polling(bot, handle_signals=False, close_bot_session=True)
        
    else: 
        
        bot = Bot(token=BOT_API)
        dp = Dispatcher()  # Получение обновлений бота
        dp.include_routers(admin, user, tournament_admin, tournament_user)
        
        await bot.delete_webhook(drop_pending_updates=True)
        
        await dp.start_polling(bot, handle_signals=False, close_bot_session=True)

# Запуск программы
if __name__ == "__main__":  # Создаём точку входа
    try:
        # Уведомляем о запуске бота
        print("Бот включён!")
        run(main())
        # Обработаем выключение бота
    except KeyboardInterrupt:
        print("Бот выключен!")
