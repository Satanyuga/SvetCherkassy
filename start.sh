#!/bin/bash

# Запуск основного бота и веб-сервера
python main.py &
MAIN_PID=$!

# Даем время на запуск основного бота
sleep 5

# Запуск userbot для мониторинга канала
python userbot.py &
USERBOT_PID=$!

echo "✅ Основной бот запущен (PID: $MAIN_PID)"
echo "✅ UserBot запущен (PID: $USERBOT_PID)"

# Ждем завершения любого из процессов
wait -n

# Если один упал - останавливаем второй
kill $MAIN_PID $USERBOT_PID 2>/dev/null

echo "❌ Один из процессов остановлен, перезапуск..."
