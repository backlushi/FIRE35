#!/bin/sh
# Посев данных при первом запуске, затем запуск сервера
python seed_data.py
exec uvicorn main:app --host 0.0.0.0 --port 8001
