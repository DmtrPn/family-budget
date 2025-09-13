import asyncpg
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import os


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.database_url)

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def init_tables(self):
        """Создание таблиц БД"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL
                );
            """)

            await conn.execute("""
                INSERT INTO categories (name) VALUES 
                ('еда'), ('транспорт'), ('жильё'), ('развлечения'), ('другое')
                ON CONFLICT (name) DO NOTHING;
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(name, owner_id)
                );
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS account_shares (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(account_id, user_id)
                );
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    type VARCHAR(10) CHECK (type IN ('income', 'expense')),
                    amount DECIMAL(12, 2) NOT NULL,
                    category_id INTEGER REFERENCES categories(id),
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

    async def create_or_get_user(self, telegram_id: int, username: str = None) -> int:
        """Создать пользователя или получить его ID"""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1", telegram_id
            )
            if user:
                return user['id']

            user_id = await conn.fetchval(
                "INSERT INTO users (telegram_id, username) VALUES ($1, $2) RETURNING id",
                telegram_id, username
            )
            return user_id

    async def create_account(self, user_id: int, name: str) -> bool:
        """Создать новый счет"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO accounts (name, owner_id) VALUES ($1, $2)",
                    name, user_id
                )
                return True
        except asyncpg.UniqueViolationError:
            return False

    async def get_user_accounts(self, user_id: int) -> List[Dict]:
        """Получить все счета пользователя (свои + расшаренные)"""
        async with self.pool.acquire() as conn:
            accounts = await conn.fetch("""
                SELECT DISTINCT a.id, a.name, a.owner_id, u.username as owner_username,
                       CASE WHEN a.owner_id = $1 THEN 'owner' ELSE 'shared' END as role
                FROM accounts a
                LEFT JOIN users u ON a.owner_id = u.id
                LEFT JOIN account_shares s ON a.id = s.account_id
                WHERE a.owner_id = $1 OR s.user_id = $1
                ORDER BY a.name
            """, user_id)
            
            # Добавляем баланс для каждого счета
            result = []
            for account in accounts:
                balance = await self.get_account_balance(account['id'])
                result.append({
                    'id': account['id'],
                    'name': account['name'],
                    'owner_id': account['owner_id'],
                    'owner_username': account['owner_username'],
                    'role': account['role'],
                    'balance': balance
                })
            
            return result

    async def get_account_by_name(self, user_id: int, name: str) -> Optional[Dict]:
        """Найти счет по названию среди доступных пользователю"""
        async with self.pool.acquire() as conn:
            account = await conn.fetchrow("""
                SELECT DISTINCT a.id, a.name, a.owner_id
                FROM accounts a
                LEFT JOIN account_shares s ON a.id = s.account_id
                WHERE (a.owner_id = $1 OR s.user_id = $1) AND a.name ILIKE $2
            """, user_id, name)
            
            if account:
                return dict(account)
            return None

    async def get_account_balance(self, account_id: int) -> float:
        """Получить баланс счета"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT 
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END), 0) as balance
                FROM transactions 
                WHERE account_id = $1
            """, account_id)
            return float(result['balance'])

    async def add_transaction(self, account_id: int, user_id: int, transaction_type: str, 
                             amount: float, category_id: Optional[int], comment: str) -> bool:
        """Добавить транзакцию"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO transactions (account_id, user_id, type, amount, category_id, comment)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, account_id, user_id, transaction_type, amount, category_id, comment)
            return True

    async def get_category_by_name(self, name: str) -> Optional[int]:
        """Получить ID категории по названию"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT id FROM categories WHERE name ILIKE $1", name
            )
            return result['id'] if result else None

    async def share_account(self, account_id: int, owner_id: int, target_user_id: int) -> bool:
        """Расшарить счет другому пользователю"""
        try:
            async with self.pool.acquire() as conn:
                # Проверяем, что пользователь является владельцем
                owner = await conn.fetchrow(
                    "SELECT id FROM accounts WHERE id = $1 AND owner_id = $2",
                    account_id, owner_id
                )
                if not owner:
                    return False

                # Добавляем доступ
                await conn.execute("""
                    INSERT INTO account_shares (account_id, user_id) 
                    VALUES ($1, $2)
                """, account_id, target_user_id)
                return True
        except asyncpg.UniqueViolationError:
            return False

    async def get_stats(self, user_id: int, period_days: int) -> Dict[str, Any]:
        """Получить статистику по всем доступным счетам за период"""
        start_date = datetime.now() - timedelta(days=period_days)
        
        async with self.pool.acquire() as conn:
            # Общие доходы и расходы
            totals = await conn.fetchrow("""
                SELECT 
                    COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as total_expense
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                LEFT JOIN account_shares s ON a.id = s.account_id
                WHERE (a.owner_id = $1 OR s.user_id = $1) 
                AND t.created_at >= $2
            """, user_id, start_date)

            # Расходы по категориям
            categories = await conn.fetch("""
                SELECT 
                    c.name,
                    COALESCE(SUM(t.amount), 0) as amount
                FROM categories c
                LEFT JOIN transactions t ON c.id = t.category_id
                LEFT JOIN accounts a ON t.account_id = a.id
                LEFT JOIN account_shares s ON a.id = s.account_id
                WHERE t.type = 'expense' 
                AND (a.owner_id = $1 OR s.user_id = $1)
                AND t.created_at >= $2
                GROUP BY c.name
                HAVING SUM(t.amount) > 0
                ORDER BY amount DESC
            """, user_id, start_date)

            total_expense = float(totals['total_expense'])
            category_stats = []
            
            for cat in categories:
                amount = float(cat['amount'])
                percentage = (amount / total_expense * 100) if total_expense > 0 else 0
                category_stats.append({
                    'name': cat['name'],
                    'amount': amount,
                    'percentage': percentage
                })

            return {
                'total_income': float(totals['total_income']),
                'total_expense': total_expense,
                'categories': category_stats
            }