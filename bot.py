import logging

from asyncio import run as asyncio_run
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ContentType
from aiogram.types.input_file import FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage

from openai_client import initialize_assistant
from message_handlers import send_welcome, handle_voice, handle_text
from config import settings

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Используем настройки из Pydantic
API_TOKEN = settings.TELEGRAM_TOKEN

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Хранение тредов для каждого пользователя
user_threads = {}


@dp.message(Command("start"))
async def send_welcome_message(message: types.Message):
    await send_welcome(message, bot, user_threads)

@dp.message(lambda message: message.content_type == ContentType.VOICE)
async def handle_voice_message(message: types.Message):
    await handle_voice(message, bot, user_threads)

@dp.message(lambda message: message.content_type == ContentType.TEXT)
async def handle_text_message(message: types.Message):
    await handle_text(message, bot, user_threads)

async def on_startup(dp):
    tasks = [initialize_assistant(chat_id) for chat_id in user_threads.keys()]
    await asyncio.gather(*tasks)

async def main():
    await dp.start_polling(bot, on_startup=on_startup)

if __name__ == '__main__':
    asyncio_run(main())
