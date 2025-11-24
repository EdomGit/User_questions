# Используем Python 3.12 slim образ для меньшего размера
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все необходимые файлы приложения
COPY main.py .
COPY agent.py .
COPY openai_module.py .

# Переменные окружения будут загружаться из .env файла через python-dotenv
# Убедитесь, что .env файл скопирован в контейнер или используйте docker-compose для передачи переменных

# Открываем порт 8001
EXPOSE 8001

# Запускаем приложение
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

