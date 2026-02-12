import os
import re
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")

ADMIN_ID = 815422710
CHANNEL_USERNAME = "pat_cherkasyoblenergo"

DATA_FILE = "data.json"

client = TelegramClient("userbot_session", API_ID, API_HASH)


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_schedule(text):
    pattern = r"(\d\.\d):\s*(.+)"
    matches = re.findall(pattern, text)
    schedule = {}

    for queue, times in matches:
        schedule[queue] = [t.strip() for t in times.split(",")]

    return schedule


@client.on(events.NewMessage(chats=CHANNEL_USERNAME))
async def handler(event):
    text = event.raw_text

    if "1.1:" not in text:
        return

    print("📥 Найден график из канала")

    data = load_data()

    today = datetime.now().strftime("%Y-%m-%d")

    if "admin_override" in data and data["admin_override"].get("date") == today:
        print("⚠️ Используется админский приоритет")
        return

    schedule = parse_schedule(text)

    data["schedule"] = schedule
    data["last_update"] = today

    save_data(data)

    print("✅ График обновлён из канала")


async def main():
    print("🚀 Запуск UserBot")

    await client.connect()

    if not await client.is_user_authorized():
        print("❌ Сессия недействительна. Нужно создать новую.")
        return

    print("✅ UserBot авторизован")

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
