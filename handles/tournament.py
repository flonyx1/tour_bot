import asyncio
import logging
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from config import ADMIN_IDS, ALLOWED_CHANNEL_ID, ALLOWED_CHAT_ID
from dependencies import get_bot, get_db
from keyboards import get_tournament_join_keyboard, get_connect_keyboard
from handlers.game import create_lobby_from_tournament, game_timeout

logger = logging.getLogger(__name__)

router = Router()
db = get_db()

# Для ограничения частоты редактирования
last_edit_time = {}

async def create_tournament_command(admin_id: int, max_players: int, hours: int) -> str:
    try:
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
            
        tournament_timeout = hours * 3600
        asyncio.create_task(tournament_timeout_func(tournament_id, tournament_timeout))
        
        return tournament_id
        
    except Exception as e:
        logger.error(f"Ошибка создания турнира: {e}")
        raise e

async def tournament_timeout_func(tournament_id: str, timeout: int):
    """Таймер для автоматического старта турнира"""
    await asyncio.sleep(timeout)
    
    tournament_data = db.get_tournament(tournament_id)
    if tournament_data and tournament_data["status"] == "registration":
        bot = get_bot()
        
        participants = tournament_data["participants"]
        logger.info(f"Регистрация турнира {tournament_id} завершена. Участников: {len(participants)}")
        
        if len(participants) >= 2:
            lobbies = await create_lobby_from_tournament(tournament_id, participants)
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

async def check_tournament_completion(tournament_id: str):
    """Бесконечная проверка завершения всех лобби турнира"""
    from dependencies import get_bot, get_db
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

@router.message(Command("tournament"))
async def create_tournament_via_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>❌ Только админ может создавать турниры !</b>")
        return
        
    await message.answer("<b>🎯 Используйте админ-панель для создания турниров !</b>\n\n<code>Напишите /admin</code>")

@router.callback_query(F.data.startswith("join_tournament_"))
async def join_tournament(callback: CallbackQuery):
    try:
        tournament_id = callback.data.split("_")[2]
        username = callback.from_user.username
        
        logger.info(f"Попытка присоединения @{username} к турниру {tournament_id}")
        
        if not username:
            await callback.answer("<b>❌ У вас должен быть username !</b>", show_alert=True)
            return
            
        tournament_data = db.get_tournament(tournament_id)
        
        if not tournament_data:
            await callback.answer("<b>❌ Турнир не найден !</b>", show_alert=True)
            return
            
        if tournament_data["status"] != "registration":
            await callback.answer("<b>❌ Регистрация на турнир закрыта !</b>", show_alert=True)
            return
            
        success = db.add_tournament_participant(tournament_id, username)
        
        if success:
            tournament_data = db.get_tournament(tournament_id)
            participants_count = len(tournament_data["participants"])
            max_players = tournament_data["max_players"]
            
            logger.info(f"Участник @{username} добавлен в турнир {tournament_id}. Теперь участников: {participants_count}")
            
            await callback.answer(f"✅ Вы участвуете в турнире ! ({participants_count}/{max_players})", show_alert=True)
            
            # ОБНОВЛЯЕМ СООБЩЕНИЕ ТОЛЬКО КАЖДЫЕ 5 УЧАСТНИКОВ ИЛИ ПРИ ЗАПОЛНЕНИИ
            if participants_count % 5 == 0 or participants_count >= max_players:
                bot = get_bot()
                try:
                    await bot.edit_message_text(
                        chat_id=ALLOWED_CHANNEL_ID,
                        message_id=tournament_data["channel_message_id"],
                        text=f"<b>🎯 ОБЪЯВЛЕН НОВЫЙ ТУРНИР 🎯</b>\n\n"
                             f"<code>🆔 ID: {tournament_id}</code>\n"
                             f"<b>👥 Участников: {participants_count}/{max_players}</b>\n"
                             f"<b>⏰ Регистрация: {tournament_data['hours']} часов</b>\n"
                             f"<b>🎮 Игры пройдут в основном чате</b>\n\n"
                             f"<b>⚡ Участвуйте в турнире !</b>\n"
                             f"<blockquote>🏆 Победитель получит славу и уважение ! 🏆</blockquote>",
                        reply_markup=get_tournament_join_keyboard(tournament_id)
                    )
                    logger.info(f"Сообщение турнира {tournament_id} обновлено")
                except Exception as e:
                    logger.error(f"Ошибка редактирования сообщения: {e}")
                
            # Если набралось достаточно участников - запускаем турнир
            if participants_count >= max_players:
                logger.info(f"Турнир {tournament_id} заполнен! Запускаем...")
                db.update_tournament_status(tournament_id, "starting")
                await asyncio.sleep(2)
                
                tournament_data = db.get_tournament(tournament_id)
                lobbies = await create_lobby_from_tournament(tournament_id, tournament_data["participants"])
                db.update_tournament_status(tournament_id, "started", lobbies)
                
                bot = get_bot()
                await bot.send_message(
                    ALLOWED_CHANNEL_ID,
                    f"<b>🎯 ТУРНИР НАЧАЛСЯ 🎯</b>\n\n"
                    f"<code>🆔 ID: {tournament_id}</code>\n"
                    f"<b>👥 Участников: {participants_count}</b>\n"
                    f"<b>🎮 Лобби: {len(lobbies)}</b>\n"
                    f"<b>📍 Игры проходят в основном чате</b>\n\n"
                    f"<b>⚡ Удачи всем игрокам !</b>\n"
                    f"<blockquote>🏆 Сражайтесь за победу ! 🏆</blockquote>"
                )
                
                # Запускаем проверку завершения турнира
                asyncio.create_task(check_tournament_completion(tournament_id))
                
        else:
            await callback.answer("<b>❌ Не удалось присоединиться к турниру !</b>", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка в join_tournament: {e}")
        await callback.answer("<b>❌ Ошибка при присоединении к турниру !</b>", show_alert=True)