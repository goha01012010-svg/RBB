# -*- coding: utf-8 -*-
"""
Telegram-бот с монетками, ежедневным бонусом, профилем, игрой "Чёт/Нечет"
и магазином фото/видео за монеты. Админ-панель встроена (по Telegram ID).

УСТАНОВКА:
    pip install aiogram

НАСТРОЙКА:
    1. Впиши свой токен бота в BOT_TOKEN ниже (получить у @BotFather).
    2. Впиши свой Telegram ID (и других админов) в ADMIN_IDS.
       Узнать свой ID можно у бота @userinfobot.
    3. (опционально) Впиши каналы для обязательной подписки в CHANNELS.
       Бота нужно добавить в эти каналы АДМИНИСТРАТОРОМ, иначе он не сможет
       проверять подписку. Если подписка не нужна — оставь CHANNELS = [].
    4. Запусти: python coin_bot.py

КАК ДОБАВИТЬ КОНТЕНТ В МАГАЗИН (только админ), два способа:

    1) Из облака по прямой ссылке (файл физически хранится в облаке,
       бот присылает его пользователю прямо оттуда при покупке):
           /addlink photo 10 https://example.com/files/pic1.jpg Закат на море
       Формат: /addlink <тип> <цена> <прямая_ссылка> <описание>
       <тип>: photo, video или document.
       ВАЖНО: ссылка должна быть ПРЯМОЙ ссылкой на сам файл (открывается/скачивается
       сразу), а не страницей просмотра. Для Google Drive и Яндекс.Диска нужно
       брать именно "прямую"/"download"-ссылку, а не обычную ссылку "поделиться".

    2) Переслав файл в Telegram (файл будет храниться на серверах Telegram):
           Пришли боту фото/видео, затем ОТВЕТЬ на это сообщение командой:
               /additem 5 Описание товара
           где 5 — цена в монетах. Описание можно не указывать.

АДМИН-КОМАНДЫ:
    /addcoins <user_id> <кол-во>          — начислить (или списать) монеты
    /setcoins <user_id> <кол-во>          — установить точный баланс
    /userinfo <user_id>                   — посмотреть профиль пользователя
    /additem <цена> <описание>            — добавить товар (в ответ на фото/видео)
    /addlink <тип> <цена> <ссылка> <опис> — добавить товар по прямой ссылке из облака
    /shoplist                             — список товаров в магазине
"""

import asyncio
import logging
import random
import sqlite3
from datetime import date, datetime

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8777297869:AAFI8lY9zZhwoBUHEdWRt23h4ucJuEtvML8"
ADMIN_IDS = {8064942862, 8189622055}  # <-- замени на свой Telegram ID (и добавь другие через запятую)
DB_PATH = "bot.db"

# Обязательная подписка на каналы.
# chat_id: @username для публичных каналов, либо числовой ID (вида -100xxxxxxxxxx)
#          для приватных каналов (узнать ID можно, переслав сообщение из канала
#          боту @userinfobot или @getmyid_bot).
# url: ссылка, которая откроется при нажатии на кнопку.
# ВАЖНО: бота нужно добавить в каждый канал АДМИНИСТРАТОРОМ, иначе бот не сможет
# проверить, подписан пользователь или нет.
CHANNELS = [
       {"chat_id": -1003983524031, "url": "https://t.me/+_T-5yV7yCJlkMjE6", "title": "Канал 1"},
       {"chat_id": -1003693383185, "url": "https://t.me/+0rpvnLX8MbJjNDEy", "title": "Канал 2"},
   ]
# Если обязательная подписка не нужна — оставь список CHANNELS пустым: CHANNELS = []
# =====================================================

logging.basicConfig(level=logging.INFO)
router = Router()


# ---------- База данных ----------
def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 0,
            reg_date TEXT,
            last_bonus TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shop_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_type TEXT,
            file_id TEXT,
            price INTEGER,
            description TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(user_id, username):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username, coins, reg_date, last_bonus) VALUES (?, ?, 0, ?, NULL)",
        (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    conn.close()


def update_coins(user_id, delta):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (delta, user_id))
    conn.commit()
    conn.close()


def set_coins(user_id, amount):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET coins = ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()


def set_last_bonus(user_id, d):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_bonus=? WHERE user_id=?", (d, user_id))
    conn.commit()
    conn.close()


def add_shop_item(media_type, file_id, price, description):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO shop_items (media_type, file_id, price, description) VALUES (?, ?, ?, ?)",
        (media_type, file_id, price, description),
    )
    conn.commit()
    conn.close()


def get_shop_items():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM shop_items")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_shop_item(item_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM shop_items WHERE item_id=?", (item_id,))
    row = cur.fetchone()
    conn.close()
    return row


def ensure_user(message: Message):
    user = get_user(message.from_user.id)
    if user is None:
        create_user(message.from_user.id, message.from_user.username or message.from_user.full_name)
        user = get_user(message.from_user.id)
    return user


# ---------- Клавиатуры ----------
def main_menu_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎁 Ежедневный бонус")
    kb.button(text="👤 Профиль")
    kb.button(text="🎲 Игры")
    kb.button(text="🛒 Магазин")
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True)


def game_choice_kb(bet):
    kb = InlineKeyboardBuilder()
    kb.button(text="Чёт", callback_data=f"game:even:{bet}")
    kb.button(text="Нечет", callback_data=f"game:odd:{bet}")
    kb.adjust(2)
    return kb.as_markup()


def shop_kb():
    items = get_shop_items()
    kb = InlineKeyboardBuilder()
    for item in items:
        label = f"{item['description'] or 'Файл'} — {item['price']} монет"
        kb.button(text=label, callback_data=f"buy:{item['item_id']}")
    kb.adjust(1)
    return kb.as_markup()


def subscribe_kb(not_subscribed_channels):
    kb = InlineKeyboardBuilder()
    for ch in not_subscribed_channels:
        kb.button(text=f"📢 {ch['title']}", url=ch["url"])
    kb.button(text="✅ Я подписался", callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()


async def get_not_subscribed(bot: Bot, user_id: int):
    """Возвращает список каналов, на которые пользователь ЕЩЁ НЕ подписан."""
    not_subscribed = []
    for ch in CHANNELS:
        chat_id = ch.get("chat_id")
        if not chat_id:
            logging.error(
                f"В CHANNELS есть запись без ключа 'chat_id': {ch}. "
                f"Проверь формат: {{'chat_id': '@channel', 'url': '...', 'title': '...'}}"
            )
            continue
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status in ("left", "kicked"):
                not_subscribed.append(ch)
        except Exception as e:
            logging.warning(f"Не удалось проверить подписку на {chat_id}: {e}")
            not_subscribed.append(ch)
    return not_subscribed


class SubscriptionMiddleware(BaseMiddleware):
    """
    Блокирует любые действия в боте, пока пользователь не подпишется
    на все каналы из CHANNELS. Админы проверку не проходят.
    """

    def __init__(self, exclude_callback_data=None):
        self.exclude_callback_data = exclude_callback_data or set()
        super().__init__()

    async def __call__(self, handler, event, data):
        if not CHANNELS:
            return await handler(event, data)

        user = event.from_user
        if user is None or is_admin(user.id):
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data in self.exclude_callback_data:
            return await handler(event, data)

        bot: Bot = data["bot"]
        not_sub = await get_not_subscribed(bot, user.id)
        if not_sub:
            text = "Чтобы пользоваться ботом, подпишись на каналы ниже, а затем нажми «Я подписался»:"
            if isinstance(event, CallbackQuery):
                await event.answer()
                await event.message.answer(text, reply_markup=subscribe_kb(not_sub))
            else:
                await event.answer(text, reply_markup=subscribe_kb(not_sub))
            return
        return await handler(event, data)


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery, bot: Bot):
    not_sub = await get_not_subscribed(bot, callback.from_user.id)
    if not_sub:
        await callback.answer("Ты подписался ещё не на все каналы!", show_alert=True)
        return
    create_user(callback.from_user.id, callback.from_user.username or callback.from_user.full_name)
    await callback.answer("Отлично, подписка подтверждена! ✅", show_alert=True)
    await callback.message.answer(
        "Спасибо за подписку! Теперь тебе доступны все функции бота:",
        reply_markup=main_menu_kb(),
    )


# ---------- FSM ----------
class GameStates(StatesGroup):
    waiting_bet = State()


# ---------- Базовые команды ----------
@router.message(Command("start"))
async def cmd_start(message: Message):
    create_user(message.from_user.id, message.from_user.username or message.from_user.full_name)
    await message.answer(
        "Привет! Это бот с монетками 🪙\nВыбирай действие на клавиатуре ниже:",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == "🎁 Ежедневный бонус")
async def daily_bonus(message: Message):
    user = ensure_user(message)
    today = date.today().isoformat()
    if user["last_bonus"] == today:
        await message.answer("Ты уже получал бонус сегодня. Приходи завтра!")
        return
    update_coins(message.from_user.id, 2)
    set_last_bonus(message.from_user.id, today)
    await message.answer("Держи +2 монеты за ежедневный бонус! 🎉")


@router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    user = ensure_user(message)
    text = (
        f"👤 Профиль\n\n"
        f"Ник: @{user['username'] if user['username'] else 'без ника'}\n"
        f"Монет: {user['coins']}\n"
        f"Дата регистрации: {user['reg_date']}"
    )
    await message.answer(text)


@router.message(F.text == "🎲 Игры")
async def games_start(message: Message, state: FSMContext):
    user = ensure_user(message)
    if user["coins"] <= 0:
        await message.answer("У тебя недостаточно монет для игры.")
        return
    await message.answer(f"Твой баланс: {user['coins']} монет.\nВведи сумму ставки:")
    await state.set_state(GameStates.waiting_bet)


@router.message(GameStates.waiting_bet)
async def process_bet(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Введи число — сумму ставки.")
        return
    bet = int(message.text)
    user = ensure_user(message)
    if bet <= 0:
        await message.answer("Ставка должна быть больше нуля.")
        return
    if bet > user["coins"]:
        await message.answer("У тебя недостаточно монет для такой ставки.")
        return
    await state.clear()
    await message.answer(
        f"Ставка: {bet} монет.\nВыбери: выпадет чёт или нечет?",
        reply_markup=game_choice_kb(bet),
    )


@router.callback_query(F.data.startswith("game:"))
async def process_game(callback: CallbackQuery):
    _, choice, bet_str = callback.data.split(":")
    bet = int(bet_str)
    user = get_user(callback.from_user.id)
    if user is None or user["coins"] < bet:
        await callback.answer("Недостаточно монет.", show_alert=True)
        return
    number = random.randint(1, 100)
    result = "even" if number % 2 == 0 else "odd"
    result_text = "Чёт" if result == "even" else "Нечет"
    if choice == result:
        update_coins(callback.from_user.id, bet)
        new_balance = get_user(callback.from_user.id)["coins"]
        await callback.message.edit_text(
            f"Выпало число {number} ({result_text}).\n✅ Ты выиграл! Ставка удвоена.\n"
            f"Твой баланс: {new_balance} монет."
        )
    else:
        update_coins(callback.from_user.id, -bet)
        new_balance = get_user(callback.from_user.id)["coins"]
        await callback.message.edit_text(
            f"Выпало число {number} ({result_text}).\n❌ Ты проиграл ставку.\n"
            f"Твой баланс: {new_balance} монет."
        )
    await callback.answer()


@router.message(F.text == "🛒 Магазин")
async def shop(message: Message):
    items = get_shop_items()
    if not items:
        await message.answer("Магазин пуст. Загляни позже.")
        return
    await message.answer("Выбери, что хочешь получить за монеты:", reply_markup=shop_kb())


@router.callback_query(F.data.startswith("buy:"))
async def buy_item(callback: CallbackQuery, bot: Bot):
    item_id = int(callback.data.split(":")[1])
    item = get_shop_item(item_id)
    if item is None:
        await callback.answer("Товар не найден.", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    if user is None or user["coins"] < item["price"]:
        await callback.answer("Недостаточно монет.", show_alert=True)
        return
    update_coins(callback.from_user.id, -item["price"])
    await callback.answer("Покупка успешна!")
    if item["media_type"] == "photo":
        await bot.send_photo(callback.from_user.id, item["file_id"], caption=item["description"] or "")
    elif item["media_type"] == "video":
        await bot.send_video(callback.from_user.id, item["file_id"], caption=item["description"] or "")
    else:
        await bot.send_document(callback.from_user.id, item["file_id"], caption=item["description"] or "")


# ---------- Админ-панель ----------
def is_admin(user_id):
    return user_id in ADMIN_IDS


@router.message(Command("addcoins"))
async def cmd_addcoins(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args:
        await message.answer("Использование: /addcoins <user_id> <кол-во>")
        return
    parts = command.args.split()
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].lstrip("-").isdigit()):
        await message.answer("Использование: /addcoins <user_id> <кол-во>")
        return
    target_id, amount = int(parts[0]), int(parts[1])
    user = get_user(target_id)
    if user is None:
        await message.answer("Пользователь не найден (он должен хотя бы раз написать /start боту).")
        return
    update_coins(target_id, amount)
    new_balance = get_user(target_id)["coins"]
    await message.answer(f"Готово. Баланс пользователя {target_id}: {new_balance} монет.")


@router.message(Command("setcoins"))
async def cmd_setcoins(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args:
        await message.answer("Использование: /setcoins <user_id> <кол-во>")
        return
    parts = command.args.split()
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        await message.answer("Использование: /setcoins <user_id> <кол-во>")
        return
    target_id, amount = int(parts[0]), int(parts[1])
    user = get_user(target_id)
    if user is None:
        await message.answer("Пользователь не найден.")
        return
    set_coins(target_id, amount)
    await message.answer(f"Баланс пользователя {target_id} установлен на {amount} монет.")


@router.message(Command("userinfo"))
async def cmd_userinfo(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Использование: /userinfo <user_id>")
        return
    target_id = int(command.args.strip())
    user = get_user(target_id)
    if user is None:
        await message.answer("Пользователь не найден.")
        return
    await message.answer(
        f"ID: {user['user_id']}\n"
        f"Ник: @{user['username']}\n"
        f"Монет: {user['coins']}\n"
        f"Регистрация: {user['reg_date']}"
    )


@router.message(Command("additem"))
async def cmd_additem(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not message.reply_to_message:
        await message.answer(
            "Ответь этой командой на сообщение с фото/видео.\n"
            "Формат: /additem <цена> <описание (необязательно)>"
        )
        return
    if not command.args:
        await message.answer("Укажи цену: /additem <цена> <описание>")
        return
    parts = command.args.split(maxsplit=1)
    price_str = parts[0]
    description = parts[1] if len(parts) > 1 else ""
    if not price_str.isdigit():
        await message.answer("Цена должна быть числом.")
        return
    price = int(price_str)
    target = message.reply_to_message
    if target.photo:
        file_id = target.photo[-1].file_id
        media_type = "photo"
    elif target.video:
        file_id = target.video.file_id
        media_type = "video"
    elif target.document:
        file_id = target.document.file_id
        media_type = "document"
    else:
        await message.answer("В сообщении, на которое ты ответил, нет фото/видео/документа.")
        return
    add_shop_item(media_type, file_id, price, description)
    await message.answer(f"Товар добавлен в магазин за {price} монет.")


@router.message(Command("addlink"))
async def cmd_addlink(message: Message, command: CommandObject):
    """
    Добавить товар в магазин по прямой ссылке на файл в облаке
    (Google Drive/Яндекс.Диск с ПРЯМОЙ ссылкой на файл, Dropbox, S3 и т.п.).
    Telegram сам скачает файл по этой ссылке, когда бот будет его отправлять —
    сам файл при этом хранится не у тебя на диске, а в облаке по этой ссылке.

    Формат:
        /addlink <тип> <цена> <ссылка> <описание>
    Где <тип> — photo, video или document.

    Пример:
        /addlink photo 10 https://example.com/files/pic1.jpg Закат на море
    """
    if not is_admin(message.from_user.id):
        return
    if not command.args:
        await message.answer(
            "Использование:\n/addlink <тип> <цена> <ссылка> <описание>\n"
            "тип: photo, video или document\n\n"
            "Пример:\n/addlink photo 10 https://example.com/pic.jpg Закат на море"
        )
        return
    parts = command.args.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer(
            "Не хватает данных. Формат:\n/addlink <тип> <цена> <ссылка> <описание>"
        )
        return
    media_type, price_str, url = parts[0].lower(), parts[1], parts[2]
    description = parts[3] if len(parts) > 3 else ""

    if media_type not in ("photo", "video", "document"):
        await message.answer("Тип должен быть: photo, video или document.")
        return
    if not price_str.isdigit():
        await message.answer("Цена должна быть числом.")
        return
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("Ссылка должна начинаться с http:// или https:// и вести напрямую на файл.")
        return

    price = int(price_str)
    add_shop_item(media_type, url, price, description)
    await message.answer(f"Товар из облака добавлен в магазин за {price} монет ({media_type}).")


@router.message(Command("shoplist"))
async def cmd_shoplist(message: Message):
    if not is_admin(message.from_user.id):
        return
    items = get_shop_items()
    if not items:
        await message.answer("Магазин пуст.")
        return
    text = "\n".join(
        f"#{i['item_id']} — {i['media_type']} — {i['price']} монет — {i['description']}" for i in items
    )
    await message.answer(text)


# ---------- Запуск ----------
async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware(exclude_callback_data={"check_sub"}))
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
