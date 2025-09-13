from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from app.infrastructure.budget_storage import BudgetStorage


class Database:
    """
    Совместимость с прежним интерфейсом Database, но реализация перенесена
    на инфраструктурный слой (SQLAlchemy AsyncSession через BaseStorage).
    """

    def __init__(self, database_url: str):
        # database_url больше не нужен напрямую: BudgetStorage использует app.config
        self._storage = BudgetStorage()

    async def connect(self):
        # Совместимость: в новой реализации отдельного пула не требуется
        return None

    async def close(self):
        # Совместимость: явного закрытия не требуется
        return None

    async def init_tables(self):
        """Создание таблиц БД"""
        await self._storage.init_tables()

    async def create_or_get_user(self, telegram_id: int, username: str | None = None) -> int:
        """Создать пользователя или получить его ID"""
        return await self._storage.create_or_get_user(telegram_id, username)

    async def create_account(self, user_id: int, name: str) -> bool:
        """Создать новый счет"""
        return await self._storage.create_account(user_id, name)

    async def get_user_accounts(self, user_id: int) -> List[Dict]:
        """Получить все счета пользователя (свои + расшаренные)"""
        return await self._storage.get_user_accounts(user_id)

    async def get_account_by_name(self, user_id: int, name: str) -> Optional[Dict]:
        """Найти счет по названию среди доступных пользователю"""
        return await self._storage.get_account_by_name(user_id, name)

    async def get_account_balance(self, account_id: int) -> float:
        """Получить баланс счета"""
        return await self._storage.get_account_balance(account_id)

    async def add_transaction(
        self,
        account_id: int,
        user_id: int,
        transaction_type: str,
        amount: float,
        category_id: Optional[int],
        comment: str,
    ) -> bool:
        """Добавить транзакцию"""
        await self._storage.add_transaction(account_id, user_id, transaction_type, amount, category_id, comment)
        return True

    async def get_category_by_name(self, name: str) -> Optional[int]:
        """Получить ID категории по названию"""
        return await self._storage.get_category_by_name(name)

    async def share_account(self, account_id: int, owner_id: int, target_user_id: int) -> bool:
        """Расшарить счет другому пользователю"""
        return await self._storage.share_account(account_id, owner_id, target_user_id)

    async def get_stats(self, user_id: int, period_days: int) -> Dict[str, Any]:
        """Получить статистику по всем доступным счетам за период
        Возвращает данные в старом формате для совместимости с handlers:
        {
            'total_income': float,
            'total_expense': float,
            'categories': [
                {'name': str, 'amount': float, 'percentage': float}
            ]  # только по расходам
        }
        """
        raw = await self._storage.get_stats(user_id, period_days)
        totals = raw.get("totals", {})
        total_income = float(totals.get("income", 0.0))
        total_expense = float(totals.get("expense", 0.0))

        expense_by_cat: Dict[str, float] = {k: float(v) for k, v in raw.get("expense", {}).items()}
        # Формируем категории с процентами (от суммы расходов)
        categories: List[Dict[str, Any]] = []
        if total_expense > 0:
            for name, amount in expense_by_cat.items():
                categories.append(
                    {
                        "name": name,
                        "amount": amount,
                        "percentage": (amount / total_expense) * 100.0,
                    }
                )
            # Сортировка по сумме по убыванию для красивого вывода
            categories.sort(key=lambda x: x["amount"], reverse=True)
        else:
            # Нет расходов — возвращаем пустой список
            categories = []

        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "categories": categories,
        }
