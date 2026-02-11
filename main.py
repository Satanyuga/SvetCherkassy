import re
import os
import requests
import base64
from telethon import TelegramClient, events

# Настройки из Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_ID = int(os.environ.get('TG_API_ID'))
API_HASH = os.environ.get('TG_API_HASH')
GH_TOKEN = os.environ.get('GH_TOKEN')
GH_REPO = "Satanyuga/SvetCherkassy"

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def update_github(new_schedule):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    res = requests.get(url, headers=headers).json()
    sha = res.get('sha')
    content_str = f'{{"schedule": "{new_schedule}"}}'
    encoded = base64.b64encode(content_str.encode()).decode()
    payload = {"message": "Update schedule", "content": encoded, "sha": sha}
    requests.put(url, json=payload, headers=headers)
    print(f"--- ГРАФИК ОБНОВЛЕН: {new_schedule} ---")

async def check_last_messages():
    print("Проверяю последние сообщения в канале...")
    async for message in client.iter_messages('cherkassyoblenergo', limit=10):
        if message.text:
            match = re.search(r"4\.1:\s*([\d:–, -]+)", message.text)
            if match:
                data = match.group(1).strip()
                update_github(data)
                break

@client.on(events.NewMessage(chats='cherkassyoblenergo'))
async def handler(event):
    match = re.search(r"4\.1:\s*([\d:–, -]+)", event.raw_text)
    if match:
        update_github(match.group(1).strip())

# При запуске проверяем историю, а потом слушаем новые посты
with client:
    client.loop.run_until_complete(check_last_messages())
    print("Бот запущен и мониторит канал в реальном времени!")
    client.run_until_disconnected()
