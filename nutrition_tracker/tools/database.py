"""
Database connection module.
Поддерживает Turso (Cloud) через libsql-client и локальный SQLite.
"""
import os
import sqlite3
from typing import Any, List, Optional, Tuple
from dotenv import load_dotenv

# Загружаем переменные окружения сразу при импорте
# .env находится на уровень выше, в папке nutrition_tracker
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

# Для локальной разработки - путь к SQLite файлу
LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'nutrition.db')

# Пробуем импортировать libsql_client
try:
    import libsql_client
    LIBSQL_AVAILABLE = True
except ImportError:
    LIBSQL_AVAILABLE = False

# Флаг: используем Turso или локальный SQLite
_using_turso = False


class DictRow(dict):
    """Row object that supports both dict and index access."""
    def __init__(self, keys, values):
        super().__init__(zip(keys, values))
        self._values = values
    
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class LibSqlCursorWrapper:
    """
    Wrapper for libsql-client to mimic sqlite3 cursor.
    """
    def __init__(self, client):
        self._client = client
        self._rows = []
        self._current_index = 0
        self._last_insert_rowid = None
        self._description = None

    def execute(self, sql: str, params: tuple = ()) -> 'LibSqlCursorWrapper':
        # libsql-client expects params as a list or tuple
        # It supports ? placeholders
        try:
            result_set = self._client.execute(sql, params)
            self._rows = result_set.rows
            self._current_index = 0
            self._last_insert_rowid = result_set.last_insert_rowid
            
            # Form description (name, type_code, display_size, internal_size, precision, scale, null_ok)
            # libsql-client columns might just be names
            if result_set.columns:
                self._description = [(col, None, None, None, None, None, None) for col in result_set.columns]
            else:
                self._description = None
                
            return self
        except Exception as e:
            # Re-raise as sqlite3 error or similar if needed, but for now just let it bubble
            raise e

    def fetchone(self):
        if self._current_index < len(self._rows):
            row = self._rows[self._current_index]
            self._current_index += 1
            # Convert row (which might be a tuple or Row object) to DictRow if description exists
            if self._description:
                keys = [d[0] for d in self._description]
                return DictRow(keys, row)
            return row
        return None

    def fetchall(self):
        remaining = self._rows[self._current_index:]
        self._current_index = len(self._rows)
        
        if self._description:
            keys = [d[0] for d in self._description]
            return [DictRow(keys, row) for row in remaining]
        return remaining

    @property
    def lastrowid(self):
        return self._last_insert_rowid

    @property
    def description(self):
        return self._description

    def close(self):
        pass


class LibSqlConnectionWrapper:
    """
    Wrapper for libsql-client to mimic sqlite3 connection.
    """
    def __init__(self, client):
        self._client = client

    def cursor(self):
        return LibSqlCursorWrapper(self._client)

    def commit(self):
        # libsql-client (HTTP) is auto-commit usually, or transaction managed differently.
        # For simple usage, we can ignore commit or implement transaction logic if needed.
        # The sync client usually executes immediately.
        pass

    def close(self):
        self._client.close()


def get_connection():
    """
    Получает подключение к базе данных.
    Использует ТОЛЬКО Turso (Cloud) через libsql-client.
    
    Returns:
        Connection object (wrapped for Turso)
    
    Raises:
        ValueError: Если не заданы TURSO_URL или TURSO_TOKEN
        ImportError: Если не установлен пакет libsql-client
    """
    global _using_turso
    
    turso_url = os.getenv('TURSO_URL')
    turso_token = os.getenv('TURSO_TOKEN')
    
    if not turso_url or not turso_token:
        raise ValueError("❌ Ошибка конфигурации: Не заданы TURSO_URL или TURSO_TOKEN в .env")
    
    # Принудительно используем HTTPS вместо libsql:// (WebSockets), чтобы избежать ошибки 505
    if turso_url.startswith("libsql://"):
        turso_url = turso_url.replace("libsql://", "https://")
        
    if not LIBSQL_AVAILABLE:
        raise ImportError("❌ Ошибка зависимостей: Пакет 'libsql-client' не установлен. Выполните: pip install libsql-client")

    # Turso (Cloud)
    _using_turso = True
    try:
        # Используем синхронный клиент
        client = libsql_client.create_client_sync(
            url=turso_url,
            auth_token=turso_token
        )
        return LibSqlConnectionWrapper(client)
    except Exception as e:
        raise ConnectionError(f"❌ Не удалось подключиться к Turso: {e}")


def get_db_info() -> str:
    """Возвращает информацию о текущем подключении."""
    return f"Turso Cloud (libsql-client): {os.getenv('TURSO_URL')}"

