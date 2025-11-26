"""
Tools для работы с SQLite (временная замена Google Sheets).
"""
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'nutrition.db')

def _get_connection():
    """Получает подключение к SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    """Инициализирует таблицы если их нет"""
    conn = _get_connection()
    cursor = conn.cursor()
    
    # Таблица приемов пищи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            meal_type TEXT DEFAULT 'snack',
            description TEXT NOT NULL,
            calories REAL DEFAULT 0,
            protein REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            source TEXT DEFAULT 'text',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица пользователей и их целей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT DEFAULT 'User',
            goal_type TEXT DEFAULT 'maintenance',
            daily_calories INTEGER DEFAULT 2000,
            daily_protein INTEGER DEFAULT 150,
            daily_fat INTEGER DEFAULT 70,
            daily_carbs INTEGER DEFAULT 200,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Инициализируем БД при импорте
_init_db()


def save_meal(
    user_id: str,
    description: str,
    calories: float,
    protein: float,
    fat: float,
    carbs: float,
    meal_type: str = "snack",
    source: str = "text"
) -> dict:
    """
    Сохраняет прием пищи в SQLite.
    
    Args:
        user_id: Идентификатор пользователя
        description: Описание еды (что съел)
        calories: Количество калорий
        protein: Количество белка в граммах
        fat: Количество жиров в граммах
        carbs: Количество углеводов в граммах
        meal_type: Тип приема пищи (breakfast/lunch/dinner/snack)
        source: Источник данных (text/photo/voice)
    
    Returns:
        dict: Статус операции и ID записи
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        now = datetime.now()
        
        # Защита от дублей: проверяем не было ли похожей записи в последние 5 минут
        five_min_ago = (now - timedelta(minutes=5)).strftime('%H:%M')
        cursor.execute('''
            SELECT id, description, calories FROM meals 
            WHERE user_id = ? AND date = ? AND time >= ?
            ORDER BY id DESC LIMIT 1
        ''', (user_id, now.strftime('%Y-%m-%d'), five_min_ago))
        
        recent = cursor.fetchone()
        if recent:
            # Проверяем похожесть описания (содержит ключевые слова)
            recent_desc = recent['description'].lower()
            new_desc = description.lower()
            # Если описания очень похожи - это дубль
            if (recent_desc in new_desc or new_desc in recent_desc or 
                abs(recent['calories'] - calories) < 50):  # или калории почти одинаковые
                conn.close()
                return {
                    "status": "duplicate_prevented",
                    "message": f"Похожий прием пищи уже записан (ID {recent['id']}): {recent['description']}. Если это другая еда, уточни описание.",
                    "existing_meal_id": recent['id']
                }
        
        cursor.execute('''
            INSERT INTO meals (user_id, date, time, meal_type, description, calories, protein, fat, carbs, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            now.strftime('%Y-%m-%d'),
            now.strftime('%H:%M'),
            meal_type,
            description,
            round(calories, 1),
            round(protein, 1),
            round(fat, 1),
            round(carbs, 1),
            source
        ))
        
        meal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": f"Прием пищи сохранен с ID {meal_id}",
            "meal_id": meal_id,
            "saved_data": {
                "description": description,
                "calories": calories,
                "protein": protein,
                "fat": fat,
                "carbs": carbs
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка сохранения: {str(e)}"
        }


def get_today_meals(user_id: str) -> dict:
    """
    Получает все приемы пищи пользователя за сегодня.
    
    Args:
        user_id: Идентификатор пользователя
    
    Returns:
        dict: Список приемов пищи и суммарные показатели
    """
    today = datetime.now().strftime('%Y-%m-%d')
    return get_meals_by_date(user_id, today)


def get_meals_by_date(user_id: str, date: str) -> dict:
    """
    Получает приемы пищи за конкретную дату.
    
    Args:
        user_id: Идентификатор пользователя
        date: Дата в формате YYYY-MM-DD
    
    Returns:
        dict: Список приемов пищи и статистика
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, time, meal_type, description, calories, protein, fat, carbs
            FROM meals
            WHERE user_id = ? AND date = ?
            ORDER BY time
        ''', (user_id, date))
        
        rows = cursor.fetchall()
        conn.close()
        
        meals = []
        totals = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        
        for row in rows:
            meal = {
                "id": row['id'],
                "time": row['time'],
                "meal_type": row['meal_type'],
                "description": row['description'],
                "calories": row['calories'] or 0,
                "protein": row['protein'] or 0,
                "fat": row['fat'] or 0,
                "carbs": row['carbs'] or 0,
            }
            meals.append(meal)
            totals["calories"] += meal["calories"]
            totals["protein"] += meal["protein"]
            totals["fat"] += meal["fat"]
            totals["carbs"] += meal["carbs"]
        
        return {
            "status": "success",
            "date": date,
            "meals": meals,
            "meals_count": len(meals),
            "totals": {
                "calories": round(totals["calories"], 1),
                "protein": round(totals["protein"], 1),
                "fat": round(totals["fat"], 1),
                "carbs": round(totals["carbs"], 1)
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка получения данных: {str(e)}"
        }


def get_week_meals(user_id: str) -> dict:
    """
    Получает статистику питания за последнюю неделю.
    
    Args:
        user_id: Идентификатор пользователя
    
    Returns:
        dict: Статистика по дням за неделю
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT date, 
                   SUM(calories) as calories,
                   SUM(protein) as protein,
                   SUM(fat) as fat,
                   SUM(carbs) as carbs,
                   COUNT(*) as meals_count
            FROM meals
            WHERE user_id = ? AND date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        ''', (user_id, start_str, end_str))
        
        rows = cursor.fetchall()
        conn.close()
        
        daily_stats = {}
        for row in rows:
            daily_stats[row['date']] = {
                "calories": round(row['calories'] or 0, 1),
                "protein": round(row['protein'] or 0, 1),
                "fat": round(row['fat'] or 0, 1),
                "carbs": round(row['carbs'] or 0, 1),
                "meals_count": row['meals_count']
            }
        
        # Средние значения
        if daily_stats:
            avg_calories = sum(d["calories"] for d in daily_stats.values()) / len(daily_stats)
            avg_protein = sum(d["protein"] for d in daily_stats.values()) / len(daily_stats)
        else:
            avg_calories = 0
            avg_protein = 0
        
        return {
            "status": "success",
            "period": f"{start_str} - {end_str}",
            "days_with_data": len(daily_stats),
            "daily_breakdown": daily_stats,
            "averages": {
                "calories": round(avg_calories, 1),
                "protein": round(avg_protein, 1)
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка получения статистики: {str(e)}"
        }


def get_user_goals(user_id: str) -> dict:
    """
    Получает цели пользователя по питанию.
    
    Args:
        user_id: Идентификатор пользователя
    
    Returns:
        dict: Цели пользователя (калории, БЖУ)
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
        if row:
            conn.close()
            return {
                "status": "success",
                "user_id": user_id,
                "goals": {
                    "goal_type": row['goal_type'],
                    "daily_calories": row['daily_calories'],
                    "daily_protein": row['daily_protein'],
                    "daily_fat": row['daily_fat'],
                    "daily_carbs": row['daily_carbs']
                }
            }
        
        # Создаем нового пользователя с дефолтными целями
        default_goals = {
            "goal_type": "maintenance",
            "daily_calories": 2000,
            "daily_protein": 150,
            "daily_fat": 70,
            "daily_carbs": 200
        }
        
        cursor.execute('''
            INSERT INTO users (user_id, goal_type, daily_calories, daily_protein, daily_fat, daily_carbs)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, default_goals["goal_type"], default_goals["daily_calories"],
              default_goals["daily_protein"], default_goals["daily_fat"], default_goals["daily_carbs"]))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "user_id": user_id,
            "goals": default_goals,
            "note": "Созданы цели по умолчанию"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка получения целей: {str(e)}"
        }


def update_user_goals(
    user_id: str,
    goal_type: Optional[str] = None,
    daily_calories: Optional[int] = None,
    daily_protein: Optional[int] = None,
    daily_fat: Optional[int] = None,
    daily_carbs: Optional[int] = None
) -> dict:
    """
    Обновляет цели пользователя.
    
    Args:
        user_id: Идентификатор пользователя
        goal_type: Тип цели (weight_loss/muscle_gain/maintenance)
        daily_calories: Дневная норма калорий
        daily_protein: Дневная норма белка
        daily_fat: Дневная норма жиров
        daily_carbs: Дневная норма углеводов
    
    Returns:
        dict: Статус операции и обновленные цели
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        # Проверяем есть ли пользователь
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
        if not row:
            # Создаем нового пользователя
            cursor.execute('''
                INSERT INTO users (user_id, goal_type, daily_calories, daily_protein, daily_fat, daily_carbs)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                goal_type or "maintenance",
                daily_calories or 2000,
                daily_protein or 150,
                daily_fat or 70,
                daily_carbs or 200
            ))
            conn.commit()
            conn.close()
            return {
                "status": "success",
                "message": "Создан новый пользователь с указанными целями"
            }
        
        # Обновляем существующего пользователя
        updates = []
        params = []
        
        if goal_type:
            updates.append("goal_type = ?")
            params.append(goal_type)
        if daily_calories:
            updates.append("daily_calories = ?")
            params.append(daily_calories)
        if daily_protein:
            updates.append("daily_protein = ?")
            params.append(daily_protein)
        if daily_fat:
            updates.append("daily_fat = ?")
            params.append(daily_fat)
        if daily_carbs:
            updates.append("daily_carbs = ?")
            params.append(daily_carbs)
        
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(user_id)
            
            cursor.execute(f'''
                UPDATE users SET {", ".join(updates)} WHERE user_id = ?
            ''', params)
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": "Цели обновлены",
            "updated_goals": {
                "goal_type": goal_type,
                "daily_calories": daily_calories,
                "daily_protein": daily_protein,
                "daily_fat": daily_fat,
                "daily_carbs": daily_carbs
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка обновления целей: {str(e)}"
        }


def edit_meal(
    user_id: str,
    meal_id: Optional[int] = None,
    description: Optional[str] = None,
    calories: Optional[float] = None,
    protein: Optional[float] = None,
    fat: Optional[float] = None,
    carbs: Optional[float] = None
) -> dict:
    """
    Редактирует прием пищи. Если meal_id не указан — редактирует последний.
    
    Args:
        user_id: Идентификатор пользователя
        meal_id: ID записи (опционально, если не указан — последняя)
        description: Новое описание (опционально)
        calories: Новые калории (опционально)
        protein: Новый белок (опционально)
        fat: Новые жиры (опционально)
        carbs: Новые углеводы (опционально)
    
    Returns:
        dict: Статус операции
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        # Если ID не указан — берём последнюю запись пользователя
        if meal_id is None:
            cursor.execute('''
                SELECT id FROM meals WHERE user_id = ? ORDER BY id DESC LIMIT 1
            ''', (user_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return {"status": "error", "message": "Нет записей для редактирования"}
            meal_id = row['id']
        
        # Проверяем что запись принадлежит пользователю
        cursor.execute('SELECT * FROM meals WHERE id = ? AND user_id = ?', (meal_id, user_id))
        meal = cursor.fetchone()
        if not meal:
            conn.close()
            return {"status": "error", "message": f"Запись #{meal_id} не найдена"}
        
        # Собираем обновления
        updates = []
        params = []
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if calories is not None:
            updates.append("calories = ?")
            params.append(round(calories, 1))
        if protein is not None:
            updates.append("protein = ?")
            params.append(round(protein, 1))
        if fat is not None:
            updates.append("fat = ?")
            params.append(round(fat, 1))
        if carbs is not None:
            updates.append("carbs = ?")
            params.append(round(carbs, 1))
        
        if not updates:
            conn.close()
            return {"status": "error", "message": "Не указано что изменить"}
        
        params.append(meal_id)
        cursor.execute(f'UPDATE meals SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()
        
        # Получаем обновленную запись
        cursor.execute('SELECT * FROM meals WHERE id = ?', (meal_id,))
        updated = cursor.fetchone()
        conn.close()
        
        return {
            "status": "success",
            "message": f"Запись #{meal_id} обновлена",
            "updated_meal": {
                "id": updated['id'],
                "description": updated['description'],
                "calories": updated['calories'],
                "protein": updated['protein'],
                "fat": updated['fat'],
                "carbs": updated['carbs']
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Ошибка редактирования: {str(e)}"}


def delete_meal(user_id: str, meal_id: Optional[int] = None) -> dict:
    """
    Удаляет прием пищи. Если meal_id не указан — удаляет последний.
    
    Args:
        user_id: Идентификатор пользователя
        meal_id: ID записи (опционально, если не указан — последняя)
    
    Returns:
        dict: Статус операции
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        # Если ID не указан — берём последнюю запись
        if meal_id is None:
            cursor.execute('''
                SELECT id, description FROM meals 
                WHERE user_id = ? 
                ORDER BY id DESC LIMIT 1
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT id, description FROM meals 
                WHERE id = ? AND user_id = ?
            ''', (meal_id, user_id))
        
        row = cursor.fetchone()
        
        if row:
            found_id = row['id']
            description = row['description']
            
            cursor.execute('DELETE FROM meals WHERE id = ?', (found_id,))
            conn.commit()
            conn.close()
            
            return {
                "status": "success",
                "message": f"Удалена запись #{found_id}: {description}"
            }
        else:
            conn.close()
            if meal_id:
                return {"status": "error", "message": f"Запись #{meal_id} не найдена"}
            return {"status": "error", "message": "Нет записей для удаления"}
    except Exception as e:
        return {"status": "error", "message": f"Ошибка удаления: {str(e)}"}


# Алиас для обратной совместимости
def delete_last_meal(user_id: str) -> dict:
    """Удаляет последний прием пищи (алиас для delete_meal)."""
    return delete_meal(user_id)

