# Telegram-бот с монетками

Файлы в архиве:
- `coin_bot.py` — сам бот (весь код в одном файле)
- `requirements.txt` — зависимости
- `Dockerfile` — для запуска в Docker
- `Procfile` — для платформ типа Railway / Render

## 1. Настройка перед запуском (обязательно)

Открой `coin_bot.py`, в самом верху найди блок `НАСТРОЙКИ` и впиши:

```python
BOT_TOKEN = "твой_токен_от_BotFather"
ADMIN_IDS = {123456789}          # твой Telegram ID
CHANNELS = [
    {"chat_id": "@your_channel1", "url": "https://t.me/your_channel1", "title": "Канал 1"},
]
```

- Токен бота — получить у [@BotFather](https://t.me/BotFather).
- Свой Telegram ID — узнать у [@userinfobot](https://t.me/userinfobot).
- Если нужна обязательная подписка на каналы — впиши их в `CHANNELS`
  и **добавь бота в каждый канал администратором** (иначе он не сможет
  проверять подписки). Если подписка не нужна — оставь `CHANNELS = []`.

## 2. Варианты запуска

### Вариант А — обычный VPS (Ubuntu/Debian)

```bash
# устанавливаем Python и venv, если их ещё нет
sudo apt update && sudo apt install -y python3 python3-venv python3-pip

# заходим в папку с ботом
cd coin_bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 coin_bot.py
```

Чтобы бот работал постоянно (даже после закрытия терминала), запусти его
через `systemd` или `screen`/`tmux`:

```bash
# вариант с screen
sudo apt install -y screen
screen -S coinbot
source venv/bin/activate
python3 coin_bot.py
# отключиться от сессии не останавливая бота: Ctrl+A, затем D
# вернуться обратно: screen -r coinbot
```

Либо через systemd (надёжнее, автоперезапуск при падении/перезагрузке сервера):

```ini
# /etc/systemd/system/coinbot.service
[Unit]
Description=Coin Telegram Bot
After=network.target

[Service]
WorkingDirectory=/root/coin_bot
ExecStart=/root/coin_bot/venv/bin/python3 coin_bot.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable coinbot
sudo systemctl start coinbot
sudo systemctl status coinbot   # проверить, что запустился
```

### Вариант Б — Docker (любой хостинг с поддержкой Docker)

```bash
docker build -t coin_bot .
docker run -d --name coin_bot --restart=always \
    -v $(pwd)/data:/app/data \
    coin_bot
```

### Вариант В — Railway / Render / аналогичные PaaS

1. Залей все файлы (`coin_bot.py`, `requirements.txt`, `Procfile`) в GitHub-репозиторий.
2. Подключи репозиторий на Railway/Render.
3. Тип сервиса — **Worker / Background Service** (НЕ Web Service, у бота нет веб-порта).
4. Хостинг сам поставит зависимости из `requirements.txt` и запустит `Procfile`.

⚠️ На таких хостингах файловая система обычно не постоянная (данные удаляются
при пересборке) — подключи persistent volume для `bot.db`, если он есть,
либо позже перейди на внешнюю БД (Postgres) вместо SQLite.

## 3. Проверка, что всё работает

После запуска напиши боту `/start` в Telegram. Если настроены каналы —
бот попросит подписаться перед тем, как открыть меню.

## 4. Админ-команды (напомню)

- `/addcoins <user_id> <кол-во>` — начислить/списать монеты
- `/setcoins <user_id> <кол-во>` — установить точный баланс
- `/userinfo <user_id>` — профиль пользователя
- `/additem <цена> <описание>` — добавить товар в ответ на пересланное фото/видео
- `/addlink <тип> <цена> <ссылка> <описание>` — добавить товар по прямой ссылке из облака
- `/shoplist` — список товаров в магазине
