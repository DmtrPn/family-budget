import asyncio
from app.logger import logger
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from aiohttp.web import middleware
from aiohttp.web_middlewares import normalize_path_middleware

from app.config import settings
from database import Database
from handlers import setup_handlers


async def on_startup(_: Dispatcher, bot: Bot):
    if settings.webhook_url:
        resp = await bot.set_webhook(settings.webhook_url)
        logger.info(f"Webhook set response: {resp}")


async def on_shutdown(_: Dispatcher, bot: Bot):
    await bot.delete_webhook()


@middleware
async def log_requests_middleware(request, handler):
    response = await handler(request)
    if response.status != 200:
        logger.warning(f"Request error: {request.method} {request.path} -> {response.status}")
    return response


async def main():
    """Основная функция запуска бота (поддержка Polling/Webhook)"""

    # Создание бота и диспетчера
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Инициализация базы данных
    db = Database(settings.database_url)
    await db.connect()
    await db.init_tables()
    logger.info("База данных инициализирована")

    # Настройка обработчиков
    handlers_router = setup_handlers(db)
    dp.include_router(handlers_router)

    # Устанавливаем список команд бота
    commands = [
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="new_account", description="Создать счёт"),
        BotCommand(command="accounts", description="Мои счета"),
        BotCommand(command="income", description="Добавить доход (команда)"),
        BotCommand(command="expense", description="Добавить расход (команда)"),
        BotCommand(command="stats", description="Статистика (week|month)"),
        BotCommand(command="share", description="Поделиться счётом"),
    ]
    await bot.set_my_commands(commands)

    try:
        await bot.delete_webhook()
        if settings.webhook_url:
            logger.info(f"Включен режим Webhook: {settings.webhook_url}")
            app = web.Application(middlewares=[normalize_path_middleware()])
            app.middlewares.append(log_requests_middleware)

            # Регистрация обработчика вебхуков
            SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=settings.webhook_path)

            # Старт aiohttp сервера
            await on_startup(dp, bot)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host=settings.webhook_host, port=int(settings.webhook_port))
            logger.info(f"Запуск aiohttp-сервера на {settings.webhook_host}:{settings.webhook_port}")
            await site.start()
            logger.info("Сервер вебхуков запущен. Ожидание событий...")
            await asyncio.Event().wait()
        else:
            logger.info("Включен режим Polling.")
            await dp.start_polling(bot)
    finally:
        if settings.webhook_url:
            await on_shutdown(dp, bot)
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
