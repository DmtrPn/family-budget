from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database import Database

router = Router()


def setup_handlers(db: Database):
    """Настройка обработчиков с базой данных"""
    
    @router.message(Command("start"))
    async def cmd_start(message: Message):
        """Команда /start"""
        user_id = await db.create_or_get_user(
            message.from_user.id, 
            message.from_user.username
        )
        
        await message.answer(
            "🏦 Добро пожаловать в Семейный бюджет!\n\n"
            "Доступные команды:\n"
            "💳 /new_account <название> - Создать счет\n"
            "📋 /accounts - Мои счета\n"
            "💰 /income <счет> <сумма> <комментарий> - Пополнение\n"
            "💸 /expense <счет> <сумма> <категория> <комментарий> - Расход\n"
            "📊 /stats week - Статистика за неделю\n"
            "📊 /stats month - Статистика за месяц\n"
            "🤝 /share <счет> <user_id> - Поделиться счетом\n\n"
            "Категории расходов: еда, транспорт, жильё, развлечения, другое"
        )

    @router.message(Command("new_account"))
    async def cmd_new_account(message: Message):
        """Создание нового счета"""
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Укажите название счета: /new_account <название>")
            return
        
        account_name = args[1].strip()
        user_id = await db.create_or_get_user(
            message.from_user.id,
            message.from_user.username
        )
        
        success = await db.create_account(user_id, account_name)
        if success:
            await message.answer(f"✅ Счет '{account_name}' создан!")
        else:
            await message.answer(f"❌ Счет '{account_name}' уже существует!")

    @router.message(Command("accounts"))
    async def cmd_accounts(message: Message):
        """Список счетов пользователя"""
        user_id = await db.create_or_get_user(
            message.from_user.id,
            message.from_user.username
        )
        
        accounts = await db.get_user_accounts(user_id)
        if not accounts:
            await message.answer("📭 У вас пока нет счетов. Создайте первый: /new_account <название>")
            return
        
        text = "💳 Ваши счета:\n\n"
        for account in accounts:
            role_emoji = "👑" if account['role'] == 'owner' else "🤝"
            owner_info = "" if account['role'] == 'owner' else f" (владелец: @{account['owner_username']})"
            text += f"{role_emoji} {account['name']}: {account['balance']:.2f} ₽{owner_info}\n"
        
        await message.answer(text)

    @router.message(Command("income"))
    async def cmd_income(message: Message):
        """Добавление дохода"""
        args = message.text.split()
        if len(args) < 4:
            await message.answer(
                "❌ Неверный формат команды!\n"
                "Правильный формат: /income <счет> <сумма> <комментарий>\n"
                "Пример: /income Карта 50000 зарплата"
            )
            return
        
        account_name = args[1]
        try:
            amount = float(args[2])
            if amount <= 0:
                raise ValueError()
        except ValueError:
            await message.answer("❌ Сумма должна быть положительным числом!")
            return
        
        comment = " ".join(args[3:])
        
        user_id = await db.create_or_get_user(
            message.from_user.id,
            message.from_user.username
        )
        
        account = await db.get_account_by_name(user_id, account_name)
        if not account:
            await message.answer(f"❌ Счет '{account_name}' не найден!")
            return
        
        await db.add_transaction(
            account['id'], user_id, 'income', amount, None, comment
        )
        
        new_balance = await db.get_account_balance(account['id'])
        await message.answer(
            f"✅ Доход добавлен!\n"
            f"💳 Счет: {account['name']}\n"
            f"💰 Сумма: +{amount:.2f} ₽\n"
            f"💬 Комментарий: {comment}\n"
            f"🏦 Баланс: {new_balance:.2f} ₽"
        )

    @router.message(Command("expense"))
    async def cmd_expense(message: Message):
        """Добавление расхода"""
        args = message.text.split()
        if len(args) < 5:
            await message.answer(
                "❌ Неверный формат команды!\n"
                "Правильный формат: /expense <счет> <сумма> <категория> <комментарий>\n"
                "Пример: /expense Карта 5000 продукты магазин\n"
                "Категории: еда, транспорт, жильё, развлечения, другое"
            )
            return
        
        account_name = args[1]
        try:
            amount = float(args[2])
            if amount <= 0:
                raise ValueError()
        except ValueError:
            await message.answer("❌ Сумма должна быть положительным числом!")
            return
        
        category_name = args[3]
        comment = " ".join(args[4:])
        
        user_id = await db.create_or_get_user(
            message.from_user.id,
            message.from_user.username
        )
        
        # Проверяем счет
        account = await db.get_account_by_name(user_id, account_name)
        if not account:
            await message.answer(f"❌ Счет '{account_name}' не найден!")
            return
        
        # Проверяем категорию
        category_id = await db.get_category_by_name(category_name)
        if not category_id:
            await message.answer(
                f"❌ Категория '{category_name}' не найдена!\n"
                "Доступные категории: еда, транспорт, жильё, развлечения, другое"
            )
            return
        
        await db.add_transaction(
            account['id'], user_id, 'expense', amount, category_id, comment
        )
        
        new_balance = await db.get_account_balance(account['id'])
        await message.answer(
            f"✅ Расход добавлен!\n"
            f"💳 Счет: {account['name']}\n"
            f"💸 Сумма: -{amount:.2f} ₽\n"
            f"📂 Категория: {category_name}\n"
            f"💬 Комментарий: {comment}\n"
            f"🏦 Баланс: {new_balance:.2f} ₽"
        )

    @router.message(Command("stats"))
    async def cmd_stats(message: Message):
        """Статистика за период"""
        args = message.text.split()
        if len(args) < 2 or args[1] not in ['week', 'month']:
            await message.answer(
                "❌ Укажите период для статистики!\n"
                "Доступные варианты: /stats week или /stats month"
            )
            return
        
        period = args[1]
        days = 7 if period == 'week' else 30
        period_name = "неделю" if period == 'week' else "месяц"
        
        user_id = await db.create_or_get_user(
            message.from_user.id,
            message.from_user.username
        )
        
        stats = await db.get_stats(user_id, days)
        
        text = f"📊 Статистика за {period_name}:\n\n"
        text += f"💰 Доходы: {stats['total_income']:.2f} ₽\n"
        text += f"💸 Расходы: {stats['total_expense']:.2f} ₽\n"
        text += f"💵 Разница: {stats['total_income'] - stats['total_expense']:.2f} ₽\n\n"
        
        if stats['categories']:
            text += "📂 Расходы по категориям:\n"
            for cat in stats['categories']:
                text += f"• {cat['name']}: {cat['amount']:.2f} ₽ ({cat['percentage']:.1f}%)\n"
        else:
            text += "📭 Нет расходов за данный период"
        
        await message.answer(text)

    @router.message(Command("share"))
    async def cmd_share(message: Message):
        """Поделиться счетом с другим пользователем"""
        args = message.text.split()
        if len(args) < 3:
            await message.answer(
                "❌ Неверный формат команды!\n"
                "Правильный формат: /share <счет> <user_id>\n"
                "Пример: /share Карта 123456789"
            )
            return
        
        account_name = args[1]
        try:
            target_user_telegram_id = int(args[2])
        except ValueError:
            await message.answer("❌ ID пользователя должен быть числом!")
            return
        
        user_id = await db.create_or_get_user(
            message.from_user.id,
            message.from_user.username
        )
        
        # Проверяем счет
        account = await db.get_account_by_name(user_id, account_name)
        if not account:
            await message.answer(f"❌ Счет '{account_name}' не найден!")
            return
        
        # Проверяем, что пользователь является владельцем
        if account['owner_id'] != user_id:
            await message.answer("❌ Вы не являетесь владельцем этого счета!")
            return
        
        # Получаем или создаем целевого пользователя
        target_user_id = await db.create_or_get_user(target_user_telegram_id)
        
        success = await db.share_account(account['id'], user_id, target_user_id)
        if success:
            await message.answer(
                f"✅ Счет '{account_name}' успешно расшарен пользователю {target_user_telegram_id}!"
            )
        else:
            await message.answer("❌ Ошибка при расшаривании счета. Возможно, доступ уже предоставлен.")

    return router