FROM python:3.10-slim

# Устанавливаем рабочую папку
WORKDIR /app

# Копируем файлы
COPY . .

# Устанавливаем библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Команда запуска
CMD ["python", "main.py"]
