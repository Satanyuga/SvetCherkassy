#!/bin/bash

# Запуск основного бота и веб-сервера
python main.py > main.log 2>&1 &
MAIN_PID=$!

# Даем время на запуск основного бота
sleep 5

# Запуск userbot для мониторинга канала
# НО ТОЛЬКО если есть сессия!
if [ -f "userbot_session.session" ]; then
    python userbot.py > userbot.log 2>&1 &
    USERBOT_PID=$!
    echo "✅ Основной бот запущен (PID: $MAIN_PID)"
    echo "✅ UserBot запущен (PID: $USERBOT_PID)"
else
    echo "⚠️ userbot_session.session не найден - UserBot отключен"
    echo "✅ Только основной бот запущен (PID: $MAIN_PID)"
    USERBOT_PID=""
fi

# Мониторим основной бот
while true; do
    if ! kill -0 $MAIN_PID 2>/dev/null; then
        echo "❌ Основной бот упал, перезапуск..."
        
        # Убиваем userbot если он есть
        if [ ! -z "$USERBOT_PID" ] && kill -0 $USERBOT_PID 2>/dev/null; then
            kill $USERBOT_PID
        fi
        
        # Перезапускаем основной бот
        python main.py > main.log 2>&1 &
        MAIN_PID=$!
    fi
    
    # Проверяем userbot (если он был запущен)
    if [ ! -z "$USERBOT_PID" ] && ! kill -0 $USERBOT_PID 2>/dev/null; then
        echo "⚠️ UserBot упал, перезапуск..."
        python userbot.py > userbot.log 2>&1 &
        USERBOT_PID=$!
    fi
    
    sleep 30
done
