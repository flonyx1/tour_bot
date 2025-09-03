# dependencies.py
from aiogram import Bot
from database import Database
from cache import CacheManager

bot_instance = None
db_instance = Database()
cache_manager = CacheManager()

def set_bot_instance(bot: Bot):
    global bot_instance
    bot_instance = bot

def get_bot() -> Bot:
    if bot_instance is None:
        raise ValueError("Bot instance not set! Call set_bot_instance first!")
    return bot_instance

def get_db() -> Database:
    return db_instance

def get_cache() -> CacheManager:
    return cache_manager