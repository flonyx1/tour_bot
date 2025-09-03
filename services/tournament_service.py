# services/tournament_service.py
import asyncio
import logging
import time
from dependencies import get_bot, get_db
from keyboards import get_connect_keyboard, get_tournament_join_keyboard
from config import ALLOWED_CHANNEL_ID, ALLOWED_CHAT_ID

logger = logging.getLogger(__name__)

async def create_tournament_command(admin_id: int, max_players: int, hours: int) -> str:
    """Создание турнира через админ-панель"""
    try:
        db = get_db()
        tournament_id = db.create_tournament(
            ALLOWED_CHAT_ID,
            admin_id,
            max_players,
            hours
        )
        
        logger.info(f"Создан турнир {tournament_id} для {max_players} игроков на {hours} часов")
        
        bot = get_bot()
        
        try:
            tournament_message = await bot.send_message(
                ALLOWED_CHANNEL_ID,
                f"<b>🎯 ОБЪЯВЛЕН НОВЫЙ ТУРНИР 🎯</b>\n\n"
                f"<code>🆔 ID: {tournament_id}</code>\n"
                f"<b>👥 Максимум игроков: {max_players}</b>\n"
                f"<b>⏰ Регистрация: {hours} часов</b>\n"
                f"<b>🎮 Игры пройдут в основном чате</b>\n\n"
                f"<b>⚡ Участвуйте в турнире !</b>\n"
                f"<blockquote>🏆 Победитель получит славу и уважение ! 🏆</blockquote>",
                reply_markup=get_tournament_join_keyboard(tournament_id)
            )
            
            db.update_tournament_message_id(tournament_id, tournament_message.message_id)
            logger.info(f"Турнир {tournament_id} опубликован в канале")
            
        except Exception as e:
            logger.error(f"Ошибка публикации турнира: {e}")
            raise e
            
        # Запускаем таймер для автоматического старта турнира
        tournament_timeout = hours * 3600
        asyncio.create_task(tournament_timeout_func(tournament_id, tournament_timeout))
        
        return tournament_id
        
    except Exception as e:
        logger.error(f"Ошибка создания турнира: {e}")
        raise e

async def tournament_timeout_func(tournament_id: str, timeout: int):
    """Таймер для автоматического старта турнира"""
    await asyncio.sleep(timeout)
    
    db = get_db()
    tournament_data = db.get_tournament(tournament_id)
    if tournament_data and tournament_data["status"] == "registration":
        bot = get_bot()
        
        participants = tournament_data["participants"]
        logger.info(f"Регистрация турнира {tournament_id} завершена. Участников: {len(participants)}")
        
        if len(participants) >= 2:
            lobbies = await create_tournament_lobbies(tournament_id, participants)
            db.update_tournament_status(tournament_id, "started", lobbies)
            
            await bot.send_message(
                ALLOWED_CHANNEL_ID,
                f"<b>🎯 ТУРНИР НАЧАЛСЯ 🎯</b>\n\n"
                f"<code>🆔 ID: {tournament_id}</code>\n"
                f"<b>👥 Участников: {len(participants)}</b>\n"
                f"<b>🎮 Создано игр: {len(lobbies)}</b>\n"
                f"<b>⏰ Регистрация длилась: {tournament_data['hours']} ч.</b>\n"
                f"<b>📍 Игры проходят в основном чате</b>\n\n"
                f"<b>⚡ Удачи всем игрокам !</b>\n"
                f"<blockquote>🏆 Сражайтесь за победу ! 🏆</blockquote>"
            )
            
            # Запускаем проверку завершения турнира
            asyncio.create_task(check_tournament_completion(tournament_id))
            
        else:
            db.update_tournament_status(tournament_id, "cancelled")
            await bot.send_message(
                ALLOWED_CHANNEL_ID,
                f"<b>❌ ТУРНИР ОТМЕНЕН ❌</b>\n\n"
                f"<code>🆔 ID: {tournament_id}</code>\n"
                f"<b>👥 Недостаточно участников: {len(participants)}/{tournament_data['max_players']}</b>\n"
                f"<b>⏰ Регистрация длилась: {tournament_data['hours']} ч.</b>\n"
                f"<blockquote>😞 В следующий раз будет больше участников ! 😞</blockquote>"
            )

async def create_tournament_lobbies(tournament_id: str, participants: list) -> list:
    """Создание лобби для турнира"""
    bot = get_bot()
    db = get_db()
    
    tournament_data = db.get_tournament(tournament_id)
    if not tournament_data:
        return []
    
    lobbies = []
    # Разбиваем участников на пары
    for i in range(0, len(participants), 2):
        if i + 1 < len(participants):
            username1 = participants[i]
            username2 = participants[i + 1]
            
            # Создаем лобби
            lobby_id = db.create_lobby(
                tournament_data["chat_id"],
                tournament_data["admin_id"],
                username1,
                username2
            )
            
            # Устанавливаем tournament_id для лобби
            db.set_lobby_tournament_id(lobby_id, tournament_id)
            
            lobbies.append(lobby_id)
            
            # Отправляем сообщение о создании лобби
            await bot.send_message(
                tournament_data["chat_id"],
                f"<b>🎮 ТУРНИРНОЕ ЛОББИ СОЗДАНО ! 🎮</b>\n\n"
                f"<code>🆔 ID: {lobby_id}</code>\n\n"
                f"<b>👤 @{username1} vs 👤 @{username2}</b>\n\n"
                f"<b>🎲 Игра: Кубы PvP</b>\n\n"
                f"<b>⏰ Время на броски: 5 минут !</b>\n"
                f"<b>❌ Если не бросите - автоматическое поражение !</b>\n\n"
                f"<blockquote>⚡ Удачи в турнире ! ⚡</blockquote>",
                reply_markup=get_connect_keyboard(lobby_id)
            )
            
            # Запускаем таймер для лобби
            asyncio.create_task(game_timeout(lobby_id))
    
    return lobbies

async def game_timeout(lobby_id: str):
    """Таймаут для игры в турнире"""
    from handlers.game import game_timeout as base_game_timeout
    await base_game_timeout(lobby_id)

async def check_tournament_completion(tournament_id: str):
    """Проверка завершения турнира"""
    bot = get_bot()
    db = get_db()
    
    # Проверяем каждые 30 секунд
    while True:
        await asyncio.sleep(30)
        
        tournament_data = db.get_tournament(tournament_id)
        if not tournament_data or tournament_data["status"] != "started":
            return
            
        all_finished = True
        winners = []
        
        # Проверяем все лобби турнира
        for lobby_id in tournament_data["lobbies"]:
            # Проверяем в активных лобби
            active_lobbies = db.get_all_lobbies()
            if lobby_id in active_lobbies:
                all_finished = False
                break
            
            # Проверяем в истории (завершенные игры)
            history_data = db._read_data().get("history", {})
            lobby_data = history_data.get(lobby_id)
            if lobby_data and lobby_data.get("winner"):
                winners.append(f"@{lobby_data['winner']}")
        
        # Если все лобби завершены
        if all_finished:
            db.update_tournament_status(tournament_id, "completed")
            
            # Формируем список победителей
            winners_text = ", ".join(winners) if winners else "нет победителей"
            
            # Отправляем в канал финальные результаты
            await bot.send_message(
                ALLOWED_CHANNEL_ID,
                f"<b>🏆 ТУРНИР ЗАВЕРШЕН 🏆</b>\n\n"
                f"<code>🎯 ID: {tournament_id}</code>\n"
                f"<b>👥 Участников: {len(tournament_data['participants'])}</b>\n"
                f"<b>🎮 Сыграно игр: {len(tournament_data['lobbies'])}</b>\n\n"
                f"<b>🏅 ПОБЕДИТЕЛИ ТУРНИРА:</b>\n"
                f"<b>{winners_text}</b>\n\n"
                f"<b>⚡ Поздравляем победителей !</b>\n"
                f"<blockquote>🎮 Спасибо всем за участие ! 🎮</blockquote>"
            )
            
            return