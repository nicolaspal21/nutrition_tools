"""
Tools для анализа питания.
Эти функции помогают агентам анализировать еду и давать рекомендации.
"""
from datetime import datetime
import json
from typing import Any


def analyze_food_description(food_description: str) -> dict:
    """
    Анализирует текстовое описание еды и возвращает примерные значения КБЖУ.
    
    Эта функция используется агентом как подсказка для структурирования данных.
    Основной расчет выполняется самим LLM агентом.
    
    Args:
        food_description: Текстовое описание еды, например "2 яйца и тост с авокадо"
    
    Returns:
        dict: Структура для заполнения агентом
    """
    return {
        "status": "needs_analysis",
        "input": food_description,
        "instruction": """
        Проанализируй описание еды и определи:
        1. Какие продукты/блюда упомянуты
        2. Примерные порции (в граммах)
        3. Рассчитай КБЖУ для каждого продукта
        4. Определи тип приема пищи (breakfast/lunch/dinner/snack)
        
        Используй свои знания о калорийности продуктов.
        Если размер порции не указан - используй стандартную порцию.
        """,
        "expected_output": {
            "foods": ["список распознанных продуктов"],
            "total_calories": "число",
            "total_protein": "число в граммах",
            "total_fat": "число в граммах", 
            "total_carbs": "число в граммах",
            "meal_type": "breakfast/lunch/dinner/snack",
            "confidence": "high/medium/low"
        }
    }


def calculate_daily_totals(meals_data_json: str) -> dict:
    """
    Рассчитывает суммарные показатели за день.
    
    Args:
        meals_data_json: JSON строка со списком приемов пищи. 
                         Каждый элемент должен содержать: calories, protein, fat, carbs.
                         Пример: '[{"calories": 300, "protein": 20, "fat": 10, "carbs": 30}]'
    
    Returns:
        dict: Суммарные показатели
    """
    try:
        meals_data = json.loads(meals_data_json) if isinstance(meals_data_json, str) else meals_data_json
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON format for meals_data"}
    
    if not meals_data:
        return {
            "status": "success",
            "totals": {
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0
            },
            "meals_count": 0
        }
    
    totals = {
        "calories": 0,
        "protein": 0,
        "fat": 0,
        "carbs": 0
    }
    
    for meal in meals_data:
        totals["calories"] += meal.get("calories", 0)
        totals["protein"] += meal.get("protein", 0)
        totals["fat"] += meal.get("fat", 0)
        totals["carbs"] += meal.get("carbs", 0)
    
    return {
        "status": "success",
        "totals": {
            "calories": round(totals["calories"], 1),
            "protein": round(totals["protein"], 1),
            "fat": round(totals["fat"], 1),
            "carbs": round(totals["carbs"], 1)
        },
        "meals_count": len(meals_data)
    }


def get_nutrition_advice(
    current_totals: dict,
    user_goals: dict,
    meal_type: str = "next"
) -> dict:
    """
    Генерирует рекомендации по питанию на основе текущего прогресса.
    
    Args:
        current_totals: Текущие суммарные показатели за день
        user_goals: Цели пользователя
        meal_type: Тип следующего приема пищи
    
    Returns:
        dict: Структура с данными для генерации рекомендаций
    """
    goals = user_goals.get("goals", user_goals)
    
    cal_consumed = current_totals.get("calories", 0)
    cal_goal = goals.get("daily_calories", 2000)
    cal_remaining = max(0, cal_goal - cal_consumed)
    cal_percent = (cal_consumed / cal_goal * 100) if cal_goal > 0 else 0
    
    protein_consumed = current_totals.get("protein", 0)
    protein_goal = goals.get("daily_protein", 150)
    protein_remaining = max(0, protein_goal - protein_consumed)
    protein_percent = (protein_consumed / protein_goal * 100) if protein_goal > 0 else 0
    
    # Определяем статус
    if cal_percent > 100:
        status = "exceeded"
        emoji = "🔴"
    elif cal_percent > 80:
        status = "almost_done"
        emoji = "🟡"
    else:
        status = "in_progress"
        emoji = "🟢"
    
    return {
        "status": "success",
        "progress": {
            "calories": {
                "consumed": round(cal_consumed, 1),
                "goal": cal_goal,
                "remaining": round(cal_remaining, 1),
                "percent": round(cal_percent, 1)
            },
            "protein": {
                "consumed": round(protein_consumed, 1),
                "goal": protein_goal,
                "remaining": round(protein_remaining, 1),
                "percent": round(protein_percent, 1)
            }
        },
        "status_emoji": emoji,
        "overall_status": status,
        "goal_type": goals.get("goal_type", "maintenance"),
        "current_time": datetime.now().strftime("%H:%M"),
        "instruction": f"""
        На основе прогресса пользователя дай краткую рекомендацию:
        
        - Прогресс по калориям: {cal_percent:.0f}% ({cal_consumed:.0f}/{cal_goal})
        - Осталось калорий: {cal_remaining:.0f}
        - Прогресс по белку: {protein_percent:.0f}% 
        - Осталось белка: {protein_remaining:.0f}г
        - Цель пользователя: {goals.get("goal_type", "maintenance")}
        - Время: {datetime.now().strftime("%H:%M")}
        
        Дай конкретную рекомендацию что съесть дальше.
        Будь позитивным и мотивирующим.
        """
    }

