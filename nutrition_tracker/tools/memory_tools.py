"""
Long-term Memory (Memory Bank) для агентов.
Хранит факты о пользователе для персонализации ответов.

Типы памяти:
- preference: предпочтения ("любит острое", "вегетарианец")
- allergy: аллергии и непереносимости ("аллергия на орехи")
- habit: привычки питания ("завтракает в 8 утра")
- fact: прочие факты ("готовит на неделю вперед")
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional
import os

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'nutrition.db')


def _get_connection():
    """Получает подключение к SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_memory_table():
    """Инициализирует таблицу памяти если её нет"""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memory_bank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Индекс для быстрого поиска по пользователю
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_memory_user 
        ON memory_bank(user_id)
    ''')
    
    conn.commit()
    conn.close()


# Инициализируем таблицу при импорте
_init_memory_table()


def store_memory(
    user_id: str,
    memory_type: str,
    content: str,
    metadata: Optional[str] = None
) -> dict:
    """
    Сохраняет факт о пользователе в долгосрочную память.
    
    Args:
        user_id: ID пользователя
        memory_type: Тип памяти (preference/allergy/habit/fact)
        content: Содержимое, например "не ест свинину" или "любит острое"
        metadata: JSON-строка с дополнительными данными (опционально)
    
    Returns:
        dict: Статус операции
    
    Примеры:
        store_memory("123", "preference", "вегетарианец")
        store_memory("123", "allergy", "непереносимость лактозы")
        store_memory("123", "habit", "обычно завтракает в 8 утра")
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        # Проверяем, нет ли уже такой записи
        cursor.execute('''
            SELECT id FROM memory_bank 
            WHERE user_id = ? AND content = ?
        ''', (user_id, content))
        
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return {
                "status": "exists",
                "message": f"Это уже запомнено: {content}"
            }
        
        cursor.execute('''
            INSERT INTO memory_bank (user_id, memory_type, content, metadata)
            VALUES (?, ?, ?, ?)
        ''', (user_id, memory_type, content, metadata or "{}"))
        
        memory_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": f"✅ Запомнил: {content}",
            "memory_id": memory_id,
            "memory_type": memory_type
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка сохранения в память: {str(e)}"
        }


def recall_memories(user_id: str, memory_type: Optional[str] = None) -> dict:
    """
    Извлекает воспоминания о пользователе из долгосрочной памяти.
    
    Args:
        user_id: ID пользователя
        memory_type: Фильтр по типу памяти (опционально).
                     Значения: preference, allergy, habit, fact
    
    Returns:
        dict: Список воспоминаний
    
    Примеры:
        recall_memories("123")  # все воспоминания
        recall_memories("123", "allergy")  # только аллергии
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        if memory_type:
            cursor.execute('''
                SELECT id, memory_type, content, created_at 
                FROM memory_bank
                WHERE user_id = ? AND memory_type = ?
                ORDER BY created_at DESC
            ''', (user_id, memory_type))
        else:
            cursor.execute('''
                SELECT id, memory_type, content, created_at 
                FROM memory_bank
                WHERE user_id = ?
                ORDER BY memory_type, created_at DESC
            ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return {
                "status": "success",
                "message": "Пока ничего не запомнено о пользователе",
                "memories": [],
                "count": 0
            }
        
        memories = []
        for row in rows:
            memories.append({
                "id": row["id"],
                "type": row["memory_type"],
                "content": row["content"],
                "created_at": row["created_at"]
            })
        
        # Группируем для красивого вывода
        by_type = {}
        for m in memories:
            t = m["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(m["content"])
        
        return {
            "status": "success",
            "memories": memories,
            "by_type": by_type,
            "count": len(memories),
            "summary": _format_memory_summary(by_type)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка чтения памяти: {str(e)}"
        }


def _format_memory_summary(by_type: dict) -> str:
    """Форматирует воспоминания в читаемую строку"""
    parts = []
    
    type_labels = {
        "preference": "🍽️ Предпочтения",
        "allergy": "⚠️ Аллергии/непереносимости",
        "habit": "🕐 Привычки",
        "fact": "📝 Факты"
    }
    
    for mem_type, items in by_type.items():
        label = type_labels.get(mem_type, mem_type)
        items_str = ", ".join(items)
        parts.append(f"{label}: {items_str}")
    
    return "\n".join(parts)


def forget_memory(user_id: str, content_substring: str) -> dict:
    """
    Удаляет воспоминание из памяти по части содержимого.
    
    Args:
        user_id: ID пользователя
        content_substring: Часть текста для поиска и удаления
    
    Returns:
        dict: Статус операции
    
    Примеры:
        forget_memory("123", "вегетарианец")  # удалит память о вегетарианстве
        forget_memory("123", "лактоз")  # удалит "непереносимость лактозы"
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        # Сначала находим что будем удалять
        cursor.execute('''
            SELECT id, content FROM memory_bank 
            WHERE user_id = ? AND content LIKE ?
        ''', (user_id, f"%{content_substring}%"))
        
        rows = cursor.fetchall()
        
        if not rows:
            conn.close()
            return {
                "status": "not_found",
                "message": f"Не нашёл воспоминаний содержащих '{content_substring}'"
            }
        
        # Удаляем
        cursor.execute('''
            DELETE FROM memory_bank 
            WHERE user_id = ? AND content LIKE ?
        ''', (user_id, f"%{content_substring}%"))
        
        deleted_count = cursor.rowcount
        deleted_items = [row["content"] for row in rows]
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": f"🗑️ Забыл: {', '.join(deleted_items)}",
            "deleted_count": deleted_count,
            "deleted_items": deleted_items
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка удаления из памяти: {str(e)}"
        }

