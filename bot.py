from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ContentType
from aiogram.fsm.storage.memory import MemoryStorage
import logging
import asyncio
import os
import subprocess
from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Загружаем переменные окружения из файла .env
load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Инициализация OpenAI клиента
client = OpenAI(OPENAI_API_KEY)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("Привет! Я бот на Aiogram.")

@dp.message(lambda message: message.content_type == ContentType.VOICE)
async def handle_voice(message: types.Message):
    voice = message.voice
    file_info = await bot.get_file(voice.file_id)
    file_path = file_info.file_path

    # Скачиваем файл
    await bot.download_file(file_path, "voice.ogg")

    # Открываем аудиофайл для чтения
    with open("voice.ogg", "rb") as audio_file:
        try:
            # Создаем транскрипцию
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            
            # Получаем ответ от OpenAI Assistant API
            response = client.chat.create(
                model="text-davinci-003",
                messages=[{"role": "user", "content": transcription}],
                max_tokens=50
            )

            # Озвучиваем полученный ответ
            audio_response = client.tts.create(
                engine="davinci",
                text=response.choices[0].text
            )
            
            # Отправляем аудио пользователю
            await message.answer_voice(audio_response)
        except AuthenticationError:
            # Обработка случая, когда запрос не проходит из-за неправильного ключа
            await message.answer("Ошибка: Не авторизован. Пожалуйста, убедитесь, что ваш API ключ OpenAI правильный.")
        except Exception as e:
            # Обработка других исключений
            await message.answer(f"Произошла ошибка: {str(e)}")

@dp.message()
async def echo(message: types.Message):
    await message.answer("Привет!")

async def main():
    # Запускаем диспетчер и бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
