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
    return "🤖 Адель на страже твоего света"

@app.route('/ping')
def ping():
    return "✅ OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

def pinger():
    while True:
        time.sleep(300)
        try:
            host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
            if host:
                requests.get(f"https://{host}.onrender.com/ping")
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
    # Убираем только мусорные тире, оставляем все запятые и пробелы
    clean_data = new_schedule.replace('–', '-').replace('—', '-').strip()
    
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    
    try:
        res = requests.get(url, headers=headers).json()
        sha = res.get('sha')
        
        content_str = f'{{"schedule": "{clean_data}"}}'
        encoded = base64.b64encode(content_str.encode()).decode()
        
        payload = {"message": "Full schedule update", "content": encoded, "sha": sha}
        requests.put(url, json=payload, headers=headers)
        print(f"--- ГРАФИК ОБНОВЛЕН ПОЛНОСТЬЮ: {clean_data} ---")
    except Exception as e:
        print(f"Ошибка GitHub: {e}")

def parse_full_schedule(text):
    # Ищем 4.1 и забираем ВСЁ до конца строки, включая запятые и пробелы
    # Регулярка теперь видит всю твою последовательность времени
    match = re.search(r"4\.1:\s*([\d:,\s\-\–\—]+)", text)
    if match:
        return match.group(1).strip()
    return None

async def check_history():
    try:
        entity = await client.get_entity(CHANNEL_URL)
        async for message in client.iter_messages(entity, limit=10):
            if message.text:
                data = parse_full_schedule(message.text)
                if data:
                    update_github(data)
                    return
    except Exception as e:
        print(f"Ошибка истории: {e}")

@client.on(events.NewMessage(chats=CHANNEL_URL))
async def handler(event):
    if event.text:
        data = parse_full_schedule(event.text)
        if data:
            update_github(data)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    threading.Thread(target=pinger).start()
    with client:
        client.loop.run_until_complete(check_history())
        client.run_until_disconnected()
