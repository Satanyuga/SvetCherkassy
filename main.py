import re
import os
import requests
import base64
import threading
import time
from flask import Flask
from telethon import TelegramClient, events

# --- ВЕБ-СЕРВЕР ---
app = Flask('')
@app.route('/')
def home(): return "Охрана Адель активна"
@app.route('/ping')
def ping(): return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_ID = int(os.environ.get('TG_API_ID'))
API_HASH = os.environ.get('TG_API_HASH')
GH_TOKEN = os.environ.get('GH_TOKEN')
GH_REPO = "Satanyuga/SvetCherkassy"

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def update_github(new_schedule):
    print(f"📡 [LOG] Обновляю GitHub: {new_schedule}")
    clean_data = new_schedule.replace('–', '-').replace('—', '-').strip()
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    try:
        res = requests.get(url, headers=headers).json()
        sha = res.get('sha')
        content_str = f'{{"schedule": "{clean_data}"}}'
        encoded = base64.b64encode(content_str.encode()).decode()
        payload = {"message": "Manual Update", "content": encoded, "sha": sha}
        requests.put(url, json=payload, headers=headers)
        print("✅ [SUCCESS] GitHub обновлен!")
    except Exception as e:
        print(f"❌ [ERROR] Ошибка GitHub: {e}")

# Слушаем ЛИЧНЫЕ сообщения (от тебя боту)
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if event.is_private: # Только личка
        print(f"📩 [LOG] Получено сообщение в личку!")
        # Ищем 4.1 и всё до 4.2 или конца
        match = re.search(r"4\.1:\s*(.*?)(?=4\.2|$)", event.text, re.DOTALL)
        if match:
            data = match.group(1).strip()
            print(f"🎯 [LOG] Нашел 4.1: {data}")
            update_github(data)
        else:
            print("⚠️ [LOG] В тексте не найдено '4.1:'")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    with client:
        print("🚀 Бот запущен! Шли ему текст в личку.")
        client.run_until_disconnected()
