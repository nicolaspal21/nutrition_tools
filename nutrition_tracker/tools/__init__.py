"""
Tools для Nutrition Tracker агентов
"""
from .sqlite_tools import (
    save_meal,
    get_today_meals,
    get_meals_by_date,
    get_week_meals,
    get_user_goals,
    update_user_goals,
    edit_meal,
    delete_meal,
    delete_last_meal,
    save_weight,
    get_weight_history,
    get_weight_nutrition_analysis,
    delete_weight,
    save_workout,
    get_workout_history,
    get_today_workout,
    delete_workout,
    export_user_data,
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
    'edit_meal',
    'delete_meal',
    'delete_last_meal',
    'save_weight',
    'get_weight_history',
    'get_weight_nutrition_analysis',
    'delete_weight',
    'save_workout',
    'get_workout_history',
    'get_today_workout',
    'delete_workout',
    'export_user_data',
    'analyze_food_description',
    'calculate_daily_totals',
    'get_nutrition_advice',
]
