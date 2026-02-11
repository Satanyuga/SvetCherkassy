import re
import os
import requests
import base64
from telethon import TelegramClient, events

# Конфиг
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_ID = int(os.environ.get('TG_API_ID'))
API_HASH = os.environ.get('TG_API_HASH')
GH_TOKEN = os.environ.get('GH_TOKEN')
GH_REPO = "Satanyuga/SvetCherkassy"

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def update_github(new_schedule):
    # Убираем лишние пробелы и приводим тире к одному виду, чтобы сайт не тупил
    clean_data = new_schedule.replace('–', '-').replace('—', '-').strip()
    
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    
    try:
        res = requests.get(url, headers=headers).json()
        sha = res.get('sha')
        
        content_str = f'{{"schedule": "{clean_data}"}}'
        encoded = base64.b64encode(content_str.encode()).decode()
        
        payload = {"message": "Update schedule", "content": encoded, "sha": sha}
        requests.put(url, json=payload, headers=headers)
        print(f"--- УСПЕХ: Данные отправлены на GitHub: {clean_data} ---")
    except Exception as e:
        print(f"Ошибка при обновлении: {e}")

async def check_last_messages():
    async for message in client.iter_messages('cherkassyoblenergo', limit=15):
        if message.text:
            # Ищем конкретно 4.1 и всё что после до конца строки
            match = re.search(r"4\.1:\s*([\d:.\s–\-—,]+)", message.text)
            if match:
                update_github(match.group(1).strip())
                break

@client.on(events.NewMessage())
async def handler(event):
    # Бот теперь слушает и канал, и твою личку
    if event.text:
        match = re.search(r"4\.1:\s*([\d:.\s–\-—,]+)", event.text)
        if match:
            update_github(match.group(1).strip())

with client:
    client.loop.run_until_complete(check_last_messages())
    print("Бот в строю. Жду графики...")
    client.run_until_disconnected()
