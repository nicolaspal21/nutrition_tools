"""
Webhook сервер для Cloud Run
Принимает HTTP запросы от Telegram и обрабатывает их через ADK агента
"""
import os
import asyncio
import logging
from aiohttp import web
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Загружаем .env
load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Глобальная переменная для Application
application: Application = None


def _log_update_task_result(task: asyncio.Task):
    """Логирует исключения из фоновой обработки update (иначе они теряются)."""
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.error(f"Unhandled error while processing update: {exc}", exc_info=exc)


# Сколько ждать обработку внутри запроса. Меньше таймаута ретрая Telegram:
# если не успели — отвечаем 200 (чтобы не получить дубль), задача доработает в фоне
PROCESS_TIMEOUT_SEC = 55


async def _process_update_within_request(update: Update):
    """
    Полная обработка update, включая отложенные задачи (альбомы фото).

    Обработка намеренно происходит ВНУТРИ webhook-запроса: Cloud Run с
    request-based биллингом выделяет CPU только пока открыт HTTP-запрос.
    Раньше мы отвечали 200 сразу и обрабатывали в фоне — фоновая задача
    работала на задушенном (~0.01) CPU, отсюда и ответы по минуте.
    """
    await application.process_update(update)

    # Альбомы: handle_photo откладывает обработку в отдельную задачу
    # (ждёт 1.5с, пока придут все фото) — дожидаемся её в рамках запроса
    from .telegram_bot import background_tasks
    pending = {t for t in background_tasks if not t.done()}
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def webhook_handler(request: web.Request) -> web.Response:
    """Обработчик webhook запросов от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)

        task = asyncio.create_task(_process_update_within_request(update))
        task.add_done_callback(_log_update_task_result)
        try:
            # shield: при таймауте задача не отменяется, а доделывается в фоне
            await asyncio.wait_for(asyncio.shield(task), timeout=PROCESS_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            logger.warning(
                f"Update processing exceeded {PROCESS_TIMEOUT_SEC}s; "
                f"returning 200 early, task continues in background"
            )
        except Exception:
            pass  # ошибка уже залогирована в _log_update_task_result

        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500, text=str(e))


async def health_check(request: web.Request) -> web.Response:
    """Health check для Cloud Run"""
    return web.Response(text="OK", status=200)


async def on_startup(app: web.Application):
    """Инициализация при старте"""
    global application
    
    try:
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        webhook_url = os.getenv('WEBHOOK_URL')
        
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set!")
        
        # Импортируем хендлеры из telegram_bot.py
        from .telegram_bot import (
            start, help_command, today_command, week_command,
            goals_command, undo_command, export_command,
            handle_text, handle_photo, handle_voice
        )
        
        # Создаём Application
        application = Application.builder().token(token).build()
        
        # Регистрируем хендлеры команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("today", today_command))
        application.add_handler(CommandHandler("week", week_command))
        application.add_handler(CommandHandler("goals", goals_command))
        application.add_handler(CommandHandler("undo", undo_command))
        application.add_handler(CommandHandler("export", export_command))
        
        # Инициализируем БД сразу при старте
        from .tools.sqlite_tools import _init_db
        _init_db()
        logger.info("✅ Database tables initialized")

        # Прогреваем агента при старте: иначе первое сообщение платит за
        # импорт ADK-агента, инициализацию memory DB и session service
        from .telegram_bot import get_runner
        get_runner()
        logger.info("✅ Agent runner warmed up")
        
        # Регистрируем хендлеры сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.VOICE, handle_voice))
        
        # Инициализируем бота
        await application.initialize()
        await application.start()
        
        # Устанавливаем webhook
        if webhook_url:
            # Запускаем установку вебхука в фоне, чтобы не блокировать старт сервера
            asyncio.create_task(_setup_webhook_background(application, webhook_url))
        else:
            logger.warning("⚠️ WEBHOOK_URL not set! Set it after first deploy.")
        
        logger.info("🚀 Nutrition Tracker webhook server started!")
    except Exception as e:
        logger.critical(f"🔥 Critical error in on_startup: {e}", exc_info=True)
        raise


async def _setup_webhook_background(application: Application, webhook_url: str):
    """Установка вебхука в фоне с повторными попытками"""
    webhook_full_url = f"{webhook_url}/webhook"
    logger.info(f"⏳ Scheduling webhook setup for {webhook_full_url}...")
    
    # Даем серверу время запуститься
    await asyncio.sleep(2)
    
    try:
        await application.bot.set_webhook(url=webhook_full_url)
        logger.info(f"✅ Webhook set to {webhook_full_url}")
    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}")


async def on_shutdown(app: web.Application):
    """Очистка при остановке"""
    global application
    if application:
        # Удаляем webhook при остановке (опционально)
        # await application.bot.delete_webhook()
        await application.stop()
        await application.shutdown()
        logger.info("👋 Webhook server stopped")


def main():
    """Запуск webhook сервера"""
    port = int(os.getenv('PORT', 8080))
    
    print("""
    ╔═══════════════════════════════════════════════════╗
    ║     🍎 NUTRITION TRACKER - CLOUD RUN 🍎           ║
    ║                                                   ║
    ║  Webhook Server for Google Cloud Run              ║
    ║  Built with Google ADK                            ║
    ╚═══════════════════════════════════════════════════╝
    """)
    
    app = web.Application()
    
    # Роуты
    app.router.add_post('/webhook', webhook_handler)
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    # Lifecycle hooks
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    logger.info(f"Starting webhook server on port {port}")
    web.run_app(app, host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()

