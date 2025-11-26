"""
Tools для работы с Google Sheets.
Эти функции используются агентами как инструменты (tools).
"""
import os
from datetime import datetime, timedelta
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials


# Глобальные переменные для кеширования подключения
_client = None
_spreadsheet = None

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def _get_spreadsheet():
    """Получает или создает подключение к Google Sheets"""
    global _client, _spreadsheet
    
    if _spreadsheet is None:
        # Ищем credentials относительно модуля (папка nutrition_tracker)
        module_dir = os.path.dirname(os.path.dirname(__file__))  # nutrition_tracker/
        default_creds = os.path.join(module_dir, 'ai-n8n-test-1-471818-5774c44e8b76.json')
        
        creds_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', default_creds)
        spreadsheet_id = os.getenv('SPREADSHEET_ID', '')
        
        if not spreadsheet_id:
            raise ValueError("SPREADSHEET_ID не задан в переменных окружения")
        
        creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        _client = gspread.authorize(creds)
        _spreadsheet = _client.open_by_key(spreadsheet_id)
    
    return _spreadsheet


def _get_or_create_sheet(name: str, headers: list):
    """Получает или создает лист с заголовками"""
    spreadsheet = _get_spreadsheet()
    
    try:
        sheet = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
        sheet.append_row(headers)
    
    return sheet


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
    Сохраняет прием пищи в Google Sheets.
    
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
        sheet = _get_or_create_sheet('meals', [
            'id', 'user_id', 'date', 'time', 'meal_type',
            'description', 'calories', 'protein', 'fat', 'carbs', 'source'
        ])
        
        # Получаем последний ID
        all_values = sheet.get_all_values()
        last_id = 0
        if len(all_values) > 1:
            for row in all_values[1:]:
                if row[0].isdigit():
                    last_id = max(last_id, int(row[0]))
        
        new_id = last_id + 1
        now = datetime.now()
        
        row = [
            new_id,
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
        ]
        
        sheet.append_row(row)
        
        return {
            "status": "success",
            "message": f"Прием пищи сохранен с ID {new_id}",
            "meal_id": new_id,
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
        sheet = _get_or_create_sheet('meals', [
            'id', 'user_id', 'date', 'time', 'meal_type',
            'description', 'calories', 'protein', 'fat', 'carbs', 'source'
        ])
        
        meals = []
        totals = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        
        all_values = sheet.get_all_values()
        for row in all_values[1:]:
            if len(row) >= 11 and str(row[1]) == str(user_id) and row[2] == date:
                meal = {
                    "id": row[0],
                    "time": row[3],
                    "meal_type": row[4],
                    "description": row[5],
                    "calories": float(row[6]) if row[6] else 0,
                    "protein": float(row[7]) if row[7] else 0,
                    "fat": float(row[8]) if row[8] else 0,
                    "carbs": float(row[9]) if row[9] else 0,
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
        sheet = _get_or_create_sheet('meals', [
            'id', 'user_id', 'date', 'time', 'meal_type',
            'description', 'calories', 'protein', 'fat', 'carbs', 'source'
        ])
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # Группируем по дням
        daily_stats = {}
        
        all_values = sheet.get_all_values()
        for row in all_values[1:]:
            if len(row) >= 11 and str(row[1]) == str(user_id):
                if start_str <= row[2] <= end_str:
                    date = row[2]
                    if date not in daily_stats:
                        daily_stats[date] = {
                            "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "meals_count": 0
                        }
                    daily_stats[date]["calories"] += float(row[6]) if row[6] else 0
                    daily_stats[date]["protein"] += float(row[7]) if row[7] else 0
                    daily_stats[date]["fat"] += float(row[8]) if row[8] else 0
                    daily_stats[date]["carbs"] += float(row[9]) if row[9] else 0
                    daily_stats[date]["meals_count"] += 1
        
        # Округляем значения
        for date in daily_stats:
            for key in ["calories", "protein", "fat", "carbs"]:
                daily_stats[date][key] = round(daily_stats[date][key], 1)
        
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
        sheet = _get_or_create_sheet('users', [
            'user_id', 'name', 'goal_type', 'daily_calories',
            'daily_protein', 'daily_fat', 'daily_carbs',
            'created_at', 'updated_at'
        ])
        
        # Дефолтные цели
        default_goals = {
            "goal_type": "maintenance",
            "daily_calories": 2000,
            "daily_protein": 150,
            "daily_fat": 70,
            "daily_carbs": 200
        }
        
        try:
            cell = sheet.find(str(user_id))
            if cell:
                row = sheet.row_values(cell.row)
                return {
                    "status": "success",
                    "user_id": user_id,
                    "goals": {
                        "goal_type": row[2] if len(row) > 2 else default_goals["goal_type"],
                        "daily_calories": int(row[3]) if len(row) > 3 and row[3] else default_goals["daily_calories"],
                        "daily_protein": int(row[4]) if len(row) > 4 and row[4] else default_goals["daily_protein"],
                        "daily_fat": int(row[5]) if len(row) > 5 and row[5] else default_goals["daily_fat"],
                        "daily_carbs": int(row[6]) if len(row) > 6 and row[6] else default_goals["daily_carbs"]
                    }
                }
        except gspread.exceptions.CellNotFound:
            pass
        
        # Создаем нового пользователя с дефолтными целями
        now = datetime.now().isoformat()
        sheet.append_row([
            user_id, "User", default_goals["goal_type"],
            default_goals["daily_calories"], default_goals["daily_protein"],
            default_goals["daily_fat"], default_goals["daily_carbs"],
            now, now
        ])
        
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
        sheet = _get_or_create_sheet('users', [
            'user_id', 'name', 'goal_type', 'daily_calories',
            'daily_protein', 'daily_fat', 'daily_carbs',
            'created_at', 'updated_at'
        ])
        
        try:
            cell = sheet.find(str(user_id))
            row_num = cell.row
        except gspread.exceptions.CellNotFound:
            # Создаем нового пользователя
            now = datetime.now().isoformat()
            sheet.append_row([
                user_id, "User", goal_type or "maintenance",
                daily_calories or 2000, daily_protein or 150,
                daily_fat or 70, daily_carbs or 200,
                now, now
            ])
            return {
                "status": "success",
                "message": "Создан новый пользователь с указанными целями"
            }
        
        # Обновляем существующего пользователя
        if goal_type:
            sheet.update_cell(row_num, 3, goal_type)
        if daily_calories:
            sheet.update_cell(row_num, 4, daily_calories)
        if daily_protein:
            sheet.update_cell(row_num, 5, daily_protein)
        if daily_fat:
            sheet.update_cell(row_num, 6, daily_fat)
        if daily_carbs:
            sheet.update_cell(row_num, 7, daily_carbs)
        
        sheet.update_cell(row_num, 9, datetime.now().isoformat())
        
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


def delete_last_meal(user_id: str) -> dict:
    """
    Удаляет последний прием пищи пользователя.
    
    Args:
        user_id: Идентификатор пользователя
    
    Returns:
        dict: Статус операции
    """
    try:
        sheet = _get_or_create_sheet('meals', [
            'id', 'user_id', 'date', 'time', 'meal_type',
            'description', 'calories', 'protein', 'fat', 'carbs', 'source'
        ])
        
        all_values = sheet.get_all_values()
        last_row = None
        last_meal_desc = None
        
        for i, row in enumerate(all_values[1:], start=2):
            if len(row) >= 2 and str(row[1]) == str(user_id):
                last_row = i
                last_meal_desc = row[5] if len(row) > 5 else "Неизвестно"
        
        if last_row:
            sheet.delete_rows(last_row)
            return {
                "status": "success",
                "message": f"Удален прием пищи: {last_meal_desc}"
            }
        else:
            return {
                "status": "error",
                "message": "Не найдено записей для удаления"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка удаления: {str(e)}"
        }


def sync_from_sqlite() -> dict:
    """
    Синхронизирует записи из SQLite в Google Sheets.
    Переносит только те записи, которых ещё нет в Sheets.
    
    Returns:
        dict: Статус операции со счётчиками
    """
    import sqlite3
    
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'nutrition.db')
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        stats = {"meals": 0, "users": 0, "weight_log": 0, "memory_bank": 0}
        
        # 1. Синхронизация meals
        sheet = _get_or_create_sheet('meals', [
            'id', 'user_id', 'date', 'time', 'meal_type',
            'description', 'calories', 'protein', 'fat', 'carbs', 'source'
        ])
        
        # Получаем существующие ID из Sheets
        existing_data = sheet.get_all_values()
        existing_ids = set()
        if len(existing_data) > 1:
            for row in existing_data[1:]:
                if row[0] and row[0].isdigit():
                    existing_ids.add(int(row[0]))
        
        # Получаем все записи из SQLite
        cursor.execute('SELECT * FROM meals ORDER BY id')
        meals = cursor.fetchall()
        
        new_rows = []
        for m in meals:
            if m['id'] not in existing_ids:
                new_rows.append([
                    m['id'], m['user_id'], m['date'], m['time'], m['meal_type'],
                    m['description'], m['calories'], m['protein'], m['fat'], 
                    m['carbs'], m['source']
                ])
        
        if new_rows:
            sheet.append_rows(new_rows)
            stats["meals"] = len(new_rows)
        
        # 2. Синхронизация users
        sheet = _get_or_create_sheet('users', [
            'user_id', 'name', 'goal_type', 'daily_calories',
            'daily_protein', 'daily_fat', 'daily_carbs',
            'created_at', 'updated_at'
        ])
        
        existing_data = sheet.get_all_values()
        existing_user_ids = set()
        if len(existing_data) > 1:
            for row in existing_data[1:]:
                if row[0]:
                    existing_user_ids.add(row[0])
        
        cursor.execute('SELECT * FROM users')
        users = cursor.fetchall()
        
        new_rows = []
        for u in users:
            if u['user_id'] not in existing_user_ids:
                new_rows.append([
                    u['user_id'], u['name'], u['goal_type'], u['daily_calories'],
                    u['daily_protein'], u['daily_fat'], u['daily_carbs'],
                    u['created_at'], u['updated_at']
                ])
        
        if new_rows:
            sheet.append_rows(new_rows)
            stats["users"] = len(new_rows)
        
        # 3. Синхронизация weight_log
        sheet = _get_or_create_sheet('weight_log', [
            'id', 'user_id', 'date', 'time', 'weight', 'note', 'created_at'
        ])
        
        existing_data = sheet.get_all_values()
        existing_ids = set()
        if len(existing_data) > 1:
            for row in existing_data[1:]:
                if row[0] and row[0].isdigit():
                    existing_ids.add(int(row[0]))
        
        cursor.execute('SELECT * FROM weight_log ORDER BY id')
        weights = cursor.fetchall()
        
        new_rows = []
        for w in weights:
            if w['id'] not in existing_ids:
                new_rows.append([
                    w['id'], w['user_id'], w['date'], w['time'],
                    w['weight'], w['note'] or '', w['created_at']
                ])
        
        if new_rows:
            sheet.append_rows(new_rows)
            stats["weight_log"] = len(new_rows)
        
        # 4. Синхронизация memory_bank
        sheet = _get_or_create_sheet('memory_bank', [
            'id', 'user_id', 'memory_type', 'content', 'metadata',
            'created_at', 'updated_at'
        ])
        
        existing_data = sheet.get_all_values()
        existing_ids = set()
        if len(existing_data) > 1:
            for row in existing_data[1:]:
                if row[0] and row[0].isdigit():
                    existing_ids.add(int(row[0]))
        
        cursor.execute('SELECT * FROM memory_bank ORDER BY id')
        memories = cursor.fetchall()
        
        new_rows = []
        for m in memories:
            if m['id'] not in existing_ids:
                new_rows.append([
                    m['id'], m['user_id'], m['memory_type'], m['content'],
                    m['metadata'] or '', m['created_at'], m['updated_at']
                ])
        
        if new_rows:
            sheet.append_rows(new_rows)
            stats["memory_bank"] = len(new_rows)
        
        conn.close()
        
        total = sum(stats.values())
        if total == 0:
            return {
                "status": "success",
                "message": "✅ Все данные уже синхронизированы!",
                "stats": stats
            }
        
        return {
            "status": "success",
            "message": f"✅ Синхронизировано: {stats['meals']} приёмов пищи, "
                      f"{stats['users']} пользователей, {stats['weight_log']} записей веса, "
                      f"{stats['memory_bank']} записей памяти",
            "stats": stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Ошибка синхронизации: {str(e)}"
        }