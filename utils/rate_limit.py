# utils/rate_limit.py
from functools import wraps
from dependencies import get_cache

def rate_limit(limit: int, period: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            message = args[0] if args else None
            
            if hasattr(message, 'from_user') and message.from_user:
                user_id = message.from_user.id
                key = f"{func.__name__}_{user_id}"
                
                if not cache.check_rate_limit(key, limit, period):
                    if hasattr(message, 'answer'):
                        await message.answer(f"⚠️ Слишком много запросов! Подождите {period} секунд.")
                    return
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator