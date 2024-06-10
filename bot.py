import logging

from os import remove
from uuid import uuid4
from asyncio import run as asyncio_run
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ContentType
from aiogram.types.input_file import FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage

from openai_client import get_assistant_response, transcribe_audio_file, initialize_client_assistant
from config import settings


# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Используем настройки из Pydantic
API_TOKEN = settings.TELEGRAM_TOKEN

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


async def handle_exception(message, exception):
    logging.error(f"Exception occurred: {exception}")
    await message.answer("Sorry, an error occurred. Please try again later.")


async def send_bot_voice_response(message, user_message_text):

    response_audio_file = await get_assistant_response(message.chat.id, user_message_text)
    if (response_audio_file):
        try:
            # Save the audio file to disk
            response_audio_path = str(uuid4())+"_response.ogg"
            with open(response_audio_path, "wb") as response_file:
                response_file.write(response_audio_file)

            # Send the voice message
            await bot.send_voice(message.chat.id, voice=FSInputFile(response_audio_path))

            # Clean up the saved audio file
            remove(response_audio_path)
        except Exception as e:
            await handle_exception(message, e)

@dp.message(Command("start"))
async def send_welcome_message(message: types.Message):
    user_message_text = "Say hello to me and describe what you can do"
    await send_bot_voice_response(message,user_message_text)

@dp.message(lambda message: message.content_type == ContentType.TEXT)
async def handle_text_message(message: types.Message):
    await send_bot_voice_response(message, message.text)

@dp.message(lambda message: message.content_type == ContentType.VOICE)
async def handle_voice_message(message: types.Message):
    voice = message.voice
    file_info = await bot.get_file(voice.file_id)
    file_path = file_info.file_path
    unique_filename = str(uuid4())+"_voice.ogg"
    await bot.download_file(file_path, unique_filename)

    user_message_text = await transcribe_audio_file(unique_filename)

    await send_bot_voice_response(message, user_message_text)
    remove(unique_filename)


async def main():
    await initialize_client_assistant()  # Инициализация клиента и ассистента
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio_run(main())
