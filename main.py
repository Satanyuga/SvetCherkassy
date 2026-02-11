import re
import os
import requests
import base64
import threading
import time
from flask import Flask
from telethon import TelegramClient, events

# --- СЕРВЕР-ПИНГАТОР ---
app = Flask('')

@app.route('/')
def home():
    return "🐺 Йеннифэр следит за светом"

@app.route('/ping')
def ping():
    return "✅ PONG", 200

def run_flask():
    # Запускаем на порту, который дает Render, или 10000 по умолчанию
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

def pinger():
    while True:
        time.sleep(300) # Пинг каждые 5 минут
        try:
            # Стучимся сами к себе, чтобы не уснуть
            host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
            if host:
                requests.get(f"https://{host}.onrender.com/ping")
                print("✨ Пинг прошел успешно")
        except:
            pass

# --- ТЕЛЕГРАМ БОТ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_ID = int(os.environ.get('TG_API_ID'))
API_HASH = os.environ.get('TG_API_HASH')
GH_TOKEN = os.environ.get('GH_TOKEN')
GH_REPO = "Satanyuga/SvetCherkassy"
CHANNEL_URL = 'https://t.me/pat_cherkasyoblenergo'

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def update_github(new_schedule):
    # Очистка от мусора, но сохранение всех цифр
    clean_data = new_schedule.replace('–', '-').replace('—', '-').strip()
    
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    
    try:
        # 1. Получаем SHA
        res = requests.get(url, headers=headers).json()
        sha = res.get('sha')
        
        # 2. Записываем
        content_str = f'{{"schedule": "{clean_data}"}}'
        encoded = base64.b64encode(content_str.encode()).decode()
        
        payload = {"message": "Update schedule", "content": encoded, "sha": sha}
        requests.put(url, json=payload, headers=headers)
        print(f"🔥 ГРАФИК ЗАПИСАН: {clean_data}")
    except Exception as e:
        print(f"Ошибка GitHub: {e}")

def parse_text(text):
    # Ищем "4.1" (с двоеточием или без) и берем ВСЮ строку до конца абзаца
    # Флаг re.MULTILINE позволяет искать по строкам
    match = re.search(r"^.*?4\.1[:\.]?\s*(.*)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None

async def check_history():
    print("🔮 Сканирую историю сообщений...")
    try:
        entity = await client.get_entity(CHANNEL_URL)
        # Проверяем последние 30 сообщений, чтобы наверняка найти график
        async for message in client.iter_messages(entity, limit=30):
            if message.text:
                data = parse_text(message.text)
                if data:
                    print(f"Нашла актуальный график: {data}")
                    update_github(data)
                    return
        print("В последних сообщениях графика для 4.1 не найдено.")
    except Exception as e:
        print(f"Ошибка чтения истории: {e}")

@client.on(events.NewMessage(chats=CHANNEL_URL))
async def handler(event):
    if event.text:
        data = parse_text(event.text)
        if data:
            update_github(data)

if __name__ == "__main__":
    # Запуск сервера в отдельном потоке
    threading.Thread(target=run_flask).start()
    # Запуск пингатора
    threading.Thread(target=pinger).start()
    
    with client:
        client.loop.run_until_complete(check_history())
        client.run_until_disconnected()
