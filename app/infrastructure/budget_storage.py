from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.abstract.base_storage import BaseStorage


class BudgetStorage(BaseStorage):
    async def init_tables(self) -> None:
        async with self.session_scope() as session:
            # users
            await session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        telegram_id BIGINT UNIQUE NOT NULL,
                        username VARCHAR(255),
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                    """
                )
            )
            # categories
            await session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS categories (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL
                    );
                    """
                )
            )
            await session.execute(
                text(
                    """
                    INSERT INTO categories (name) VALUES
                    ('еда'), ('транспорт'), ('жильё'), ('развлечения'), ('другое')
                    ON CONFLICT (name) DO NOTHING;
                    """
                )
            )
            # accounts
            await session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS accounts (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(name, owner_id)
                    );
                    """
                )
            )
            # shares
            await session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS account_shares (
                        id SERIAL PRIMARY KEY,
                        account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(account_id, user_id)
                    );
                    """
                )
            )
            # transactions
            await session.execute(
                text(
                    """
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
                    """
                )
            )

    async def create_or_get_user(self, telegram_id: int, username: Optional[str] = None) -> int:
        async with self.session_scope() as session:
            res = await session.execute(text("SELECT id FROM users WHERE telegram_id = :tg"), {"tg": telegram_id})
            row = res.first()
            if row:
                return int(row[0])
            res = await session.execute(
                text(
                    "INSERT INTO users (telegram_id, username) VALUES (:tg, :username) RETURNING id"
                ),
                {"tg": telegram_id, "username": username},
            )
            return int(res.scalar_one())

    async def create_account(self, user_id: int, name: str) -> bool:
        async with self.session_scope() as session:
            try:
                await session.execute(
                    text("INSERT INTO accounts (name, owner_id) VALUES (:name, :owner_id)"),
                    {"name": name, "owner_id": user_id},
                )
                return True
            except IntegrityError:
                # unique constraint (name, owner_id)
                return False

    async def get_account_balance(self, account_id: int) -> float:
        async with self.session_scope(read_only=True) as session:
            res = await session.execute(
                text(
                    """
                    SELECT COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END), 0)
                    FROM transactions WHERE account_id = :account_id
                    """
                ),
                {"account_id": account_id},
            )
            val = res.scalar()
            return float(val or 0)

    async def get_user_accounts(self, user_id: int) -> List[Dict]:
        async with self.session_scope(read_only=True) as session:
            res = await session.execute(
                text(
                    """
                    SELECT DISTINCT a.id, a.name, a.owner_id, u.username as owner_username,
                           CASE WHEN a.owner_id = :uid THEN 'owner' ELSE 'shared' END as role
                    FROM accounts a
                    LEFT JOIN users u ON a.owner_id = u.id
                    LEFT JOIN account_shares s ON a.id = s.account_id
                    WHERE a.owner_id = :uid OR s.user_id = :uid
                    ORDER BY a.name
                    """
                ),
                {"uid": user_id},
            )
            rows = res.mappings().all()
            result: List[Dict] = []
            for row in rows:
                balance = await self.get_account_balance(int(row["id"]))
                result.append(
                    {
                        "id": int(row["id"]),
                        "name": row["name"],
                        "owner_id": int(row["owner_id"]) if row["owner_id"] is not None else None,
                        "owner_username": row["owner_username"],
                        "role": row["role"],
                        "balance": balance,
                    }
                )
            return result

    async def get_account_by_name(self, user_id: int, name: str) -> Optional[Dict]:
        async with self.session_scope(read_only=True) as session:
            res = await session.execute(
                text(
                    """
                    SELECT a.id, a.name, a.owner_id
                    FROM accounts a
                    LEFT JOIN account_shares s ON a.id = s.account_id
                    WHERE (a.owner_id = :uid OR s.user_id = :uid) AND a.name = :name
                    LIMIT 1
                    """
                ),
                {"uid": user_id, "name": name},
            )
            row = res.mappings().first()
            if not row:
                return None
            return {"id": int(row["id"]), "name": row["name"], "owner_id": int(row["owner_id"]) if row["owner_id"] is not None else None}

    async def add_transaction(
        self,
        account_id: int,
        user_id: int,
        transaction_type: str,
        amount: float,
        category_id: Optional[int],
        comment: str,
    ) -> None:
        async with self.session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO transactions (account_id, user_id, type, amount, category_id, comment)
                    VALUES (:account_id, :user_id, :type, :amount, :category_id, :comment)
                    """
                ),
                {
                    "account_id": account_id,
                    "user_id": user_id,
                    "type": transaction_type,
                    "amount": amount,
                    "category_id": category_id,
                    "comment": comment,
                },
            )

    async def get_category_by_name(self, name: str) -> Optional[int]:
        async with self.session_scope(read_only=True) as session:
            res = await session.execute(text("SELECT id FROM categories WHERE name = :name"), {"name": name})
            val = res.scalar()
            return int(val) if val is not None else None

    async def share_account(self, account_id: int, owner_id: int, target_user_id: int) -> bool:
        async with self.session_scope() as session:
            # Проверяем, является ли запрашивающий владельцем счета
            res = await session.execute(
                text("SELECT owner_id FROM accounts WHERE id = :aid"), {"aid": account_id}
            )
            row = res.first()
            if not row or int(row[0]) != owner_id:
                return False
            try:
                await session.execute(
                    text(
                        "INSERT INTO account_shares (account_id, user_id) VALUES (:aid, :uid)"
                    ),
                    {"aid": account_id, "uid": target_user_id},
                )
                return True
            except IntegrityError:
                return False

    async def get_stats(self, user_id: int, period_days: int) -> Dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=period_days)
        async with self.session_scope(read_only=True) as session:
            res = await session.execute(
                text(
                    """
                    SELECT c.name AS category, t.type, SUM(t.amount) AS total
                    FROM transactions t
                    LEFT JOIN categories c ON t.category_id = c.id
                    WHERE t.user_id = :uid AND t.created_at >= :since
                    GROUP BY c.name, t.type
                    ORDER BY c.name
                    """
                ),
                {"uid": user_id, "since": since},
            )
            rows = res.mappings().all()

            stats = {"income": {}, "expense": {}}
            for row in rows:
                category = row["category"] or "без категории"
                stats[row["type"]][category] = float(row["total"] or 0)

            # Общие суммы
            res_total = await session.execute(
                text(
                    """
                    SELECT type, COALESCE(SUM(amount), 0) AS total
                    FROM transactions
                    WHERE user_id = :uid AND created_at >= :since
                    GROUP BY type
                    """
                ),
                {"uid": user_id, "since": since},
            )
            totals = {"income": 0.0, "expense": 0.0}
            for trow in res_total.mappings().all():
                totals[trow["type"]] = float(trow["total"] or 0)

            stats["totals"] = totals
            return stats
