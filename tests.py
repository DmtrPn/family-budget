import pytest
from database import Database

# Используем тестовую базу данных
TEST_DB_URL = "postgresql://test_user:test_password@localhost/test_family_budget"


@pytest.fixture
async def db():
    """Фикстура для тестовой базы данных"""
    database = Database(TEST_DB_URL)
    await database.connect()
    await database.init_tables()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_create_user(db):
    """Тест создания пользователя"""
    user_id = await db.create_or_get_user(12345, "testuser")
    assert user_id is not None

    # Повторное создание должно вернуть тот же ID
    user_id2 = await db.create_or_get_user(12345, "testuser")
    assert user_id == user_id2


@pytest.mark.asyncio
async def test_create_account(db):
    """Тест создания счета"""
    user_id = await db.create_or_get_user(12345, "testuser")

    # Создание счета
    success = await db.create_account(user_id, "Test Account")
    assert success is True

    # Повторное создание должно вернуть False
    success = await db.create_account(user_id, "Test Account")
    assert success is False


@pytest.mark.asyncio
async def test_get_user_accounts(db):
    """Тест получения счетов пользователя"""
    user_id = await db.create_or_get_user(12345, "testuser")

    # Пустой список для нового пользователя
    accounts = await db.get_user_accounts(user_id)
    assert len(accounts) == 0

    # Создаем счет и проверяем
    await db.create_account(user_id, "Test Account")
    accounts = await db.get_user_accounts(user_id)
    assert len(accounts) == 1
    assert accounts[0]["name"] == "Test Account"
    assert accounts[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_transactions(db):
    """Тест операций с транзакциями"""
    user_id = await db.create_or_get_user(12345, "testuser")
    await db.create_account(user_id, "Test Account")

    account = await db.get_account_by_name(user_id, "Test Account")
    account_id = account["id"]

    # Проверяем начальный баланс
    balance = await db.get_account_balance(account_id)
    assert balance == 0

    # Добавляем доход
    category_id = await db.get_category_by_name("еда")
    await db.add_transaction(account_id, user_id, "income", 1000.0, None, "Test income")

    balance = await db.get_account_balance(account_id)
    assert balance == 1000.0

    # Добавляем расход
    await db.add_transaction(account_id, user_id, "expense", 300.0, category_id, "Test expense")

    balance = await db.get_account_balance(account_id)
    assert balance == 700.0


@pytest.mark.asyncio
async def test_account_sharing(db):
    """Тест совместного использования счетов"""
    user1_id = await db.create_or_get_user(12345, "user1")
    user2_id = await db.create_or_get_user(67890, "user2")

    await db.create_account(user1_id, "Shared Account")
    account = await db.get_account_by_name(user1_id, "Shared Account")

    # user2 не должен видеть счет до расшаривания
    user2_accounts = await db.get_user_accounts(user2_id)
    assert len(user2_accounts) == 0

    # Расшариваем счет
    success = await db.share_account(account["id"], user1_id, user2_id)
    assert success is True

    # Теперь user2 должен видеть счет
    user2_accounts = await db.get_user_accounts(user2_id)
    assert len(user2_accounts) == 1
    assert user2_accounts[0]["name"] == "Shared Account"
    assert user2_accounts[0]["role"] == "shared"


@pytest.mark.asyncio
async def test_statistics(db):
    """Тест статистики"""
    user_id = await db.create_or_get_user(12345, "testuser")
    await db.create_account(user_id, "Test Account")

    account = await db.get_account_by_name(user_id, "Test Account")
    account_id = account["id"]

    # Добавляем несколько транзакций
    food_category = await db.get_category_by_name("еда")
    transport_category = await db.get_category_by_name("транспорт")

    await db.add_transaction(account_id, user_id, "income", 10000.0, None, "Salary")
    await db.add_transaction(account_id, user_id, "expense", 3000.0, food_category, "Food")
    await db.add_transaction(account_id, user_id, "expense", 1000.0, transport_category, "Transport")

    # Получаем статистику за месяц
    stats = await db.get_stats(user_id, 30)

    assert stats["total_income"] == 10000.0
    assert stats["total_expense"] == 4000.0
    assert len(stats["categories"]) == 2

    # Проверяем категории
    food_cat = next(cat for cat in stats["categories"] if cat["name"] == "еда")
    assert food_cat["amount"] == 3000.0
    assert food_cat["percentage"] == 75.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
