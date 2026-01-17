import os
import asyncio
import random
import math
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "8579017652:AAEDaJ19YRsEhh7eNAMnwzGv46cSznlHN1g"
ADMIN_ID = 6694772539

API_ID = 26268732
API_HASH = "c9ea3a9b4fa74e41595629490e86c627"

SESSIONS_DIR = "sessions"

STICKERS = ["👋", "😊", "🙋‍♂️", "🤝"]

DEVICES = [
    {
        "device_model": "iPhone 14 Pro",
        "system_version": "iOS 17.2",
        "app_version": "10.9",
        "lang_code": "ru"
    }
]
# ==============================================

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# хранение последних отправленных сообщений
LAST_SENT = {}


# ===== FSM =====
class AttackState(StatesGroup):
    waiting_targets = State()
    waiting_messages = State()


# ===== UTILS =====
def parse_list(text: str):
    return [x.strip() for x in text.split(",") if x.strip()]


def chunk_list(data, size):
    return [data[i:i + size] for i in range(0, len(data), size)]


def pick_message(messages, last_message):
    if len(messages) == 1:
        return messages[0]
    return random.choice([m for m in messages if m != last_message])


# ===== TELETHON =====
async def send_with_session(session_file, targets, messages):
    session_path = os.path.join(SESSIONS_DIR, session_file)
    device = random.choice(DEVICES)

    client = TelegramClient(
        session=session_path,
        api_id=API_ID,
        api_hash=API_HASH,
        device_model=device["device_model"],
        system_version=device["system_version"],
        app_version=device["app_version"],
        lang_code=device["lang_code"],
        system_lang_code=device["lang_code"]
    )

    @client.on(events.NewMessage(incoming=True))
    async def incoming_handler(event):
        sender = await event.get_sender()
        tag = f"@{sender.username}" if sender.username else sender.id
        text = event.raw_text
        time_now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        await bot.send_message(
            ADMIN_ID,
            "📩 *Получен ответ*\n\n"
            f"👤 Тег: `{tag}`\n"
            f"💬 Сообщение: `{text}`\n"
            f"⏰ Время: `{time_now}`\n"
            f"📱 Сессия: `{session_file}`",
            parse_mode="Markdown"
        )

    last_message = None

    try:
        await client.start()

        for target in targets:
            sticker = random.choice(STICKERS)
            await client.send_message(target, sticker)
            await asyncio.sleep(random.uniform(1.5, 3))

            message = pick_message(messages, last_message)
            await client.send_message(target, message)

            LAST_SENT[target] = {
                "message": message,
                "time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "session": session_file
            }

            print(f"[+] {session_file} -> {target} | {message}")

            last_message = message
            await asyncio.sleep(random.uniform(3, 5))

        # 🔒 держим соединение открытым для ответов
        await client.run_until_disconnected()

    except FloodWaitError as e:
        print(f"[!] {session_file}: FloodWait {e.seconds}")

    except Exception as e:
        print(f"[-] {session_file}: {e}")

    finally:
        await client.disconnect()


async def start_attack(targets, messages):
    sessions = [s for s in os.listdir(SESSIONS_DIR) if s.endswith(".session")]
    per_session = math.ceil(len(targets) / len(sessions))
    chunks = chunk_list(targets, per_session)

    tasks = []
    for session, chunk in zip(sessions, chunks):
        tasks.append(send_with_session(session, chunk, messages))

    await asyncio.gather(*tasks)


# ===== BOT =====
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer("🤖 Бот запущен\n/attack — начать")


@dp.message_handler(commands=["attack"])
async def attack_cmd(message: types.Message):
    await message.answer("📥 Введи теги через запятую")
    await AttackState.waiting_targets.set()


@dp.message_handler(state=AttackState.waiting_targets)
async def get_targets(message: types.Message, state: FSMContext):
    targets = parse_list(message.text)
    await state.update_data(targets=targets)
    await AttackState.waiting_messages.set()
    await message.answer("💬 Введи сообщения через запятую")


@dp.message_handler(state=AttackState.waiting_messages)
async def get_messages(message: types.Message, state: FSMContext):
    messages = parse_list(message.text)
    data = await state.get_data()

    await state.finish()
    await message.answer("🚀 Запуск")

    asyncio.create_task(start_attack(data["targets"], messages))


# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)