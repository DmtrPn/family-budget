import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database import Database
from handlers import setup_handlers


async def main():
    """Основная функция запуска бота"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO if not settings.debug else logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
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
    
    try:
        logger.info("Запуск бота...")
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")