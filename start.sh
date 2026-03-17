#!/bin/sh
# Посев данных при первом запуске, затем запуск сервера + бота
python seed_data.py
python bot.py &
exec uvicorn main:app --host 0.0.0.0 --port 8001
