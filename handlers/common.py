from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from config import ADMIN_IDS


router = Router()


@router.message(Command("start"))
async def start_command(message: Message):
    if message.chat.type == "private" and message.from_user.id not in ADMIN_IDS:
        await message.answer("<b>🚫 Бот не работает в личных сообщениях !</b>")
        return
        

    await message.answer("🎮 Добро пожаловать в турнирного бота !")


@router.message(Command("help"))
async def help_command(message: Message):
    if message.chat.type == "private" and message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 Бот не работает в личных сообщениях !")
        return
        

    help_text = """
<b>🎯 Команды бота 🎯</b>

<code>👑 Для админов 👑</code>
/game @username1 @username2 - Создать лобби 
/stop <lobby_id> - Остановить лобби 
/admin - Админ панель 

<code>🎮 Для игроков 🎮</code>
Нажмите «Подключиться» когда создано лобби 
Кидайте кубики когда все подключились 

<blockquote>🎲 Удачи в игре ! 🎲</blockquote>
    """

    await message.answer(help_text)