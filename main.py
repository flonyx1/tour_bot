# main.py
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import admin, game, common, tournament
from dependencies import set_bot_instance
from middleware import AccessMiddleware, RateLimitMiddleware

async def main():
    storage = MemoryStorage()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)
    
    set_bot_instance(bot)
    
    # Middleware
    access_middleware = AccessMiddleware()
    rate_limit_middleware = RateLimitMiddleware()
    
    dp.message.middleware(access_middleware)
    dp.callback_query.middleware(access_middleware)
    dp.message.middleware(rate_limit_middleware)
    dp.callback_query.middleware(rate_limit_middleware)
    
    # Routers
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(game.router)
    dp.include_router(tournament.router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())