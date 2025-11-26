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
    
    # Таблица для записи веса
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weight_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            weight REAL NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, date)
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
        
        # Мягкая защита от дублей: проверяем ТОЧНОЕ совпадение описания за последние 2 минуты
        two_min_ago = (now - timedelta(minutes=2)).strftime('%H:%M')
        cursor.execute('''
            SELECT id, description FROM meals 
            WHERE user_id = ? AND date = ? AND time >= ? AND meal_type = ?
            ORDER BY id DESC LIMIT 1
        ''', (user_id, now.strftime('%Y-%m-%d'), two_min_ago, meal_type))
        
        recent = cursor.fetchone()
        if recent:
            # Проверяем ТОЧНОЕ совпадение описания (игнорируя регистр)
            recent_desc = recent['description'].lower().strip()
            new_desc = description.lower().strip()
            # Только если описания идентичны — это дубль
            if recent_desc == new_desc:
                conn.close()
                return {
                    "status": "duplicate_prevented",
                    "message": f"Эта еда уже записана (ID {recent['id']}): {recent['description']}",
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


# ============================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ВЕСОМ
# ============================================================

def save_weight(
    user_id: str,
    weight: float,
    note: Optional[str] = None
) -> dict:
    """
    Сохраняет вес пользователя. Один замер в день (перезаписывает если уже есть).
    
    Args:
        user_id: Идентификатор пользователя
        weight: Вес в килограммах
        note: Опциональная заметка (например, "после тренировки")
    
    Returns:
        dict: Статус операции
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M')
        
        # Проверяем есть ли уже запись за сегодня
        cursor.execute('''
            SELECT id, weight FROM weight_log WHERE user_id = ? AND date = ?
        ''', (user_id, date_str))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующую запись
            old_weight = existing['weight']
            cursor.execute('''
                UPDATE weight_log 
                SET weight = ?, time = ?, note = ?, created_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND date = ?
            ''', (weight, time_str, note, user_id, date_str))
            conn.commit()
            conn.close()
            
            diff = weight - old_weight
            diff_str = f"+{diff:.1f}" if diff > 0 else f"{diff:.1f}"
            
            return {
                "status": "updated",
                "message": f"Вес обновлён: {old_weight:.1f} → {weight:.1f} кг ({diff_str})",
                "date": date_str,
                "weight": weight,
                "previous_weight": old_weight,
                "change": round(diff, 2)
            }
        
        # Создаем новую запись
        cursor.execute('''
            INSERT INTO weight_log (user_id, date, time, weight, note)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, date_str, time_str, weight, note))
        
        weight_id = cursor.lastrowid
        conn.commit()
        
        # Получаем предыдущий вес для сравнения
        cursor.execute('''
            SELECT weight, date FROM weight_log 
            WHERE user_id = ? AND date < ?
            ORDER BY date DESC LIMIT 1
        ''', (user_id, date_str))
        prev = cursor.fetchone()
        conn.close()
        
        if prev:
            diff = weight - prev['weight']
            diff_str = f"+{diff:.1f}" if diff > 0 else f"{diff:.1f}"
            return {
                "status": "success",
                "message": f"Вес записан: {weight:.1f} кг ({diff_str} с {prev['date']})",
                "weight_id": weight_id,
                "date": date_str,
                "weight": weight,
                "previous_weight": prev['weight'],
                "previous_date": prev['date'],
                "change": round(diff, 2)
            }
        
        return {
            "status": "success",
            "message": f"Вес записан: {weight:.1f} кг (первая запись)",
            "weight_id": weight_id,
            "date": date_str,
            "weight": weight
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка сохранения веса: {str(e)}"
        }


def get_weight_history(user_id: str, days: int = 30) -> dict:
    """
    Получает историю веса за указанный период.
    
    Args:
        user_id: Идентификатор пользователя
        days: Количество дней (по умолчанию 30)
    
    Returns:
        dict: История веса со статистикой
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT date, time, weight, note
            FROM weight_log
            WHERE user_id = ? AND date BETWEEN ? AND ?
            ORDER BY date DESC
        ''', (user_id, start_str, end_str))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return {
                "status": "success",
                "message": "Записей о весе не найдено",
                "entries": [],
                "count": 0
            }
        
        entries = []
        weights = []
        for row in rows:
            entries.append({
                "date": row['date'],
                "time": row['time'],
                "weight": row['weight'],
                "note": row['note']
            })
            weights.append(row['weight'])
        
        # Статистика
        current = weights[0]  # последний замер (сортировка DESC)
        first = weights[-1]   # первый замер в периоде
        total_change = current - first
        min_weight = min(weights)
        max_weight = max(weights)
        avg_weight = sum(weights) / len(weights)
        
        return {
            "status": "success",
            "period": f"{start_str} — {end_str}",
            "entries": entries,
            "count": len(entries),
            "stats": {
                "current_weight": round(current, 1),
                "start_weight": round(first, 1),
                "total_change": round(total_change, 2),
                "min_weight": round(min_weight, 1),
                "max_weight": round(max_weight, 1),
                "avg_weight": round(avg_weight, 1)
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка получения истории веса: {str(e)}"
        }


def get_weight_nutrition_analysis(user_id: str, days: int = 14) -> dict:
    """
    Анализирует связь между весом и питанием.
    Показывает динамику веса вместе с данными о потреблении калорий.
    
    Args:
        user_id: Идентификатор пользователя
        days: Период анализа в днях (по умолчанию 14)
    
    Returns:
        dict: Комбинированный анализ веса и питания
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # Получаем вес
        cursor.execute('''
            SELECT date, weight FROM weight_log
            WHERE user_id = ? AND date BETWEEN ? AND ?
            ORDER BY date
        ''', (user_id, start_str, end_str))
        weight_rows = cursor.fetchall()
        
        # Получаем питание (агрегированное по дням)
        cursor.execute('''
            SELECT date, 
                   SUM(calories) as calories,
                   SUM(protein) as protein,
                   SUM(fat) as fat,
                   SUM(carbs) as carbs
            FROM meals
            WHERE user_id = ? AND date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        ''', (user_id, start_str, end_str))
        nutrition_rows = cursor.fetchall()
        
        # Получаем цели пользователя
        cursor.execute('SELECT daily_calories FROM users WHERE user_id = ?', (user_id,))
        user_row = cursor.fetchone()
        daily_goal = user_row['daily_calories'] if user_row else 2000
        
        conn.close()
        
        # Собираем данные по дням
        weight_data = {row['date']: row['weight'] for row in weight_rows}
        nutrition_data = {row['date']: {
            'calories': row['calories'] or 0,
            'protein': row['protein'] or 0,
            'fat': row['fat'] or 0,
            'carbs': row['carbs'] or 0
        } for row in nutrition_rows}
        
        # Комбинируем данные
        combined = []
        all_dates = sorted(set(weight_data.keys()) | set(nutrition_data.keys()))
        
        for date in all_dates:
            entry = {"date": date}
            if date in weight_data:
                entry["weight"] = weight_data[date]
            if date in nutrition_data:
                entry["calories"] = round(nutrition_data[date]['calories'], 0)
                entry["protein"] = round(nutrition_data[date]['protein'], 1)
                entry["deficit_surplus"] = round(daily_goal - nutrition_data[date]['calories'], 0)
            combined.append(entry)
        
        # Аналитика
        if len(weight_data) >= 2:
            weights = list(weight_data.values())
            first_weight = weights[0]
            last_weight = weights[-1]
            weight_change = last_weight - first_weight
        else:
            weight_change = None
            first_weight = None
            last_weight = None
        
        if nutrition_data:
            calories_list = [d['calories'] for d in nutrition_data.values()]
            avg_calories = sum(calories_list) / len(calories_list)
            avg_deficit = daily_goal - avg_calories
        else:
            avg_calories = None
            avg_deficit = None
        
        # Рассчёт: при дефиците ~7700 ккал теряется ~1 кг
        expected_change = None
        if avg_deficit is not None and len(nutrition_data) > 0:
            total_deficit = avg_deficit * len(nutrition_data)
            expected_change = round(-total_deficit / 7700, 2)  # минус = потеря веса
        
        return {
            "status": "success",
            "period": f"{start_str} — {end_str}",
            "daily_goal": daily_goal,
            "daily_data": combined,
            "summary": {
                "weight_entries": len(weight_data),
                "nutrition_entries": len(nutrition_data),
                "weight_change": round(weight_change, 2) if weight_change is not None else None,
                "start_weight": round(first_weight, 1) if first_weight else None,
                "current_weight": round(last_weight, 1) if last_weight else None,
                "avg_daily_calories": round(avg_calories, 0) if avg_calories else None,
                "avg_daily_deficit": round(avg_deficit, 0) if avg_deficit else None,
                "expected_weight_change": expected_change
            },
            "insight": _generate_weight_insight(weight_change, expected_change, avg_deficit)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка анализа: {str(e)}"
        }


def _generate_weight_insight(weight_change, expected_change, avg_deficit):
    """Генерирует инсайт на основе данных о весе и питании."""
    if weight_change is None or expected_change is None:
        return "Недостаточно данных для анализа. Продолжай записывать вес и питание!"
    
    # Сравниваем фактическое изменение веса с ожидаемым
    diff = weight_change - expected_change
    
    if avg_deficit > 0:  # Дефицит калорий
        if weight_change < 0:
            if abs(diff) < 0.5:
                return "✅ Отлично! Вес снижается в соответствии с дефицитом калорий."
            elif weight_change < expected_change:
                return "🎯 Вес снижается быстрее ожидаемого. Возможно, есть незамеченные источники активности или воды."
            else:
                return "📊 Вес снижается медленнее ожидаемого. Проверь точность записей еды."
        else:
            return "⚠️ При дефиците калорий вес растёт. Возможны: задержка воды, неточный учёт еды, или период адаптации."
    
    elif avg_deficit < 0:  # Профицит калорий
        if weight_change > 0:
            if abs(diff) < 0.5:
                return "💪 Вес набирается в соответствии с профицитом калорий."
            else:
                return "📊 Набор веса отличается от ожидаемого. Нормально при колебаниях воды."
        else:
            return "🔥 Несмотря на профицит, вес не растёт. Возможно, высокий уровень активности."
    
    else:
        return "⚖️ Калории примерно соответствуют поддержанию веса."


def delete_weight(user_id: str, date: Optional[str] = None) -> dict:
    """
    Удаляет запись о весе. Если дата не указана — удаляет последнюю.
    
    Args:
        user_id: Идентификатор пользователя
        date: Дата записи в формате YYYY-MM-DD (опционально)
    
    Returns:
        dict: Статус операции
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        if date:
            cursor.execute('''
                SELECT id, date, weight FROM weight_log 
                WHERE user_id = ? AND date = ?
            ''', (user_id, date))
        else:
            cursor.execute('''
                SELECT id, date, weight FROM weight_log 
                WHERE user_id = ? 
                ORDER BY date DESC LIMIT 1
            ''', (user_id,))
        
        row = cursor.fetchone()
        
        if row:
            cursor.execute('DELETE FROM weight_log WHERE id = ?', (row['id'],))
            conn.commit()
            conn.close()
            return {
                "status": "success",
                "message": f"Удалена запись о весе за {row['date']}: {row['weight']} кг"
            }
        else:
            conn.close()
            return {
                "status": "error",
                "message": "Запись о весе не найдена"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка удаления: {str(e)}"
        }

