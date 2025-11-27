"""
Tools для Nutrition Tracker агентов
"""
from .sheets_tools import (
    save_meal,
    get_today_meals,
    get_meals_by_date,
    get_week_meals,
    get_user_goals,
    update_user_goals,
    delete_last_meal,
)
from .nutrition_tools import (
    analyze_food_description,
    calculate_daily_totals,
    get_nutrition_advice,
)

__all__ = [
    'save_meal',
    'get_today_meals', 
    'get_meals_by_date',
    'get_week_meals',
    'get_user_goals',
    'update_user_goals',
    'delete_last_meal',
    'analyze_food_description',
    'calculate_daily_totals',
    'get_nutrition_advice',
]





