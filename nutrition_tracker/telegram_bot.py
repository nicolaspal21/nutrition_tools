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
from google.genai import types

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO)
)
logger = logging.getLogger(__name__)
# Уменьшим шум от httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

# Глобальные переменные для ADK
_runner = None
_session_service = None

# Кэш для сбора альбомов (media groups)
_media_groups: dict[str, list[bytes]] = {}
_media_group_captions: dict[str, str] = {}
_media_group_updates: dict[str, Update] = {}
_media_group_user_ids: dict[str, str] = {}


def _redact(text: str) -> str:
    """
    Маскирует секреты в строке, чтобы они не утекали в логи:
    - пароль в connection string (postgres://user:PASS@host)
    - authToken=... в query-параметрах
    """
    import re
    s = str(text)
    s = re.sub(r'(://[^:/@\s]+:)[^@\s]+(@)', r'\1<redacted>\2', s)
    s = re.sub(r'((?:authToken|password|token)=)[^&\s\'"]+', r'\1<redacted>', s, flags=re.IGNORECASE)
    return s


def _build_session_db_url():
    """
    Готовит async-URL и connect_args для DatabaseSessionService на основе
    SESSION_DB_URL (например, строка подключения Neon Postgres).

    ADK использует create_async_engine, поэтому нужен async-драйвер:
    схема нормализуется к postgresql+asyncpg://. Параметры sslmode/channel_binding
    из строки Neon не понимает asyncpg — убираем их и включаем ssl через connect_args.

    Returns:
        (url, connect_args) или (None, None), если SESSION_DB_URL не задан.
    """
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

    raw = os.getenv('SESSION_DB_URL')
    if not raw:
        return None, None

    parts = urlsplit(raw)

    # Нормализуем схему к async-драйверу
    scheme = parts.scheme
    if scheme in ('postgres', 'postgresql'):
        scheme = 'postgresql+asyncpg'

    connect_args = {}
    # asyncpg не понимает libpq-параметры sslmode/channel_binding — выносим в ssl
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop('sslmode', None)
    query.pop('channel_binding', None)
    if sslmode and sslmode != 'disable':
        connect_args['ssl'] = True

    url = urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return url, connect_args


def _create_session_service():
    """
    Создаёт персистентный DatabaseSessionService (Postgres, напр. Neon), чтобы
    контекст диалога переживал рестарты/масштабирование Cloud Run.
    При любой ошибке или отсутствии SESSION_DB_URL — fallback на InMemory.
    """
    from google.adk.sessions import InMemorySessionService

    url, connect_args = _build_session_db_url()
    if url:
        try:
            from google.adk.sessions import DatabaseSessionService
            service = DatabaseSessionService(db_url=url, connect_args=connect_args)
            logger.info("🗄️ Using DatabaseSessionService (Postgres) — sessions are persistent")
            return service
        except Exception as e:
            # ВАЖНО: текст ошибки может содержать URL с паролем — редактируем
            logger.warning(
                f"⚠️ Failed to init DatabaseSessionService "
                f"[{type(e).__name__}: {_redact(e)}]; "
                f"falling back to InMemory (sessions lost on restart)"
            )
    else:
        logger.warning(
            "⚠️ SESSION_DB_URL not set; using InMemory sessions (lost on restart)"
        )

    return InMemorySessionService()


def get_runner():
    """Получает или создает Runner для ADK агента"""
    global _runner, _session_service

    if _runner is None:
        from .agent import root_agent
        from .tools.memory_tools import init_memory_db

        # Инициализируем БД памяти (безопасно)
        init_memory_db()

        _session_service = _create_session_service()

        _runner = Runner(
            agent=root_agent,
            app_name="nutrition_tracker",
            session_service=_session_service,
        )

    return _runner


async def run_agent(user_id: str, message: str) -> str:
    """
    Запускает агента для обработки текстового сообщения.
    
    Args:
        user_id: ID пользователя Telegram
        message: Текст сообщения
    
    Returns:
        Ответ агента
    """
    return await run_agent_multimodal(user_id, message)


async def run_agent_multimodal(
    user_id: str, 
    message: str,
    media_bytes: bytes = None,
    media_mime_type: str = None
) -> str:
    """
    Запускает агента для обработки мультимодального сообщения (текст + фото/аудио).
    
    Args:
        user_id: ID пользователя Telegram
        message: Текст сообщения
        media_bytes: Байты медиафайла (фото или аудио)
        media_mime_type: MIME тип медиа (image/jpeg, audio/ogg и т.д.)
    
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
        
        # Формируем parts для Content
        parts = [types.Part(text=f"[user_id: {user_id}] {message}")]
        
        # Добавляем медиа если есть
        if media_bytes and media_mime_type:
            parts.append(
                types.Part(
                    inline_data=types.Blob(
                        mime_type=media_mime_type,
                        data=bytes(media_bytes)
                    )
                )
            )
        
        content = types.Content(role="user", parts=parts)
        
        # Собираем ответ из async generator
        final_response = ""
        async for event in runner.run_async(
            session_id=session_id,
            user_id=user_id,
            new_message=content,
        ):
            # Логируем все события для отладки
            logger.debug(f"Event: {type(event).__name__}, is_final: {event.is_final_response()}")
            
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
📸 Анализировать *фото еды* — просто сфоткай блюдо!
🎤 Понимать *голосовые* — расскажи что съел
✍️ Анализировать текст — напиши описание
⚖️ Отслеживать *вес* и динамику
🏃 Записывать *тренировки*
📦 Экспортировать данные в *CSV*
📊 Показывать статистику

*Как пользоваться:*
• 📸 Отправь фото еды
• ✍️ Напиши: "съел борщ и хлеб"
• ⚖️ Напиши: "вес 75.5"
• 🏃 Напиши: "тренировка 400 ккал"
• ❓ Спроси: "что я ел сегодня?"

*Команды:*
/today — сводка за сегодня
/week — статистика за неделю
/goals — твои цели
/export — скачать данные в CSV
/help — справка

Давай начнем! 🚀
"""
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """📖 *Справка NutriTracker*

*Добавление еды (3 способа):*

📸 *Фото* — сфоткай блюдо (можно несколько фото сразу!)

🎤 *Голосовое* — запиши что съел голосом

✍️ *Текст* — напиши описание:
• "Съел борщ и 2 куска хлеба"
• "На завтрак овсянка с бананом"

⚖️ *Вес* — напиши: "вес 75.5" или "взвесился 74 кг"

🏃 *Тренировки* — напиши: "тренировка 400 ккал" или "пробежка 30 минут"

*Вопросы:*
• "Что я ел сегодня?"
• "Мой вес?" / "история веса"
• "Мои тренировки"

*Команды:*
/today — сводка за сегодня
/week — статистика за неделю
/goals — показать цели
/undo — отменить последнее
/export — скачать данные в CSV
/help — эта справка

*Примеры /export:*
• `/export` — всё за 30 дней
• `/export 7` — за неделю
• `/export 30 meals` — только еда за месяц
• `/export 14 weight workouts` — вес и тренировки

💡 Бот использует Gemini AI для анализа фото, аудио и текста.
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


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /export — экспорт данных в CSV"""
    user_id = str(update.effective_user.id)
    
    # Парсим аргументы: /export [days] [типы]
    # Примеры: /export, /export 7, /export 30 meals, /export 14 weight workouts
    args = context.args if context.args else []
    
    days = 30  # по умолчанию
    data_types = None  # все типы
    
    if args:
        # Первый аргумент - количество дней
        try:
            days = int(args[0])
            args = args[1:]
        except ValueError:
            pass
        
        # Остальные аргументы - типы данных
        if args:
            data_types = []
            for arg in args:
                arg_lower = arg.lower()
                if arg_lower in ['meals', 'еда', 'food']:
                    data_types.append('meals')
                elif arg_lower in ['weight', 'вес']:
                    data_types.append('weight')
                elif arg_lower in ['workouts', 'тренировки', 'workout']:
                    data_types.append('workouts')
    
    status_msg = await update.message.reply_text(
        f"📦 Готовлю экспорт за {days} дней..."
    )
    
    try:
        from .tools.sqlite_tools import export_user_data
        result = export_user_data(
            user_id=user_id,
            data_types=data_types,
            days=days
        )
        
        if result.get('status') == 'error':
            await status_msg.edit_text(f"❌ {result.get('message')}")
            return
        
        csv_content = result.get('csv_content', '')
        filename = result.get('filename', 'export.csv')
        summary = result.get('summary', '')
        period = result.get('period', '')
        
        if not csv_content.strip():
            await status_msg.edit_text("💭 Нет данных для экспорта за указанный период")
            return
        
        # Отправляем CSV файл
        import io
        csv_file = io.BytesIO(csv_content.encode('utf-8-sig'))  # BOM для Excel
        csv_file.name = filename
        
        await status_msg.delete()
        await update.message.reply_document(
            document=csv_file,
            filename=filename,
            caption=f"📊 *Экспорт данных*\n\n📅 Период: {period}\n📝 {summary}",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


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
        
        # Проверяем есть ли ожидающий экспорт для отправки
        await _send_pending_export_if_exists(user_id, update)
        
    except Exception as e:
        logger.error(f"Error handling text: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


async def _send_pending_export_if_exists(user_id: str, update: Update):
    """Проверяет и отправляет ожидающий экспорт если есть"""
    try:
        from .tools.sqlite_tools import pop_pending_export
        
        export_data = pop_pending_export(user_id)
        if not export_data or export_data.get('status') != 'success':
            return
        
        csv_content = export_data.get('csv_content', '')
        if not csv_content.strip():
            return
        
        filename = export_data.get('filename', 'export.csv')
        summary = export_data.get('summary', '')
        period = export_data.get('period', '')
        
        # Отправляем CSV файл
        csv_file = io.BytesIO(csv_content.encode('utf-8-sig'))  # BOM для Excel
        csv_file.name = filename
        
        await update.message.reply_document(
            document=csv_file,
            filename=filename,
            caption=f"📊 *Экспорт данных*\n\n📅 Период: {period}\n📝 {summary}",
            parse_mode='Markdown'
        )
        logger.info(f"Export file sent to user {user_id}: {filename}")
        
    except Exception as e:
        logger.error(f"Error sending export file: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий — поддержка альбомов (несколько фото одного блюда)"""
    user_id = str(update.effective_user.id)
    media_group_id = update.message.media_group_id
    caption = update.message.caption
    
    # Скачиваем фото (максимальное разрешение)
    photo = update.message.photo[-1]
    photo_file = await context.bot.get_file(photo.file_id)
    photo_bytes = bytes(await photo_file.download_as_bytearray())
    
    if media_group_id:
        # Это альбом — собираем все фото
        if media_group_id not in _media_groups:
            _media_groups[media_group_id] = []
            _media_group_updates[media_group_id] = update
            _media_group_user_ids[media_group_id] = user_id
            if caption:
                _media_group_captions[media_group_id] = caption
            # Запускаем отложенную обработку
            asyncio.create_task(
                _process_media_group_delayed(media_group_id, context)
            )
        
        _media_groups[media_group_id].append(photo_bytes)
        # Сохраняем caption если есть (может быть на любом фото альбома)
        if caption and media_group_id not in _media_group_captions:
            _media_group_captions[media_group_id] = caption
    else:
        # Одиночное фото — обрабатываем сразу
        await _process_single_photo(user_id, photo_bytes, caption, update, context)


async def _process_media_group_delayed(
    media_group_id: str, 
    context: ContextTypes.DEFAULT_TYPE
):
    """Ждём 1.5 сек пока все фото альбома придут, потом обрабатываем"""
    await asyncio.sleep(1.5)
    
    photos = _media_groups.pop(media_group_id, [])
    caption = _media_group_captions.pop(media_group_id, None)
    update = _media_group_updates.pop(media_group_id, None)
    user_id = _media_group_user_ids.pop(media_group_id, None)
    
    if not photos or not update or not user_id:
        return
    
    status_msg = await update.message.reply_text(
        f"📸 Анализирую {len(photos)} фото блюда..."
    )
    
    try:
        # Формируем prompt
        prompt = caption or f"Это {len(photos)} фото одного блюда с разных ракурсов. Распознай блюдо, определи порцию, посчитай КБЖУ."
        
        # Отправляем все фото в одном запросе
        response = await _run_agent_with_multiple_images(user_id, prompt, photos)
        
        try:
            await status_msg.edit_text(response, parse_mode='Markdown')
        except Exception:
            await status_msg.edit_text(response)
    except Exception as e:
        logger.error(f"Error processing media group: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


async def _process_single_photo(
    user_id: str, 
    photo_bytes: bytes, 
    caption: str,
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE
):
    """Обработка одиночного фото"""
    prompt = caption or "Распознай еду на этом фото, определи порцию, посчитай калории и БЖУ."
    
    status_msg = await update.message.reply_text("📸 Анализирую фото...")
    
    try:
        response = await run_agent_multimodal(
            user_id, prompt,
            media_bytes=photo_bytes,
            media_mime_type="image/jpeg"
        )
        
        try:
            await status_msg.edit_text(response, parse_mode='Markdown')
        except Exception:
            await status_msg.edit_text(response)
    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await status_msg.edit_text(f"❌ Ошибка обработки фото: {str(e)}")


async def _run_agent_with_multiple_images(
    user_id: str, 
    message: str, 
    images: list[bytes]
) -> str:
    """Запускает агента с несколькими изображениями"""
    runner = get_runner()
    session_id = f"telegram_{user_id}"
    
    try:
        try:
            await _session_service.create_session(
                app_name="nutrition_tracker",
                user_id=user_id,
                session_id=session_id
            )
        except Exception:
            pass
        
        # Формируем parts: текст + все изображения
        parts = [types.Part(text=f"[user_id: {user_id}] {message}")]
        
        for img_bytes in images:
            parts.append(
                types.Part(
                    inline_data=types.Blob(
                        mime_type="image/jpeg",
                        data=img_bytes
                    )
                )
            )
        
        content = types.Content(role="user", parts=parts)
        
        final_response = ""
        async for event in runner.run_async(
            session_id=session_id,
            user_id=user_id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        if event.is_final_response():
                            final_response = part.text
                        elif not final_response:
                            final_response = part.text
        
        return final_response if final_response else "Не удалось получить ответ."
            
    except Exception as e:
        logger.error(f"Error running agent with images: {e}")
        return f"Произошла ошибка: {str(e)}"


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик голосовых сообщений — расшифровывает аудио через Gemini"""
    user_id = str(update.effective_user.id)
    
    status_msg = await update.message.reply_text("🎤 Расшифровываю голосовое...")
    
    try:
        # Получаем голосовое сообщение
        voice = update.message.voice
        voice_file = await context.bot.get_file(voice.file_id)
        voice_bytes = await voice_file.download_as_bytearray()
        
        # Передаём аудио напрямую в агента (Gemini Audio)
        response = await run_agent_multimodal(
            user_id,
            "Расшифруй это голосовое сообщение. Пользователь описывает еду. "
            "Проанализируй, посчитай калории и БЖУ, сохрани в дневник.",
            media_bytes=voice_bytes,
            media_mime_type="audio/ogg"
        )
        
        try:
            await status_msg.edit_text(response, parse_mode='Markdown')
        except Exception:
            await status_msg.edit_text(response)
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
    application.add_handler(CommandHandler("export", export_command))
    
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
        application.add_handler(CommandHandler("export", export_command))
        
        # Регистрируем обработчики сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.VOICE, handle_voice))
        
        logger.info("🚀 Запуск Telegram бота...")
        
        # Логируем информацию о базе данных
        from .tools.database import get_db_info
        logger.info(f"💾 Database: {get_db_info()}")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        raise


if __name__ == "__main__":
    main()

