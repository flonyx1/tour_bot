# database.py (добавляем недостающие методы)
import json
import os
import uuid
import threading
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from cachetools import TTLCache

class Database:
    def __init__(self, file_path: str = "data/games.json"):
        self.file_path = file_path
        self._ensure_directory_exists()
        self.lock = threading.RLock()
        self.write_lock = threading.Lock()
        self._write_queue = asyncio.Queue()
        self._is_writing = False
        self._cache = TTLCache(maxsize=1000, ttl=300)

    def _ensure_directory_exists(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def _read_data(self) -> Dict:
        with self.lock:
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {"lobbies": {}, "history": {}, "tournaments": {}, "temp_dice": {}}

    async def _write_data_async(self, data: Dict):
        with self.write_lock:
            try:
                temp_file = self.file_path + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                
                if os.path.exists(self.file_path):
                    os.replace(temp_file, self.file_path)
                else:
                    os.rename(temp_file, self.file_path)
                    
            except Exception as e:
                print(f"Error writing database: {e}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)

    def _write_data_sync(self, data: Dict):
        with self.write_lock:
            try:
                temp_file = self.file_path + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                
                if os.path.exists(self.file_path):
                    os.replace(temp_file, self.file_path)
                else:
                    os.rename(temp_file, self.file_path)
                    
            except Exception as e:
                print(f"Error writing database: {e}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)

    async def _background_writer(self):
        while True:
            try:
                data = await self._write_queue.get()
                await self._write_data_async(data)
                self._write_queue.task_done()
            except Exception as e:
                print(f"Background writer error: {e}")

    def _get_cached_data(self) -> Dict:
        cached = self._cache.get('data')
        if cached is None:
            cached = self._read_data()
            self._cache['data'] = cached
        return cached

    def _update_cache(self, new_data: Dict):
        self._cache['data'] = new_data

    # ========== ТУРНИРНЫЕ МЕТОДЫ ==========

    def update_tournament_message_id(self, tournament_id: str, message_id: int):
        """Обновление ID сообщения турнира в канале"""
        data = self._get_cached_data()
        
        if "tournaments" in data and tournament_id in data["tournaments"]:
            data["tournaments"][tournament_id]["channel_message_id"] = message_id
            self._update_cache(data)
            self._write_queue.put_nowait(data)

    def get_tournament_by_lobby(self, lobby_id: str) -> Optional[Dict]:
        """Получение турнира по ID лобби"""
        data = self._get_cached_data()
        lobby = data["lobbies"].get(lobby_id)
        if not lobby or not lobby.get("tournament_id"):
            return None
        
        tournament_id = lobby["tournament_id"]
        return data.get("tournaments", {}).get(tournament_id)

    def get_active_tournaments(self) -> List[Dict]:
        """Получение активных турниров"""
        data = self._get_cached_data()
        active_tournaments = []
        
        for tournament_id, tournament_data in data.get("tournaments", {}).items():
            if tournament_data["status"] in ["registration", "in_progress"]:
                active_tournaments.append(tournament_data)
                
        return active_tournaments

    def update_tournament_round(self, tournament_id: str, round_number: int):
        """Обновление текущего раунда турнира"""
        data = self._get_cached_data()
        
        if "tournaments" in data and tournament_id in data["tournaments"]:
            data["tournaments"][tournament_id]["current_round"] = round_number
            self._update_cache(data)
            self._write_queue.put_nowait(data)
            return True
        return False

    def clear_old_data(self, days: int = 7):
        """Очистка старых данных из истории"""
        data = self._get_cached_data()
        cutoff_date = datetime.now().timestamp() - (days * 24 * 3600)
        
        history_to_keep = {}
        for lobby_id, lobby_data in data.get("history", {}).items():
            created_at = datetime.fromisoformat(lobby_data["created_at"]).timestamp()
            if created_at > cutoff_date:
                history_to_keep[lobby_id] = lobby_data
                
        data["history"] = history_to_keep
        self._update_cache(data)
        self._write_queue.put_nowait(data)

    # ========== МЕТОДЫ ЛОББИ ==========

    def set_lobby_tournament_id(self, lobby_id: str, tournament_id: str):
        """Установка tournament_id для лобби"""
        data = self._get_cached_data()
        
        if lobby_id in data["lobbies"]:
            data["lobbies"][lobby_id]["tournament_id"] = tournament_id
            self._update_cache(data)
            self._write_queue.put_nowait(data)
            return True
        return False

    def get_tournament_id_by_lobby(self, lobby_id: str) -> Optional[str]:
        """Получение ID турнира по ID лобби"""
        data = self._get_cached_data()
        lobby = data["lobbies"].get(lobby_id)
        return lobby.get("tournament_id") if lobby else None

    def create_lobby(self, chat_id: int, admin_id: int, username1: str, username2: str) -> str:
        data = self._get_cached_data()
        lobby_id = str(uuid.uuid4())[:8]
        
        lobby_data = {
            "lobby_id": lobby_id,
            "chat_id": chat_id,
            "admin_id": admin_id,
            "players": {
                username1: {"connected": False, "dice": None},
                username2: {"connected": False, "dice": None}
            },
            "created_at": datetime.now().isoformat(),
            "status": "waiting",
            "winner": None,
            "scores": None,
            "finished": False,
            "tournament_id": None
        }
        
        data["lobbies"][lobby_id] = lobby_data
        self._update_cache(data)
        self._write_queue.put_nowait(data)
        return lobby_id

    def connect_player(self, lobby_id: str, username: str) -> bool:
        data = self._get_cached_data()
        
        if lobby_id in data["lobbies"] and username in data["lobbies"][lobby_id]["players"]:
            data["lobbies"][lobby_id]["players"][username]["connected"] = True
            self._update_cache(data)
            self._write_queue.put_nowait(data)
            return True
        
        return False

    def set_player_dice(self, lobby_id: str, username: str, dice_values: List[int]) -> bool:
        data = self._get_cached_data()
        
        if lobby_id in data["lobbies"] and username in data["lobbies"][lobby_id]["players"]:
            data["lobbies"][lobby_id]["players"][username]["dice"] = dice_values
            self._update_cache(data)
            self._write_queue.put_nowait(data)
            return True
        
        return False

    def get_lobby(self, lobby_id: str) -> Optional[Dict]:
        data = self._get_cached_data()
        return data["lobbies"].get(lobby_id)

    def get_all_lobbies(self) -> Dict:
        data = self._get_cached_data()
        return data["lobbies"]

    def move_to_history(self, lobby_id: str):
        data = self._get_cached_data()
        
        if lobby_id in data["lobbies"]:
            lobby_data = data["lobbies"][lobby_id]
            lobby_data["finished"] = True
            data["history"][lobby_id] = lobby_data
            del data["lobbies"][lobby_id]
            self._update_cache(data)
            self._write_queue.put_nowait(data)

    def delete_lobby(self, lobby_id: str):
        data = self._get_cached_data()
        
        if lobby_id in data["lobbies"]:
            del data["lobbies"][lobby_id]
            self._update_cache(data)
            self._write_queue.put_nowait(data)

    def update_lobby_status(self, lobby_id: str, status: str, winner: str = None, scores: Dict = None):
        data = self._get_cached_data()
        
        if lobby_id in data["lobbies"]:
            data["lobbies"][lobby_id]["status"] = status

            if winner:
                data["lobbies"][lobby_id]["winner"] = winner

            if scores:
                data["lobbies"][lobby_id]["scores"] = scores
                
            if status in ["finished", "draw", "timeout"]:
                data["lobbies"][lobby_id]["finished"] = True

            self._update_cache(data)
            self._write_queue.put_nowait(data)

    # ========== ОСНОВНЫЕ МЕТОДЫ ТУРНИРОВ ==========

    def create_tournament(self, chat_id: int, admin_id: int, max_players: int, hours: int) -> str:
        data = self._get_cached_data()
        tournament_id = str(uuid.uuid4())[:8]
        
        tournament_data = {
            "tournament_id": tournament_id,
            "chat_id": chat_id,
            "admin_id": admin_id,
            "max_players": max_players,
            "hours": hours,
            "status": "registration",
            "participants": [],
            "created_at": datetime.now().isoformat(),
            "lobbies": [],
            "channel_message_id": None,
            "current_round": 1
        }
        
        if "tournaments" not in data:
            data["tournaments"] = {}
            
        data["tournaments"][tournament_id] = tournament_data
        self._update_cache(data)
        self._write_queue.put_nowait(data)
        return tournament_id

    def add_tournament_participant(self, tournament_id: str, username: str) -> bool:
        data = self._get_cached_data()
        
        if "tournaments" in data and tournament_id in data["tournaments"]:
            tournament = data["tournaments"][tournament_id]

            if username not in tournament["participants"] and len(tournament["participants"]) < tournament["max_players"]:
                tournament["participants"].append(username)
                self._update_cache(data)
                self._write_queue.put_nowait(data)
                return True
            
        return False

    def get_tournament(self, tournament_id: str) -> Optional[Dict]:
        data = self._get_cached_data()
        return data.get("tournaments", {}).get(tournament_id)

    def update_tournament_status(self, tournament_id: str, status: str, lobbies: List[str] = None):
        data = self._get_cached_data()
        
        if "tournaments" in data and tournament_id in data["tournaments"]:
            data["tournaments"][tournament_id]["status"] = status

            if lobbies:
                data["tournaments"][tournament_id]["lobbies"] = lobbies

            self._update_cache(data)
            self._write_queue.put_nowait(data)

    def get_all_tournaments(self) -> Dict:
        data = self._get_cached_data()
        return data.get("tournaments", {})

    def delete_tournament(self, tournament_id: str):
        data = self._get_cached_data()
        
        if "tournaments" in data and tournament_id in data["tournaments"]:
            del data["tournaments"][tournament_id]
            self._update_cache(data)
            self._write_queue.put_nowait(data)

    # ========== ВРЕМЕННЫЕ ДАННЫЕ ==========

    def set_temp_dice(self, user_id: str, dice_values: List[int]):
        data = self._get_cached_data()
        data["temp_dice"][user_id] = {
            "dice": dice_values,
            "timestamp": datetime.now().isoformat()
        }
        self._update_cache(data)
        self._write_queue.put_nowait(data)

    def get_temp_dice(self, user_id: str) -> Optional[List[int]]:
        data = self._get_cached_data()
        user_data = data["temp_dice"].get(user_id)
        if user_data:
            return user_data["dice"]
        return None

    def clear_temp_dice(self, user_id: str):
        data = self._get_cached_data()
        if user_id in data["temp_dice"]:
            del data["temp_dice"][user_id]
            self._update_cache(data)
            self._write_queue.put_nowait(data)

    async def start_background_writer(self):
        asyncio.create_task(self._background_writer())

    async def close(self):
        await self._write_queue.join()