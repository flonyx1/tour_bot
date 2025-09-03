def number_to_emoji(number: int) -> str:
    emoji_map = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }

    return ''.join(emoji_map[digit] for digit in str(number))



def format_game_result(lobby_data: dict) -> str:
    players = list(lobby_data["players"].keys())
    
    result = f"<b>🎯 РЕЗУЛЬТАТЫ ИГРЫ</b>\n\n"
    result += f"<code>🆔 Лобби: {lobby_data['lobby_id']}</code>\n\n"
    
    result += "<b>⚔️ УЧАСТНИКИ:</b>\n"

    for i, player in enumerate(players, 1):
        dice_values = lobby_data["players"][player]["dice"]

        if dice_values and len(dice_values) == 2:
            total = sum(dice_values)
            result += f"👤 Игрок №{i}: @{player}\n"
            result += f"🎲 Броски: {number_to_emoji(dice_values[0])} + {number_to_emoji(dice_values[1])}\n"
            result += f"📊 Сумма: {number_to_emoji(total)}\n\n"

        else:
            result += f"👤 Игрок №{i}: @{player}\n"
            result += f"🎲 Броски: не брошены\n"
            result += f"📊 Сумма: 0️⃣\n\n"
    

    result += "<b>🏆 ИТОГИ ИГРЫ:</b>\n\n"

    if lobby_data.get("status") == "timeout":
        if lobby_data.get("winner"):
            result += f"⏰ Результат по таймауту !\n"
            result += f"<b>🏅 Победитель: @{lobby_data['winner']} 🏅</b>\n"

        else:
            result += f"⏰ Оба игрока проиграли по таймауту ! ❌\n"

    elif lobby_data.get("winner"):
        result += f"<b>✨ Победитель: @{lobby_data['winner']} ✨</b>\n"
        result += f"🎉 Поздравляем с победой ! 🎉\n"

    else:
        result += "🤝 Ничья ! 🤝\n"
    

    result += f"\n<code>🕐 Создано: {lobby_data['created_at'][:19].replace('T', ' ')}</code>"
    result += f"\n\n<blockquote>⚡ Спасибо за игру ! ⚡</blockquote>"

    return result