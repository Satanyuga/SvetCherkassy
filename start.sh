
#!/bin/bash

echo "🚀 Запуск системы..."

# Запуск основного бота
python main.py &
MAIN_PID=$!
echo "✅ Основной бот запущен (PID: $MAIN_PID)"

sleep 3

# Запуск мониторинга канала
echo "📡 Запуск мониторинга канала Обленерго..."
python channel_monitor.py &
MONITOR_PID=$!
echo "✅ Мониторинг запущен (PID: $MONITOR_PID)"

# Ждем
wait $MAIN_PID
