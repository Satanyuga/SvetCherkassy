import re
import os
import requests
import base64
import threading
import time
import json
from flask import Flask
from telethon import TelegramClient, events

# --- ВЕБ-СЕРВЕР ---
app = Flask('')
@app.route('/')
def home(): return "Adele System Active"
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

def update_github(data_dict):
    """Отправляет весь словарь групп в data.json"""
    print(f"📡 [LOG] Обновляю GitHub...")
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    
    try:
        # Получаем SHA текущего файла
        res = requests.get(url, headers=headers).json()
        sha = res.get('sha')
        
        # Формируем JSON строку
        content_str = json.dumps(data_dict, ensure_ascii=False, indent=2)
        encoded = base64.b64encode(content_str.encode()).decode()
        
        payload = {
            "message": "Update all groups",
            "content": encoded,
            "sha": sha
        }
        
        r = requests.put(url, json=payload, headers=headers)
        if r.status_code in [200, 201]:
            print("✅ [SUCCESS] Данные всех групп обновлены!")
        else:
            print(f"❌ [ERROR] Ошибка GitHub: {r.text}")
    except Exception as e:
        print(f"❌ [CRITICAL] Сбой: {e}")

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if event.is_private:
        print("📩 [LOG] Сообщение получено. Начинаю парсинг всех групп...")
        
        # Регулярка для поиска всех групп типа 4.1: время
        # Ищет паттерн "Цифра.Цифра: всё до следующей такой же пары или конца"
        found_groups = re.findall(r"(\d\.\d):\s*(.*?)(?=\s*\d\.\d:|$)", event.text, re.DOTALL)
        
        if found_groups:
            data_to_save = {}
            for g_name, g_time in found_groups:
                clean_time = g_time.replace('–', '-').replace('—', '-').strip()
                data_to_save[g_name] = clean_time
            
            update_github(data_to_save)
            await event.reply(f"✅ Обновлено групп: {len(data_to_save)}\nЗаписал: {', '.join(data_to_save.keys())}")
        else:
            await event.reply("❌ Не нашел в тексте групп в формате '4.1: время'")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    with client:
        print("🚀 Бот запущен! Шли полный текст с группами в личку.")
        client.run_until_disconnected()
