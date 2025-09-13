from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.infrastructure.database import Database

# Helpers for money formatting


def _fmt_amount(amount: float, decimals: int = 2) -> str:
    try:
        return format(amount, f",.{decimals}f").replace(",", " ")
    except Exception:
        # Fallback to simple format
        return f"{amount:.{decimals}f}"


def _fmt_money(amount: float, decimals: int = 2) -> str:
    return f"{_fmt_amount(amount, decimals)} ₽"


router = Router()

# Константы кнопок
BTN_ADD_INCOME = "➕ Пополнить баланс"
BTN_ADD_EXPENSE = "➖ Добавить списание"
BTN_STATS = "📊 Статистика"
BTN_ACCOUNTS = "💳 Счета"
BTN_CANCEL = "Отмена"

CATEGORIES = ["еда", "транспорт", "жильё", "развлечения", "другое"]


class ExpenseFSM(StatesGroup):
    ChoosingAccount = State()
    ChoosingCategory = State()
    EnteringAmount = State()
    Confirming = State()


class IncomeFSM(StatesGroup):
    ChoosingAccount = State()
    EnteringAmount = State()


def _main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADD_INCOME)],
            [KeyboardButton(text=BTN_ADD_EXPENSE)],
            [KeyboardButton(text=BTN_STATS)],
            [KeyboardButton(text=BTN_ACCOUNTS)],
        ],
        resize_keyboard=True,
    )


def setup_handlers(db: Database):
    """Настройка обработчиков с базой данных"""

    @router.message(Command("start"))
    async def cmd_start(message: Message):
        """Команда /start"""
        await db.create_or_get_user(message.from_user.id, message.from_user.username)

        await message.answer(
            "🏦 Добро пожаловать в Семейный бюджет!\n\n" "Выберите действие с помощью кнопок ниже.",
            reply_markup=_main_menu(),
        )

    @router.message(F.text == BTN_ADD_EXPENSE)
    async def start_expense_flow(message: Message, state: FSMContext):
        """Запуск FSM добавления расхода"""
        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)
        accounts = await db.get_user_accounts(user_id)

        # Показать кнопку Отмена на время сценария
        cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)
        await message.answer("Выберите счёт для списания:", reply_markup=cancel_kb)

        if not accounts:
            await message.answer("📭 У вас нет счетов. Создайте счёт командой: /new_account <название>")
            await state.clear()
            await message.answer("Возвращаю главное меню", reply_markup=_main_menu())
            return

        if len(accounts) == 1:
            # Автовыбор
            await state.update_data(account_id=accounts[0]["id"], account_name=accounts[0]["name"])
            # Переходим к выбору категории
            builder = [
                [InlineKeyboardButton(text=cat.capitalize(), callback_data=f"cat:{cat}") for cat in CATEGORIES[:3]],
                [InlineKeyboardButton(text=cat.capitalize(), callback_data=f"cat:{cat}") for cat in CATEGORIES[3:]],
            ]
            await message.answer("Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=builder))
            await state.set_state(ExpenseFSM.ChoosingCategory)
        else:
            # Показать список счетов инлайн-кнопками
            rows = []
            row = []
            for i, acc in enumerate(accounts, 1):
                row.append(
                    InlineKeyboardButton(
                        text=f"{acc['name']} ({_fmt_money(acc['balance'], 0)})",
                        callback_data=f"acc:{acc['id']}:{acc['name']}",
                    )
                )
                if i % 2 == 0:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            await message.answer("Выберите счёт:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
            await state.set_state(ExpenseFSM.ChoosingAccount)

    @router.message(F.text == BTN_STATS)
    async def stats_menu(message: Message):
        """Показать выбор периода статистики"""
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Неделя", callback_data="period:week"),
                    InlineKeyboardButton(text="Месяц", callback_data="period:month"),
                ]
            ]
        )
        await message.answer("Выберите период статистики:", reply_markup=kb)

    @router.message(F.text == BTN_ADD_INCOME)
    async def start_income_flow(message: Message, state: FSMContext):
        """Запуск пополнения (доход) через кнопки"""
        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)
        accounts = await db.get_user_accounts(user_id)

        cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)
        await message.answer("Выберите счёт для пополнения:", reply_markup=cancel_kb)

        if not accounts:
            await message.answer("📭 У вас нет счетов. Создайте счёт командой: /new_account <название>")
            await state.clear()
            await message.answer("Возвращаю главное меню", reply_markup=_main_menu())
            return

        if len(accounts) == 1:
            await state.update_data(account_id=accounts[0]["id"], account_name=accounts[0]["name"])
            await message.answer("Введите сумму, при желании добавьте комментарий через пробел.")
            await state.set_state(IncomeFSM.EnteringAmount)
        else:
            rows = []
            row = []
            for i, acc in enumerate(accounts, 1):
                row.append(
                    InlineKeyboardButton(
                        text=f"{acc['name']} ({_fmt_money(acc['balance'], 0)})",
                        callback_data=f"incacc:{acc['id']}:{acc['name']}",
                    )
                )
                if i % 2 == 0:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            await message.answer("Выберите счёт:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
            await state.set_state(IncomeFSM.ChoosingAccount)

    @router.callback_query(F.data.startswith("incacc:"))
    async def income_choose_account(cb: CallbackQuery, state: FSMContext):
        if await state.get_state() != IncomeFSM.ChoosingAccount:
            await cb.answer()
            return
        _, acc_id, acc_name = cb.data.split(":", 2)
        await state.update_data(account_id=int(acc_id), account_name=acc_name)
        await cb.message.answer("Введите сумму, при желании добавьте комментарий через пробел.")
        await state.set_state(IncomeFSM.EnteringAmount)
        await cb.answer()

    @router.message(IncomeFSM.EnteringAmount)
    async def income_enter_amount(message: Message, state: FSMContext):
        text = message.text.strip()
        first, *rest = text.split()
        try:
            amount = float(first.replace(",", "."))
            if amount <= 0:
                raise ValueError()
        except Exception:
            await message.answer("Сумма должна быть числом. Попробуйте ещё раз.")
            return
        comment = " ".join(rest)
        data = await state.get_data()
        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)
        account_id = data.get("account_id")
        account_name = data.get("account_name")
        await db.add_transaction(account_id, user_id, "income", amount, None, comment)
        new_balance = await db.get_account_balance(account_id)
        await message.answer(
            f"✅ Пополнение: +{_fmt_amount(amount, 0)}"
            f" (счёт: {account_name}). Комментарий: {comment if comment else '—'}",
            reply_markup=_main_menu(),
        )
        await message.answer(f"🏦 Баланс счёта '{account_name}': {_fmt_money(new_balance)}")
        await state.clear()

    @router.message(F.text == BTN_ACCOUNTS)
    async def accounts_menu(message: Message):
        """Список счетов по кнопке"""
        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)
        accounts = await db.get_user_accounts(user_id)
        if not accounts:
            await message.answer(
                "📭 У вас пока нет счетов. Создайте первый: /new_account <название>", reply_markup=_main_menu()
            )
            return
        text = "💳 Ваши счета:\n\n"
        for account in accounts:
            role_emoji = "👑" if account["role"] == "owner" else "🤝"
            owner_info = "" if account["role"] == "owner" else f" (владелец: @{account['owner_username']})"
            text += f"{role_emoji} {account['name']}: {_fmt_money(account['balance'])}{owner_info}\n"
        await message.answer(text, reply_markup=_main_menu())

    @router.message(F.text == BTN_CANCEL)
    async def cancel_anytime(message: Message, state: FSMContext):
        await state.clear()
        await message.answer("❌ Действие отменено.", reply_markup=_main_menu())

    @router.callback_query(F.data.startswith("acc:"))
    async def choose_account(cb: CallbackQuery, state: FSMContext):
        if await state.get_state() != ExpenseFSM.ChoosingAccount:
            await cb.answer()
            return
        _, acc_id, acc_name = cb.data.split(":", 2)
        await state.update_data(account_id=int(acc_id), account_name=acc_name)
        # Кнопки категорий
        rows = [
            [InlineKeyboardButton(text=cat.capitalize(), callback_data=f"cat:{cat}") for cat in CATEGORIES[:3]],
            [InlineKeyboardButton(text=cat.capitalize(), callback_data=f"cat:{cat}") for cat in CATEGORIES[3:]],
        ]
        await cb.message.answer("Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        await state.set_state(ExpenseFSM.ChoosingCategory)
        await cb.answer()

    @router.callback_query(F.data.startswith("cat:"))
    async def choose_category(cb: CallbackQuery, state: FSMContext):
        if await state.get_state() != ExpenseFSM.ChoosingCategory:
            await cb.answer()
            return
        _, cat = cb.data.split(":", 1)
        await state.update_data(category=cat)
        await cb.message.answer("Введите сумму, при желании добавьте комментарий через пробел.")
        await state.set_state(ExpenseFSM.EnteringAmount)
        await cb.answer()

    @router.message(ExpenseFSM.EnteringAmount)
    async def enter_amount(message: Message, state: FSMContext):
        text = message.text.strip()
        # ожидается: "500" или "500 ужин в кафе"
        first, *rest = text.split()
        try:
            amount = float(first.replace(",", "."))
            if amount <= 0:
                raise ValueError()
        except Exception:
            await message.answer("Сумма должна быть числом. Попробуйте ещё раз.")
            return
        comment = " ".join(rest)
        data = await state.get_data()
        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)
        # Проверим категорию id
        category_id = await db.get_category_by_name(data.get("category"))
        if not category_id:
            await message.answer("Ошибка: категория не найдена. Начните сначала.", reply_markup=_main_menu())
            await state.clear()
            return
        account_id = data.get("account_id")
        account_name = data.get("account_name")
        await db.add_transaction(account_id, user_id, "expense", amount, category_id, comment)
        new_balance = await db.get_account_balance(account_id)
        category_name = data.get("category")
        await message.answer(
            f"✅ Списание: {_fmt_amount(amount, 0)} ({category_name},"
            f" счёт: {account_name}). Комментарий: {comment if comment else '—'}",
            reply_markup=_main_menu(),
        )
        await message.answer(f"🏦 Баланс счёта '{account_name}': {_fmt_money(new_balance)}")
        await state.clear()

    # Оставляем существующие командные обработчики ниже
    @router.message(Command("new_account"))
    async def cmd_new_account(message: Message):
        """Создание нового счета"""
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Укажите название счета: /new_account <название>")
            return

        account_name = args[1].strip()
        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)

        success = await db.create_account(user_id, account_name)
        if success:
            await message.answer(f"✅ Счет '{account_name}' создан!")
        else:
            await message.answer(f"❌ Счет '{account_name}' уже существует!")

    @router.message(Command("accounts"))
    async def cmd_accounts(message: Message):
        """Список счетов пользователя"""
        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)

        accounts = await db.get_user_accounts(user_id)
        if not accounts:
            await message.answer("📭 У вас пока нет счетов. Создайте первый: /new_account <название>")
            return

        text = "💳 Ваши счета:\n\n"
        for account in accounts:
            role_emoji = "👑" if account["role"] == "owner" else "🤝"
            owner_info = "" if account["role"] == "owner" else f" (владелец: @{account['owner_username']})"
            text += f"{role_emoji} {account['name']}: {_fmt_money(account['balance'])}{owner_info}\n"

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

        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)

        account = await db.get_account_by_name(user_id, account_name)
        if not account:
            await message.answer(f"❌ Счет '{account_name}' не найден!")
            return

        await db.add_transaction(account["id"], user_id, "income", amount, None, comment)

        new_balance = await db.get_account_balance(account["id"])
        await message.answer(
            f"✅ Доход добавлен!\n"
            f"💳 Счет: {account['name']}\n"
            f"💰 Сумма: +{_fmt_money(amount)}\n"
            f"💬 Комментарий: {comment}\n"
            f"🏦 Баланс: {_fmt_money(new_balance)}"
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

        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)

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

        await db.add_transaction(account["id"], user_id, "expense", amount, category_id, comment)

        new_balance = await db.get_account_balance(account["id"])
        await message.answer(
            f"✅ Расход добавлен!\n"
            f"💳 Счет: {account['name']}\n"
            f"💸 Сумма: -{_fmt_money(amount)}\n"
            f"📂 Категория: {category_name}\n"
            f"💬 Комментарий: {comment}\n"
            f"🏦 Баланс: {_fmt_money(new_balance)}"
        )

    @router.message(Command("stats"))
    async def cmd_stats(message: Message):
        """Статистика за период (команда)"""
        args = message.text.split()
        if len(args) < 2 or args[1] not in ["week", "month"]:
            await message.answer(
                "❌ Укажите период для статистики!\n" "Доступные варианты: /stats week или /stats month"
            )
            return
        period = args[1]
        await _send_stats(message, period, message.from_user)

    @router.callback_query(F.data.startswith("period:"))
    async def stats_period(cb: CallbackQuery):
        period = cb.data.split(":", 1)[1]
        await _send_stats(cb.message, period, cb.from_user)
        await cb.answer()

    async def _send_stats(message: Message, period: str, user):
        if period not in ("week", "month"):
            await message.answer("Неверный период.")
            return
        days = 7 if period == "week" else 30
        period_name = "неделю" if period == "week" else "месяц"
        # Используем пользователя-инициатора (сообщение или колбэк)
        user_id = await db.create_or_get_user(user.id, user.username)
        stats = await db.get_stats(user_id, days)
        text = f"📊 Статистика за {period_name}:\n\n"
        text += f"💰 Доходы: {_fmt_money(stats['total_income'])}\n"
        text += f"💸 Расходы: {_fmt_money(stats['total_expense'])}\n"
        text += f"💵 Разница: {_fmt_money(stats['total_income'] - stats['total_expense'])}\n\n"
        if stats["categories"]:
            text += "📂 Расходы по категориям:\n"
            for cat in stats["categories"]:
                text += f"• {cat['name']}: {_fmt_money(cat['amount'])} ({cat['percentage']:.1f}%)\n"
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

        user_id = await db.create_or_get_user(message.from_user.id, message.from_user.username)

        # Проверяем счет
        account = await db.get_account_by_name(user_id, account_name)
        if not account:
            await message.answer(f"❌ Счет '{account_name}' не найден!")
            return

        # Проверяем, что пользователь является владельцем
        if account["owner_id"] != user_id:
            await message.answer("❌ Вы не являетесь владельцем этого счета!")
            return

        # Получаем или создаем целевого пользователя
        target_user_id = await db.create_or_get_user(target_user_telegram_id)

        success = await db.share_account(account["id"], user_id, target_user_id)
        if success:
            await message.answer(f"✅ Счет '{account_name}' успешно расшарен пользователю {target_user_telegram_id}!")
        else:
            await message.answer("❌ Ошибка при расшаривании счета. Возможно, доступ уже предоставлен.")

    return router
