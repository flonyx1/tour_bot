from typing import Final


BOT_TOKEN: Final = "8370839605:AAHcrzWu9D6Y1ITECnJrkryARHVduRqOZ_o"
ADMIN_IDS: Final = [7557982628]  # Замените на ID админа
ALLOWED_CHAT_ID: Final = -1003026944355  # ID чата где проходят игры
ALLOWED_CHANNEL_ID: Final = -1002958222504  # ID канала где публикуются турниры
LOBBY_TIMEOUT: Final = 300  # 5 минут в секундах для подключения
GAME_TIMEOUT: Final = 300   # 5 минут в секундах для игры
MIN_TOURNAMENT_TIMEOUT: Final = 5 * 3600  # 5 часов минимум
MAX_TOURNAMENT_TIMEOUT: Final = 12 * 3600  # 12 часов максимум