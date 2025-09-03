import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from config import ADMIN_IDS, LOBBY_TIMEOUT, GAME_TIMEOUT
from dependencies import get_bot, get_db
from keyboards import get_connect_keyboard, get_game_result_keyboard
from utils.helpers import format_game_result

router = Router()
db = get_db()

user_dice_throws = {}

@router.message(Command("game"))
async def create_game(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>❌ Только админ может создавать игры !</b>")
        return
        
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("<b>❌ Использование: /game @username1 @username2 !</b>")
            return
            
        username1 = parts[1].lstrip('@').lower()
        username2 = parts[2].lstrip('@').lower()
        
        if not username1 or not username2:
            await message.answer("<b>❌ Указаны некорректные username !</b>")
            return
            
        lobby_id = db.create_lobby(
            message.chat.id,
            message.from_user.id,
            username1,
            username2
        )
        
        await message.answer(
            f"<b>✅ Успешно создано лобби 1 vs 1 ✅</b>\n\n"
            f"<code>🆔 ID: {lobby_id}</code>\n"
            f"<b>👤 Игрок 1: @{username1}</b>\n"
            f"<b>👤 Игрок 2: @{username2}</b>\n\n"
            f"<b>⏰ Подключение в течение 5 минут !</b>\n"
            f"<blockquote>⚡ Торопитесь присоединиться ! ⚡</blockquote>",
            reply_markup=get_connect_keyboard(lobby_id)
        )
        
        asyncio.create_task(lobby_timeout(lobby_id))
        
    except Exception as e:
        await message.answer(f"<b>❌ Ошибка при создании лобби: {e} !</b>")

async def lobby_timeout(lobby_id: str):
    """Таймер для удаления лобби при неактивности"""
    await asyncio.sleep(LOBBY_TIMEOUT)
    
    lobby_data = db.get_lobby(lobby_id)
    if lobby_data and lobby_data["status"] == "waiting":
        # Находим кто не подключился
        not_connected = []
        for username, player_data in lobby_data["players"].items():
            if not player_data["connected"]:
                not_connected.append(username)
        
        db.delete_lobby(lobby_id)
        bot = get_bot()
        
        # Отправляем в чат
        try:
            if not_connected:
                await bot.send_message(
                    lobby_data["chat_id"],
                    f"<b>❌ Лобби {lobby_id} удалено !</b>\n\n"
                    f"<b>👥 Игроки: @{', @'.join(lobby_data['players'].keys())}</b>\n"
                    f"<b>❌ Не подключились: @{', @'.join(not_connected)}</b>\n"
                    f"<blockquote>⏰ Время на подключение истекло ! ⏰</blockquote>"
                )
            else:
                await bot.send_message(
                    lobby_data["chat_id"],
                    f"<b>❌ Лобби {lobby_id} удалено по таймауту !</b>"
                )
        except:
            pass

@router.callback_query(F.data.startswith("connect_"))
async def connect_to_lobby(callback: CallbackQuery):
    lobby_id = callback.data.split("_")[1]
    username = callback.from_user.username.lower() if callback.from_user.username else None
        
    if not username:
        await callback.answer("<b>❌ У вас должен быть username !</b>", show_alert=True)
        return
        
    lobby_data = db.get_lobby(lobby_id)
    
    if not lobby_data:
        await callback.answer("<b>❌ Лобби не найдено или время истекло !</b>", show_alert=True)
        return
        
    lobby_usernames = [name.lower() for name in lobby_data["players"].keys()]
    if username not in lobby_usernames:
        await callback.answer("<b>❌ Вы не участник этой игры !</b>", show_alert=True)
        return
        
    original_username = None
    for player_username in lobby_data["players"].keys():
        if player_username.lower() == username:
            original_username = player_username
            break
            
    if db.connect_player(lobby_id, original_username):
        await callback.answer("<b>✅ Вы подключились к лобби !</b>")
        
        lobby_data = db.get_lobby(lobby_id)
        all_connected = all(player["connected"] for player in lobby_data["players"].values())
        
        if all_connected:
            db.update_lobby_status(lobby_id, "playing")
            players = list(lobby_data["players"].keys())
            
            bot = get_bot()
            await bot.send_message(
                lobby_data["chat_id"],
                f"<b>🎮 Все игроки подключились к лобби {lobby_id} ! 🎮</b>\n\n"
                f"<b>👤 @{players[0]} и 👤 @{players[1]}</b>\n\n"
                f"<b>🎲 Кидайте по 2 кубика в этот чат !</b>\n"
                f"<b>⏰ Время на броски: 5 минут !</b>\n"
                f"<b>❌ Если не бросите - автоматическое поражение !</b>\n"
                f"<blockquote>⚡ Удачи игрокам ! ⚡</blockquote>"
            )
            
            # ЗАПУСКАЕМ ТАЙМЕР ДЛЯ ИГРЫ
            asyncio.create_task(game_timeout(lobby_id))
            
    else:
        await callback.answer("<b>❌ Ошибка подключения !</b>", show_alert=True)

async def game_timeout(lobby_id: str):
    """Таймер для автоматического завершения игры"""
    await asyncio.sleep(GAME_TIMEOUT)
    
    from dependencies import get_bot, get_db
    bot = get_bot()
    db = get_db()
    
    lobby_data = db.get_lobby(lobby_id)
    if lobby_data and lobby_data["status"] == "playing":
        
        players = list(lobby_data["players"].keys())
        scores = {}
        losers = []
        
        for player in players:
            dice_values = lobby_data["players"][player]["dice"]
            if dice_values and len(dice_values) == 2:
                scores[player] = sum(dice_values)
            else:
                scores[player] = 0
                losers.append(player)
        
        # Если оба не бросили - оба проиграли
        if len(losers) == 2:
            db.update_lobby_status(lobby_id, "timeout", None, scores)
            await bot.send_message(
                lobby_data["chat_id"],
                f"<b>⏰ Время вышло ! ⏰</b>\n\n"
                f"<b>❌ Оба игрока не бросили кубики !</b>\n"
                f"<b>👤 @{players[0]} и 👤 @{players[1]} - проиграли по таймауту !</b>\n"
                f"<blockquote>😞 В следующий раз будьте быстрее ! 😞</blockquote>"
            )
            
            # Отправляем админу
            try:
                await bot.send_message(
                    lobby_data["admin_id"],
                    f"<b>⏰ ЛОББИ {lobby_id} - ТАЙМАУТ ⏰</b>\n\n"
                    f"<b>👥 Игроки: @{', @'.join(players)}</b>\n"
                    f"<b>❌ Оба не бросили кубики</b>\n"
                    f"<blockquote>🕐 Время на броски истекло</blockquote>"
                )
            except:
                pass
                
        # Если один не бросил - он проиграл
        elif len(losers) == 1:
            winner = [p for p in players if p not in losers][0]
            db.update_lobby_status(lobby_id, "finished", winner, scores)
            await bot.send_message(
                lobby_data["chat_id"],
                f"<b>⏰ Время вышло ! ⏰</b>\n\n"
                f"<b>❌ @{losers[0]} не бросил кубики !</b>\n"
                f"<b>🏆 Победитель: @{winner} по таймауту !</b>\n"
                f"<blockquote>🎉 Поздравляем с победой ! 🎉</blockquote>"
            )
            
            # Отправляем админу
            try:
                await bot.send_message(
                    lobby_data["admin_id"],
                    f"<b>🏆 ПОБЕДИТЕЛЬ ЛОББИ {lobby_id} 🏆</b>\n\n"
                    f"<b>👥 Игроки: @{', @'.join(players)}</b>\n"
                    f"<b>🎯 Победитель: @{winner}</b>\n"
                    f"<b>📊 Причина: противник не бросил кубики</b>\n"
                    f"<blockquote>⚡ Информация о завершенной игре ⚡</blockquote>"
                )
            except:
                pass
                
        else:
            # Оба бросили - обрабатываем результаты
            await process_game_result(lobby_id, lobby_data["chat_id"], force=True)
        
        # Перемещаем в историю
        db.move_to_history(lobby_id)

@router.message(F.dice)
async def handle_dice_throw(message: Message):
    username = message.from_user.username.lower() if message.from_user.username else None
    if not username:
        return
        
    lobbies = db.get_all_lobbies()
    for lobby_id, lobby_data in lobbies.items():
        lobby_usernames = [name.lower() for name in lobby_data["players"].keys()]
        
        if (lobby_data["chat_id"] == message.chat.id and 
            lobby_data["status"] == "playing" and 
            username in lobby_usernames):
            
            original_username = None
            for player_username in lobby_data["players"].keys():
                if player_username.lower() == username:
                    original_username = player_username
                    break
            
            if original_username not in user_dice_throws:
                user_dice_throws[original_username] = []
            
            user_dice_throws[original_username].append(message.dice.value)
            
            if len(user_dice_throws[original_username]) == 2:
                db.set_player_dice(lobby_id, original_username, user_dice_throws[original_username].copy())
                del user_dice_throws[original_username]
                
                await message.answer(f"<b>✅ @{original_username} бросил кубики !</b>")
                
                lobby_data = db.get_lobby(lobby_id)
                all_thrown = all(player["dice"] is not None for player in lobby_data["players"].values())
                
                if all_thrown:
                    await process_game_result(lobby_id, message.chat.id)
            break

async def process_game_result(lobby_id: str, chat_id: int, force: bool = False):
    bot = get_bot()
    db = get_db()
    
    lobby_data = db.get_lobby(lobby_id)
    if not lobby_data:
        return
        
    players = list(lobby_data["players"].keys())
    
    scores = {}
    for player in players:
        dice_values = lobby_data["players"][player]["dice"]
        if dice_values and len(dice_values) == 2:
            scores[player] = sum(dice_values)
        else:
            scores[player] = 0
    
    player1, player2 = players
    score1 = scores[player1]
    score2 = scores[player2]
    
    if score1 > score2:
        winner = player1
        db.update_lobby_status(lobby_id, "finished", winner, scores)
        result_text = format_game_result(db.get_lobby(lobby_id))
        await bot.send_message(chat_id, result_text, reply_markup=get_game_result_keyboard())
        
        try:
            await bot.send_message(
                lobby_data["admin_id"],
                f"<b>🏆 ПОБЕДИТЕЛЬ ЛОББИ {lobby_id} 🏆</b>\n\n"
                f"<b>👥 Игроки: @{player1} vs @{player2}</b>\n"
                f"<b>📊 Счет: {score1} - {score2}</b>\n"
                f"<b>🎯 Победитель: @{winner}</b>\n"
                f"<blockquote>⚡ Информация о завершенной игре ⚡</blockquote>"
            )
        except:
            pass
            
    elif score2 > score1:
        winner = player2
        db.update_lobby_status(lobby_id, "finished", winner, scores)
        result_text = format_game_result(db.get_lobby(lobby_id))
        await bot.send_message(chat_id, result_text, reply_markup=get_game_result_keyboard())
        
        try:
            await bot.send_message(
                lobby_data["admin_id"],
                f"<b>🏆 ПОБЕДИТЕЛЬ ЛОББИ {lobby_id} 🏆</b>\n\n"
                f"<b>👥 Игроки: @{player1} vs @{player2}</b>\n"
                f"<b>📊 Счет: {score1} - {score2}</b>\n"
                f"<b>🎯 Победитель: @{winner}</b>\n"
                f"<blockquote>⚡ Информация о завершенной игре ⚡</blockquote>"
            )
        except:
            pass
            
    else:
        # НИЧЬЯ - ПЕРЕКИДЫВАЕМ, А НЕ ЗАВЕРШАЕМ
        if not force:
            await handle_draw(lobby_id, chat_id, players)
            return  # НЕ перемещаем в историю!
        else:
            db.update_lobby_status(lobby_id, "draw", None, scores)
            result_text = format_game_result(db.get_lobby(lobby_id))
            await bot.send_message(chat_id, result_text, reply_markup=get_game_result_keyboard())
    
    # Перемещаем в историю только если игра завершена (не ничья для переброса)
    db.move_to_history(lobby_id)

async def handle_draw(lobby_id: str, chat_id: int, players: list):
    """Обработка ничьи - переброс кубиков"""
    bot = get_bot()
    db = get_db()
    
    # Сбрасываем броски для перекидывания
    for player in players:
        db.set_player_dice(lobby_id, player, None)
    
    # Очищаем временные данные
    for player in players:
        if player in user_dice_throws:
            del user_dice_throws[player]
    
    # НЕ перемещаем в историю! Оставляем лобби активным
    db.update_lobby_status(lobby_id, "playing")  # Возвращаем статус playing
    
    await bot.send_message(
        chat_id,
        f"<b>🎯 НИЧЬЯ ! 🎯</b>\n\n"
        f"<b>👤 @{players[0]} и 👤 @{players[1]}</b>\n\n"
        f"<b>🔄 Перекидывайте кубики заново !</b>\n"
        f"<b>🎲 Кидайте по 2 кубика снова !</b>\n"
        f"<b>⏰ Время: 5 минут снова !</b>\n"
        f"<blockquote>⚡ На этот раз определим победителя ! ⚡</blockquote>"
    )
    
    # Запускаем таймер заново
    asyncio.create_task(game_timeout(lobby_id))

async def create_lobby_from_tournament(tournament_id: str, participants: list) -> list:
    """Создание лобби из участников турнира"""
    from dependencies import get_bot, get_db
    bot = get_bot()
    db = get_db()
    
    # Получаем данные турнира
    tournament_data = None
    all_tournaments = db.get_all_tournaments()
    for tid, data in all_tournaments.items():
        if tid == tournament_id:
            tournament_data = data
            break
    
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
            
            lobbies.append(lobby_id)
            
            # Отправляем сообщение о создании лобби в ЧАТ
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
            
            # ЗАПУСКАЕМ ТАЙМЕР ДЛЯ ЛОББИ - ВАЖНО!
            asyncio.create_task(game_timeout(lobby_id))
    
    return lobbies

@router.message(Command("cancel"))
async def cancel_game(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    global user_dice_throws
    user_dice_throws = {}
    await message.answer("<b>✅ Временные данные очищены !</b>")