# Указываем базовый образ
FROM python:3.13-slim

WORKDIR /app

# Копируем файл с зависимостями (если используется venv, сначала создайте `requirements.txt`)
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта в контейнер
COPY . .

# Указываем команду запуска
CMD ["python", "./app/main.py"]
