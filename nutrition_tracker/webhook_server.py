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


async def webhook_handler(request: web.Request) -> web.Response:
    """Обработчик webhook запросов от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        
        # Обрабатываем update асинхронно
        asyncio.create_task(application.process_update(update))
        
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
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    webhook_url = os.getenv('WEBHOOK_URL')
    
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set!")
    
    # Импортируем хендлеры из telegram_bot.py
    from .telegram_bot import (
        start, help_command, today_command, week_command,
        goals_command, undo_command, sync_command,
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
    application.add_handler(CommandHandler("sync", sync_command))
    
    # Регистрируем хендлеры сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Инициализируем бота
    await application.initialize()
    await application.start()
    
    # Устанавливаем webhook
    if webhook_url:
        webhook_full_url = f"{webhook_url}/webhook"
        await application.bot.set_webhook(url=webhook_full_url)
        logger.info(f"✅ Webhook set to {webhook_full_url}")
    else:
        logger.warning("⚠️ WEBHOOK_URL not set! Set it after first deploy.")
    
    logger.info("🚀 Nutrition Tracker webhook server started!")


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

