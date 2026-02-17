#!/bin/bash

echo "🚀 Запуск системы..."

# Запуск основного бота
python main.py &
MAIN_PID=$!
echo "✅ Основной бот запущен (PID: $MAIN_PID)"

sleep 3

# Запуск RSS парсера (БЕЗ авторизации!)
echo "📡 Запуск RSS парсера..."
python rss_parser.py &
RSS_PID=$!
echo "✅ RSS парсер запущен (PID: $RSS_PID)"

# Ждем
wait $MAIN_PID
