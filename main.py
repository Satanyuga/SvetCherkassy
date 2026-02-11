import re
import os
import requests
import base64
from telethon import TelegramClient, events

# Берем данные из настроек Render (Environment Variables)
API_ID = int(os.environ.get('TG_API_ID'))
API_HASH = os.environ.get('TG_API_HASH')
GH_TOKEN = os.environ.get('GH_TOKEN')
GH_REPO = os.environ.get('GH_REPO') # Формат: логин/репозиторий

client = TelegramClient('anon', API_ID, API_HASH)

@client.on(events.NewMessage(chats='cherkassyoblenergo'))
async def handler(event):
    text = event.raw_text
    # Магия: ищем только строку для 4.1, игнорируя весь спам вокруг
    match = re.search(r"4\.1:\s*([\d:–, -]+)", text)
    
    if match:
        schedule_data = match.group(1).strip()
        print(f"Нашла график: {schedule_data}")
        update_github(schedule_data)

def update_github(new_schedule):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    
    # 1. Получаем SHA файла (нужен для перезаписи)
    res = requests.get(url, headers=headers).json()
    sha = res.get('sha')
    
    # 2. Формируем новый JSON
    content_str = f'{{"schedule": "{new_schedule}"}}'
    encoded = base64.b64encode(content_str.encode()).decode()
    
    # 3. Отправляем на GitHub
    payload = {
        "message": "Обновление графика 4.1",
        "content": encoded,
        "sha": sha
    }
    requests.put(url, json=payload, headers=headers)
    print("GitHub обновлен!")

print("Сервер запущен и ждет новостей от Облэнерго...")
client.start()
client.run_until_disconnected()
