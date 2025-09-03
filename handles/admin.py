import asyncio
import time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from dependencies import get_db
from keyboards import get_admin_keyboard, get_lobby_list_keyboard, get_tournament_list_keyboard
from services.tournament_service import create_tournament_command

router = Router()
db = get_db()

last_edit_time = {}
EDIT_DELAY = 2.0

class TournamentCreation(StatesGroup):
    waiting_for_players = State()
    waiting_for_time = State()

async def safe_edit_message(chat_id, message_id, text, reply_markup=None):
    """Safe message editing with rate limiting"""
    current_time = time.time()
    key = f"{chat_id}_{message_id}"
    
    if key in last_edit_time:
        time_since_last = current_time - last_edit_time[key]
        if time_since_last < EDIT_DELAY:
            await asyncio.sleep(EDIT_DELAY - time_since_last)
    
    from dependencies import get_bot
    bot = get_bot()
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
        last_edit_time[key] = time.time()
        return True
    except Exception as e:
        print(f"Error editing message: {e}")
        return False

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>❌ Доступ запрещен!</b>")
        return
        
    await message.answer(
        "<b>👑 Админ панель 👑</b>\n\n"
        "<b>⚡ Управление турнирами и лобби</b>\n\n"
        "<blockquote>🎮 Выберите действие из меню ниже!</blockquote>",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data == "admin_active_lobbies")
async def show_active_lobbies(callback: CallbackQuery):
    try:
        # Используем асинхронное получение данных
        lobbies = db.get_all_lobbies()
        
        if not lobbies:
            await callback.message.edit_text("<b>📭 Нет активных лобби!</b>")
            return
            
        await safe_edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            "<b>🎯 Активные лобби 🎯</b>",
            reply_markup=get_lobby_list_keyboard(lobbies)
        )
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "admin_tournaments")
async def show_active_tournaments(callback: CallbackQuery):
    try:
        tournaments = db.get_all_tournaments()
        
        if not tournaments:
            await callback.message.edit_text("<b>📭 Нет активных турниров!</b>")
            return
            
        await safe_edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            "<b>🎯 Активные турниры 🎯</b>",
            reply_markup=get_tournament_list_keyboard(tournaments)
        )
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "admin_create_tournament")
async def create_tournament_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TournamentCreation.waiting_for_players)
    
    await safe_edit_message(
        callback.message.chat.id,
        callback.message.message_id,
        "<b>🎯 Создание турнира 🎯</b>\n\n"
        "<b>👉 Введите количество участников:</b>\n\n"
        "<code>• Должно быть четным числом</code>\n"
        "<code>• Минимум 2 участника</code>\n\n"
        "<blockquote>⚡ Пример: 64</blockquote>"
    )

@router.message(StateFilter(TournamentCreation.waiting_for_players))
async def process_players_count(message: Message, state: FSMContext):
    try:
        players_count = int(message.text)
        
        if players_count < 2:
            await message.answer("<b>❌ Количество участников должно быть не менее 2!</b>\n\n<b>👉 Введите снова:</b>")
            return
            
        if players_count % 2 != 0:
            await message.answer("<b>❌ Количество участников должно быть четным!</b>\n\n<b>👉 Введите снова:</b>")
            return
            
        await state.update_data(players_count=players_count)
        await state.set_state(TournamentCreation.waiting_for_time)
        
        await message.answer(
            "<b>✅ Количество участников принято!</b>\n\n"
            "<b>👉 Теперь введите время регистрации в часах:</b>\n\n"
            "<code>• От 1 до 24 часов</code>\n\n"
            "<blockquote>⚡ Пример: 8</blockquote>"
        )
        
    except ValueError:
        await message.answer("<b>❌ Введите число!</b>\n\n<b>👉 Введите количество участников:</b>")

@router.message(StateFilter(TournamentCreation.waiting_for_time))
async def process_registration_time(message: Message, state: FSMContext):
    try:
        hours = int(message.text)
        
        if hours < 1 or hours > 24:
            await message.answer("<b>❌ Время регистрации должно быть от 1 до 24 часов!</b>\n\n<b>👉 Введите снова:</b>")
            return
            
        data = await state.get_data()
        players_count = data['players_count']
        
        tournament_id = await create_tournament_command(
            message.from_user.id,
            players_count,
            hours
        )
        
        await message.answer(
            f"<b>✅ Турнир создан успешно!</b>\n\n"
            f"<code>🆔 ID: {tournament_id}</code>\n"
            f"<b>👥 Игроков: {players_count}</b>\n"
            f"<b>⏰ Время регистрации: {hours} часов</b>\n\n"
            f"<blockquote>🎯 Турнир опубликован в канале!</blockquote>"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("<b>❌ Введите число!</b>\n\n<b>👉 Введите время регистрации:</b>")
    except Exception as e:
        await message.answer(f"<b>❌ Ошибка при создании турнира:</b>\n\n<code>{str(e)[:100]}...</code>")
        await state.clear()

@router.callback_query(F.data.startswith("lobby_info_"))
async def show_lobby_info(callback: CallbackQuery):
    try:
        lobby_id = callback.data.split("_")[2]
        lobby_data = db.get_lobby(lobby_id)
        
        if not lobby_data:
            await callback.answer("❌ Лобби не найдено!", show_alert=True)
            return
            
        info_text = f"<b>🎮 Лобби {lobby_id}</b>\n\n"
        info_text += f"<code>Статус: {lobby_data['status']}</code>\n"
        info_text += f"<code>Создано: {lobby_data['created_at'][:19].replace('T', ' ')}</code>\n\n"
        
        for username, player_data in lobby_data["players"].items():
            status = "✅" if player_data["connected"] else "❌"
            dice_status = "🎲" if player_data["dice"] else "⏳"
            info_text += f"{status} {dice_status} @{username}\n"
        
        await safe_edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            info_text
        )
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data.startswith("tournament_info_"))
async def show_tournament_info(callback: CallbackQuery):
    try:
        tournament_id = callback.data.split("_")[2]
        tournament_data = db.get_tournament(tournament_id)
        
        if not tournament_data:
            await callback.answer("❌ Турнир не найден!", show_alert=True)
            return
            
        info_text = f"<b>🎯 Турнир {tournament_id}</b>\n\n"
        info_text += f"<code>Статус: {tournament_data['status']}</code>\n"
        info_text += f"<code>Игроков: {len(tournament_data['participants'])}/{tournament_data['max_players']}</code>\n"
        info_text += f"<code>Время: {tournament_data['hours']} часов</code>\n"
        info_text += f"<code>Создан: {tournament_data['created_at'][:19].replace('T', ' ')}</code>\n\n"
        
        if tournament_data["participants"]:
            info_text += f"<b>👥 Участники ({len(tournament_data['participants'])}):</b>\n"
            for i, participant in enumerate(tournament_data["participants"][:10], 1):
                info_text += f"{i}. @{participant}\n"
            if len(tournament_data["participants"]) > 10:
                info_text += f"... и еще {len(tournament_data['participants']) - 10}\n"
        
        await safe_edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            info_text
        )
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "admin_back")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit_message(
        callback.message.chat.id,
        callback.message.message_id,
        "<b>👑 Админ панель 👑</b>\n\n"
        "<b>⚡ Управление турнирами и лобби</b>\n\n"
        "<blockquote>🎮 Выберите действие из меню ниже!</blockquote>",
        reply_markup=get_admin_keyboard()
    )

@router.message(Command("stop"))
async def stop_lobby(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>❌ Доступ запрещен!</b>")
        return
        
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("<b>❌ Использование: /stop <lobby_id></b>")
            return
            
        lobby_id = parts[1]
        lobby_data = db.get_lobby(lobby_id)
        
        if not lobby_data:
            await message.answer("<b>❌ Лобби не найдено!</b>")
            return
            
        db.move_to_history(lobby_id)
        await message.answer(f"<b>✅ Лобби {lobby_id} остановлено и перемещено в историю!</b>")
        
    except Exception as e:
        await message.answer(f"<b>❌ Ошибка: {e}</b>")

@router.message(Command("cleanup"))
async def cleanup_database(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>❌ Доступ запрещен!</b>")
        return
        
    try:
        db.clear_old_data(7)
        await message.answer("<b>✅ База данных очищена от старых записей (старше 7 дней)!</b>")
    except Exception as e:
        await message.answer(f"<b>❌ Ошибка при очистке базы данных: {e}</b>")

@router.message(Command("stats"))
async def show_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>❌ Доступ запрещен!</b>")
        return
        
    try:
        # Используем асинхронный доступ к данным
        active_lobbies = len(db.get_all_lobbies())
        tournaments = db.get_all_tournaments()
        active_tournaments = len(tournaments)
        
        # Считаем историю лобби
        data = db._read_data()
        history_lobbies = len(data.get("history", {}))
        
        stats_text = "<b>📊 Статистика системы</b>\n\n"
        stats_text += f"<code>Активных лобби: {active_lobbies}</code>\n"
        stats_text += f"<code>Завершенных игр: {history_lobbies}</code>\n"
        stats_text += f"<code>Активных турниров: {active_tournaments}</code>\n\n"
        
        # Добавляем статистику по турнирам
        if tournaments:
            registered_players = sum(len(t['participants']) for t in tournaments.values())
            stats_text += f"<code>Зарегистрировано игроков: {registered_players}</code>\n"
        
        stats_text += "<blockquote>⚡ Система работает стабильно</blockquote>"
        
        await message.answer(stats_text)
        
    except Exception as e:
        await message.answer(f"<b>❌ Ошибка при получении статистики: {e}</b>")