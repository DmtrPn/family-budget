from app.logger import logging
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql import text


def create_if_not_exist_database(url: str):
    """
    Создает базу данных, если она не существует.

    Args:
        url: URL подключения к базе данных в формате
            postgresql+asyncpg://user:password@host:port/dbname
    """
    # Преобразуем URL для синхронного подключения
    sync_url = url.replace("+asyncpg", "")

    # Получаем имя базы данных из URL
    db_name = url.split("/")[-1]

    # Создаем URL для подключения к postgres (системной БД)
    root_url = sync_url.rsplit("/", 1)[0] + "/postgres"

    engine = create_engine(root_url, isolation_level="AUTOCOMMIT")

    try:
        # Проверяем существование базы данных
        with engine.connect() as connection:
            result = connection.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")).fetchone()

            if not result:
                logging.info(f"База данных не существует. Создаём: {db_name}")
                connection.execute(text(f"CREATE DATABASE {db_name}"))
            else:
                logging.info(f"База данных {db_name} уже существует.")

    except OperationalError as e:
        logging.error(f"Ошибка при создании базы данных: {e}")
        raise
    finally:
        engine.dispose()
