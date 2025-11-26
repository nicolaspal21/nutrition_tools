"""
Telegram Bot интеграция для Nutrition Tracker
Использует ADK агента для обработки сообщений
"""
import os
import io
import asyncio
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Временно для отладки
)
logger = logging.getLogger(__name__)
# Уменьшим шум от httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

# Глобальные переменные для ADK
_runner = None
_session_service = None


def get_runner():
    """Получает или создает Runner для ADK агента"""
    global _runner, _session_service
    
    if _runner is None:
        from .agent import root_agent
        
        _session_service = InMemorySessionService()
        _runner = Runner(
            agent=root_agent,
            app_name="nutrition_tracker",
            session_service=_session_service,
        )
    
    return _runner


async def run_agent(user_id: str, message: str) -> str:
    """
    Запускает агента для обработки сообщения.
    
    Args:
        user_id: ID пользователя Telegram
        message: Текст сообщения
    
    Returns:
        Ответ агента
    """
    runner = get_runner()
    session_id = f"telegram_{user_id}"
    
    try:
        # Создаем или получаем сессию
        try:
            await _session_service.create_session(
                app_name="nutrition_tracker",
                user_id=user_id,
                session_id=session_id
            )
        except Exception:
            pass  # Сессия уже существует
        
        # Преобразуем сообщение в Content (обязательный формат для ADK)
        content = types.Content(
            role="user",
            parts=[types.Part(text=f"[user_id: {user_id}] {message}")]
        )
        
        # Собираем ответ из async generator
        final_response = ""
        async for event in runner.run_async(
            session_id=session_id,
            user_id=user_id,
            new_message=content,
        ):
            # Логируем все события для отладки
            logger.info(f"Event: {type(event).__name__}, is_final: {event.is_final_response()}, content: {event.content}")
            
            # Извлекаем текст из любого события с контентом
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        # Берём последний текстовый ответ (финальный)
                        if event.is_final_response():
                            final_response = part.text
                        elif not final_response:
                            # Сохраняем промежуточный если финального ещё нет
                            final_response = part.text
        
        return final_response if final_response else "Не удалось получить ответ. Попробуй еще раз."
            
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        return f"Произошла ошибка: {str(e)}"


# ============================================================
# TELEGRAM HANDLERS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_msg = f"""👋 *Привет, {user.first_name}!*

Я NutriTracker — твой AI-помощник по питанию.

*Что я умею:*
📸 Анализировать описание еды
🔢 Считать калории и БЖУ
💡 Давать персональные советы
📊 Показывать статистику

*Как пользоваться:*
• Просто напиши что съел: "2 яйца и тост"
• Спроси статистику: "что я ел сегодня?"
• Установи цели: "хочу похудеть"

*Команды:*
/today — сводка за сегодня
/week — статистика за неделю
/goals — твои цели
/undo — отменить последнюю запись
/help — справка

Давай начнем! 🚀
"""
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """📖 *Справка NutriTracker*

*Добавление еды:*
Просто напиши что съел:
• "Съел борщ и 2 куска хлеба"
• "На завтрак овсянка с бананом"
• "Перекусил яблоком"

*Вопросы о питании:*
• "Что я ел вчера?"
• "Сколько калорий за неделю?"
• "Покажи статистику"

*Управление целями:*
• "Хочу похудеть"
• "Установи калории 1800"
• "Мои цели"

*Команды:*
/start — начало работы
/today — сводка за сегодня
/week — статистика за неделю
/goals — показать цели
/undo — отменить последнее
/help — эта справка

💡 Бот использует AI для анализа. Точность ~90%.
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /today"""
    user_id = str(update.effective_user.id)
    
    status_msg = await update.message.reply_text("🔍 Загружаю данные...")
    response = await run_agent(user_id, "Покажи что я съел сегодня и прогресс к целям")
    try:
        await status_msg.edit_text(response, parse_mode='Markdown')
    except Exception:
        await status_msg.edit_text(response)


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /week"""
    user_id = str(update.effective_user.id)
    
    status_msg = await update.message.reply_text("📊 Собираю статистику за неделю...")
    response = await run_agent(user_id, "Покажи статистику питания за последнюю неделю")
    try:
        await status_msg.edit_text(response, parse_mode='Markdown')
    except Exception:
        await status_msg.edit_text(response)


async def goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /goals"""
    user_id = str(update.effective_user.id)
    
    status_msg = await update.message.reply_text("🎯 Загружаю цели...")
    response = await run_agent(user_id, "Покажи мои текущие цели по питанию")
    try:
        await status_msg.edit_text(response, parse_mode='Markdown')
    except Exception:
        await status_msg.edit_text(response)


async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /undo"""
    user_id = str(update.effective_user.id)
    
    status_msg = await update.message.reply_text("🗑 Удаляю...")
    response = await run_agent(user_id, "Отмени последний прием пищи")
    try:
        await status_msg.edit_text(response, parse_mode='Markdown')
    except Exception:
        await status_msg.edit_text(response)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    # Показываем что обрабатываем
    status_msg = await update.message.reply_text("🔍 Обрабатываю...")
    
    try:
        response = await run_agent(user_id, text)
        # Пробуем отправить с Markdown, если не получится - без форматирования
        try:
            await status_msg.edit_text(response, parse_mode='Markdown')
        except Exception:
            # Markdown не распарсился - отправляем plain text
            await status_msg.edit_text(response)
    except Exception as e:
        logger.error(f"Error handling text: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    user_id = str(update.effective_user.id)
    caption = update.message.caption or "Что это за еда? Проанализируй и посчитай калории."
    
    status_msg = await update.message.reply_text("📸 Анализирую фото...")
    
    try:
        # Получаем фото
        photo = update.message.photo[-1]
        photo_file = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_file.download_as_bytearray()
        
        # TODO: Интеграция с Gemini Vision через ADK
        # Пока используем только подпись
        response = await run_agent(
            user_id, 
            f"Пользователь отправил фото еды с подписью: {caption}. "
            "Проанализируй описание и рассчитай примерные калории."
        )
        
        try:
            await status_msg.edit_text(response, parse_mode='Markdown')
        except Exception:
            await status_msg.edit_text(response)
    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await status_msg.edit_text(f"❌ Ошибка обработки фото: {str(e)}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик голосовых сообщений"""
    user_id = str(update.effective_user.id)
    
    status_msg = await update.message.reply_text("🎤 Обрабатываю голосовое...")
    
    try:
        # Получаем голосовое
        voice = update.message.voice
        voice_file = await context.bot.get_file(voice.file_id)
        voice_bytes = await voice_file.download_as_bytearray()
        
        # TODO: Интеграция с Gemini Audio через ADK
        # Пока просим пользователя написать текстом
        await status_msg.edit_text(
            "🎤 Извини, обработка голосовых сообщений пока в разработке.\n"
            "Пожалуйста, напиши текстом что ты съел."
        )
    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


def create_bot() -> Application:
    """Создает и настраивает Telegram бота"""
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("week", week_command))
    application.add_handler(CommandHandler("goals", goals_command))
    application.add_handler(CommandHandler("undo", undo_command))
    
    # Регистрируем обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    return application


async def post_init(application):
    """Инициализация бота после создания"""
    await application.bot.initialize()


def main():
    """Точка входа для Telegram бота"""
    print("""
    ╔═══════════════════════════════════════════════════╗
    ║         🍎 NUTRITION TRACKER BOT 🍎               ║
    ║                                                   ║
    ║  Built with Google ADK                            ║
    ║  Capstone Project | Agents Intensive              ║
    ╚═══════════════════════════════════════════════════╝
    """)
    
    try:
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
        
        # Создаем приложение с post_init для правильной инициализации
        application = (
            Application.builder()
            .token(token)
            .post_init(post_init)
            .build()
        )
        
        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("today", today_command))
        application.add_handler(CommandHandler("week", week_command))
        application.add_handler(CommandHandler("goals", goals_command))
        application.add_handler(CommandHandler("undo", undo_command))
        
        # Регистрируем обработчики сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.VOICE, handle_voice))
        
        logger.info("🚀 Запуск Telegram бота...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        raise


if __name__ == "__main__":
    main()

