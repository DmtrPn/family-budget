import asyncio
from aiogram import Dispatcher, Bot
from aiohttp import web
from aiohttp.web import middleware

from app.config import WEBHOOK_URL, WEBHOOK_PORT
from app.logger import logger
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp.web_middlewares import normalize_path_middleware

from init import bot, storage
from app.bot.routers.main_router import main_router
from app.bot.routers.site_router import site_router
from app.bot.routers.subscription_router import subscription_router
from app.bot.routers.payment_router import payment_router

from error_handler import ErrorHandlerMiddleware
from app.bot.routers.command_router import command_router, set_bot_commands


async def on_startup(_: Dispatcher, bot: Bot):
    if WEBHOOK_URL is not None:
        response = await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Ответ Telegram API на установку Webhook: {response}")


async def on_shutdown(_: Dispatcher, bot: Bot):
    await bot.delete_webhook()


@middleware
async def log_requests_middleware(request, handler):
    response = await handler(request)
    if response.status != 200:
        logger.warning(f"Ошибка на запрос: {request.method} {request.path} Ответ: {response.status}")
    return response


async def main():
    await bot.delete_webhook()
    dp = Dispatcher(storage=storage)
    dp.include_router(command_router)
    dp.include_router(site_router)
    dp.include_router(subscription_router)
    dp.include_router(payment_router)

    dp.include_router(main_router)
    # dp.errors.register(handle_errors)
    dp.message.middleware(ErrorHandlerMiddleware())

    await set_bot_commands(bot)

    logger.info("Бот запущен и ожидает сообщений...")
    try:
        if WEBHOOK_URL:
            logger.info(f"Включен режим работы через Webhook {WEBHOOK_URL}.")
            app = web.Application(middlewares=[normalize_path_middleware()])
            app.middlewares.append(log_requests_middleware)

            SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
            await on_startup(dp, bot)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host="0.0.0.0", port=int(WEBHOOK_PORT))
            logger.info(f"Запуск aiohttp-сервера на {site.name}")

            await site.start()
            logger.info("Запущен сервер для вебхуков!")
            await asyncio.Event().wait()

        else:
            logger.info("Включен режим работы через Polling.")
            try:
                await dp.start_polling(bot)
            except Exception as e:
                logger.error(f"Ошибка при запуске Polling: {e}")
    finally:
        if WEBHOOK_URL:
            await on_shutdown(dp, bot)

        await bot.sinc_session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
