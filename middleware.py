# middleware.py
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from config import ALLOWED_CHAT_ID, ADMIN_IDS
from dependencies import get_cache

class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, CallbackQuery):
            return await handler(event, data)
        
        if isinstance(event, Message) and event.chat.type == "private":
            if event.from_user.id not in ADMIN_IDS:
                await event.answer("🚫 Бот не работает в личных сообщениях!")
                return
            
            return await handler(event, data)
        
        if isinstance(event, Message):
            if event.chat.id != ALLOWED_CHAT_ID:
                await event.answer("🚫 Бот работает только в основном чате!")
                return
        
        return await handler(event, data)

class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        cache = get_cache()
        
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
            key = f"rate_limit_{user_id}"
            
            if not cache.check_rate_limit(key, 5, 60):  # 5 запросов в минуту
                if isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Слишком много запросов! Подождите немного.", show_alert=True)
                return
            
            # Additional spam protection for dice throws
            if isinstance(event, Message) and event.dice:
                dice_key = f"dice_limit_{user_id}"
                if not cache.check_rate_limit(dice_key, 3, 10):  # 3 кубика в 10 секунд
                    await event.answer("⚠️ Слишком много бросков! Подождите 10 секунд.")
                    return
        
        return await handler(event, data)