FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY coin_bot.py .

# Файл базы данных будет создан автоматически при первом запуске.
# Если хостинг поддерживает volume/persistent storage — примонтируй его в /app,
# чтобы bot.db не терялся при пересборке/рестарте контейнера.
VOLUME ["/app/data"]

CMD ["python", "coin_bot.py"]
