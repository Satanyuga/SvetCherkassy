import re
import os
import requests
import base64
from telethon import TelegramClient, events

# Твои секреты из Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_ID = int(os.environ.get('TG_API_ID'))
API_HASH = os.environ.get('TG_API_HASH')
GH_TOKEN = os.environ.get('GH_TOKEN')
GH_REPO = "Satanyuga/SvetCherkassy"

# Настоящая ссылка на канал
CHANNEL_URL = 'https://t.me/pat_cherkasyoblenergo'

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def update_github(new_schedule):
    # Убираем все виды тире и лишние пробелы
    clean_data = new_schedule.replace('–', '-').replace('—', '-').strip()
    
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    
    try:
        res = requests.get(url, headers=headers).json()
        sha = res.get('sha')
        
        content_str = f'{{"schedule": "{clean_data}"}}'
        encoded = base64.b64encode(content_str.encode()).decode()
        
        payload = {"message": "Auto-update schedule", "content": encoded, "sha": sha}
        requests.put(url, json=payload, headers=headers)
        print(f"--- ГУД: GitHub обновлен: {clean_data} ---")
    except Exception as e:
        print(f"Ошибка записи в репозиторий: {e}")

async def check_last_messages():
    print(f"Лезу в историю канала {CHANNEL_URL}...")
    try:
        entity = await client.get_entity(CHANNEL_URL)
        async for message in client.iter_messages(entity, limit=20):
            if message.text:
                # Ищем магические цифры 4.1
                match = re.search(r"4\.1:\s*([\d:.\s–\-—,]+)", message.text)
                if match:
                    data = match.group(1).strip()
                    update_github(data)
                    print(f"Вытянул из истории: {data}")
                    return
        print("В последних 20 постах группы 4.1 не нашел.")
    except Exception as e:
        print(f"Ошибка при поиске в истории: {e}")

@client.on(events.NewMessage(chats=CHANNEL_URL))
async def handler(event):
    if event.text:
        match = re.search(r"4\.1:\s*([\d:.\s–\-—,]+)", event.text)
        if match:
            update_github(match.group(1).strip())

with client:
    # Пытаемся обновить данные сразу при старте
    client.loop.run_until_complete(check_last_messages())
    print("Бот в засаде. Мониторим канал...")
    client.run_until_disconnected()
