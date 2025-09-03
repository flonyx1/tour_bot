from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder



def get_connect_keyboard(lobby_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="➕ Подключиться", 
        callback_data=f"connect_{lobby_id}"
    )

    return builder.as_markup()



def get_tournament_join_keyboard(tournament_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⚡ Участвовать в турнире ⚡", 
        callback_data=f"join_tournament_{tournament_id}"
    )

    return builder.as_markup()



def get_game_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="⚡️ Канал", 
        url="https://t.me/Murderya"
    )

    builder.button(
        text="🎰 Розыгрыши", 
        url="https://t.me/MurderBog_bot"
    )
    
    builder.adjust(1) 

    return builder.as_markup()



def get_game_result_chat() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="💬 Перейти", 
        url="https://t.me/+JH2ZGpyw1JNmMjky"
    )
    
    builder.adjust(1)
    return builder.as_markup()




def get_admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text="📊 Активные лобби 📊", callback_data="admin_active_lobbies")
    builder.button(text="🎯 Активные турниры 🎯", callback_data="admin_tournaments")
    builder.button(text="➕ Создать турнир ➕", callback_data="admin_create_tournament")

    builder.adjust(1)

    return builder.as_markup()



def get_lobby_list_keyboard(lobbies: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for lobby_id, lobby_data in lobbies.items():
        status_emoji = "🟢" if lobby_data['status'] == 'playing' else "🟡" if lobby_data['status'] == 'waiting' else "🔴"
        builder.button(
            text=f"{status_emoji} Лобби {lobby_id} - {lobby_data['status']} {status_emoji}", 
            callback_data=f"lobby_info_{lobby_id}"
        )


    builder.button(text="⬅️ Назад в меню ⬅️", callback_data="admin_back")

    builder.adjust(1)


    return builder.as_markup()



def get_tournament_list_keyboard(tournaments: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for tournament_id, tournament_data in tournaments.items():
        status_emoji = "🟢" if tournament_data['status'] == 'started' else "🟡" if tournament_data['status'] == 'registration' else "🔴"
        builder.button(
            text=f"{status_emoji} Турнир {tournament_id} - {tournament_data['status']} {status_emoji}", 
            callback_data=f"tournament_info_{tournament_id}"
        )

    builder.button(text="⬅️ Назад", callback_data="admin_back")

    builder.adjust(1)

    return builder.as_markup()