"""
Search Tools - Интеграция Google Search через отдельный агент

Поскольку Google Search tool нельзя комбинировать с function calling в Gemini 2.0,
мы используем отдельный search_agent который вызывается через этот tool.
"""
import asyncio
import logging
from typing import Optional

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.adk.models.google_llm import Gemini
from google.genai import types

logger = logging.getLogger(__name__)

# Конфигурация retry
retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)

# Отдельный агент ТОЛЬКО для поиска (без других tools)
_search_agent = Agent(
    name="search_agent",
    model=Gemini(model="gemini-2.0-flash", retry_options=retry_config),
    description="Ищет информацию о калорийности продуктов и питании в интернете через Google.",
    instruction="""Ты помощник по поиску информации о питании.

Твоя задача:
1. Искать калорийность и КБЖУ продуктов
2. Находить информацию о пользе/вреде продуктов
3. Искать рецепты и их калорийность

Формат поиска:
- Для калорийности: "[продукт] калорийность КБЖУ на 100г"
- Для рецептов: "[блюдо] рецепт калории"

После поиска дай КРАТКИЙ ответ с найденными данными:
- Калории на 100г
- Белки, жиры, углеводы
- Источник (если важно)

Не давай длинных объяснений, только факты.
""",
    tools=[google_search],  # ТОЛЬКО google_search!
)

# Session service для search_agent (синглтон)
_search_session_service: Optional[InMemorySessionService] = None
_search_runner: Optional[Runner] = None


def _get_search_runner() -> Runner:
    """Получает или создает Runner для search_agent"""
    global _search_session_service, _search_runner
    
    if _search_runner is None:
        _search_session_service = InMemorySessionService()
        _search_runner = Runner(
            agent=_search_agent,
            app_name="nutrition_search",
            session_service=_search_session_service,
        )
    
    return _search_runner


async def _run_search_async(query: str) -> str:
    """Внутренняя async функция для вызова search_agent"""
    runner = _get_search_runner()
    session_id = "search_session"
    
    try:
        # Создаем сессию (или используем существующую)
        try:
            await _search_session_service.create_session(
                app_name="nutrition_search",
                user_id="system",
                session_id=session_id
            )
        except Exception:
            pass  # Сессия уже существует
        
        # Запрос к search_agent
        content = types.Content(
            role="user",
            parts=[types.Part(text=query)]
        )
        
        final_response = ""
        async for event in runner.run_async(
            session_id=session_id,
            user_id="system",
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        if event.is_final_response():
                            final_response = part.text
                        elif not final_response:
                            final_response = part.text
        
        return final_response if final_response else "Информация не найдена"
        
    except Exception as e:
        logger.error(f"Error in search_agent: {e}")
        return f"Ошибка поиска: {str(e)}"


def search_nutrition_info(query: str) -> dict:
    """
    Ищет информацию о калорийности и КБЖУ продуктов в интернете.
    
    Используй этот инструмент когда:
    - Нужно узнать калорийность незнакомого продукта
    - Пользователь спрашивает о пользе/вреде продукта
    - Нужно найти КБЖУ экзотического блюда
    - Не уверен в калорийности
    
    Args:
        query: Поисковый запрос (например: "калорийность авокадо на 100г")
    
    Returns:
        dict со статусом и найденной информацией
    """
    try:
        # Запускаем async функцию в event loop
        try:
            loop = asyncio.get_running_loop()
            # Если уже есть running loop - создаем task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _run_search_async(query))
                result = future.result(timeout=30)
        except RuntimeError:
            # Нет running loop - запускаем напрямую
            result = asyncio.run(_run_search_async(query))
        
        return {
            "status": "success",
            "query": query,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {
            "status": "error",
            "query": query,
            "error": str(e)
        }

