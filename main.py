import re
import os
import requests
import base64
from telethon import TelegramClient, events

# Параметры из Render (Environment Variables)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_ID = int(os.environ.get('TG_API_ID'))
API_HASH = os.environ.get('TG_API_HASH')
GH_TOKEN = os.environ.get('GH_TOKEN')
GH_REPO = "Satanyuga/SvetCherkassy"

# Запуск бота
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@client.on(events.NewMessage(chats='cherkassyoblenergo'))
async def handler(event):
    text = event.raw_text
    # Ищем график для группы 4.1
    match = re.search(r"4\.1:\s*([\d:–, -]+)", text)
    if match:
        new_data = match.group(1).strip()
        update_github(new_data)

def update_github(new_schedule):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    
    # Берем SHA файла для обновления
    res = requests.get(url, headers=headers).json()
    sha = res.get('sha')
    
    # Формируем JSON с новым графиком
    content_str = f'{{"schedule": "{new_schedule}"}}'
    encoded = base64.b64encode(content_str.encode()).decode()
    
    # Отправляем обновленный файл на GitHub
    payload = {
        "message": "Auto-update schedule",
        "content": encoded,
        "sha": sha
    }
    requests.put(url, json=payload, headers=headers)
    print(f"График в GitHub обновлен: {new_schedule}")

print("Бот-наблюдатель запущен и ждет новостей...")
client.run_until_disconnected()
