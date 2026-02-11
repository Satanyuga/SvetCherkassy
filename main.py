import re
import os
import requests
import base64
import threading
import time
import datetime
from flask import Flask
from telethon import TelegramClient, events

# --- ВЕБ-СЕРВЕР (Чтобы Render не заснул) ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 Адель на связи. Система мониторинга 4.1 активна."

@app.route('/ping')
def ping():
    return "✅ OK", 200

def run_flask():
    print("🌐 [LOG] Запуск веб-сервера...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

# --- НАСТРОЙКИ (Берутся из Environment Variables на Render) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_ID = int(os.environ.get('TG_API_ID'))
API_HASH = os.environ.get('TG_API_HASH')
GH_TOKEN = os.environ.get('GH_TOKEN')
GH_REPO = "Satanyuga/SvetCherkassy"

# Инициализация клиента
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def to_minutes(time_str):
    """Превращает '14:30' в 870 минут от начала дня"""
    try:
        parts = time_str.strip().split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except:
        return 0

def update_github(new_schedule):
    """Запись графика в репозиторий GitHub"""
    print(f"📡 [LOG] Обновляю данные на GitHub: {new_schedule}")
    
    # Приводим тире к стандарту и убираем лишнее
    clean_data = new_schedule.replace('–', '-').replace('—', '-').strip()
    clean_data = re.sub(r'[,\s]+$', '', clean_data)
    
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    
    try:
        # Получаем текущий файл для получения SHA
        res = requests.get(url, headers=headers).json()
        sha = res.get('sha')
        
        content_str = f'{{"schedule": "{clean_data}"}}'
        encoded = base64.b64encode(content_str.encode()).decode()
        
        payload = {
            "message": f"Update: {clean_data}",
            "content": encoded,
            "sha": sha
        }
        
        r = requests.put(url, json=payload, headers=headers)
        if r.status_code in [200, 201]:
            print("✅ [SUCCESS] GitHub обновлен успешно.")
        else:
            print(f"❌ [ERROR] Ошибка GitHub: {r.status_code} {r.text}")
    except Exception as e:
        print(f"❌ [CRITICAL] Ошибка записи: {e}")

# --- ОБРАБОТЧИК СООБЩЕНИЙ (Твоя личка) ---
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if event.is_private:
        print(f"📩 [LOG] Получено сообщение в личку!")
        
        # Регулярка: ищем всё от 4.1: до 4.2: или конца сообщения
        match = re.search(r"4\.1:\s*(.*?)(?=4\.2|$)", event.text, re.DOTALL)
        
        if match:
            data = match.group(1).strip()
            print(f"🎯 [LOG] Вырезано время для 4.1: {data}")
            update_github(data)
            await event.reply(f"✅ Принято! График обновлен: {data}")
        else:
            print("⚠️ [LOG] Не нашел метку '4.1:' в тексте")
            await event.reply("⚠️ Ошибка: В сообщении нет данных для группы 4.1")

# --- ФОНОВЫЙ МОНИТОРИНГ УВЕДОМЛЕНИЙ ---
def notification_checker():
    """Раз в минуту проверяет, не пора ли слать уведомление (логика для будущего)"""
    while True:
        # Тут можно добавить логику рассылки Пушей через внешние сервисы
        # Пока просто держим поток живым
        time.sleep(60)

if __name__ == "__main__":
    # 1. Запуск Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Запуск чекера (заглушка на будущее)
    threading.Thread(target=notification_checker, daemon=True).start()
    
    # 3. Запуск основного клиента Telegram
    print("🚀 Бот Адель запущен и готов к работе!")
    with client:
        client.run_until_disconnected()
