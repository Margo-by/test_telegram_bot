import os
import logging
import asyncio
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ContentType
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError
import openai
import requests
import io
import soundfile as sf
import numpy as np
from aiogram.types.input_file import FSInputFile  # Изменили импорт
from config import settings  # Импортируем настройки

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Загружаем переменные окружения из файла .env
load_dotenv()

# Используем настройки из Pydantic
API_TOKEN = settings.TELEGRAM_TOKEN
OPENAI_API_KEY = settings.OPENAI_API_KEY

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Инициализация OpenAI клиента
client = OpenAI()
client2 = openai.Client()
client3 = OpenAI()

# Создание ассистента
assistant = client2.beta.assistants.create(
    name="Chat Assistant",
    instructions="You are a chat assistant. You can answer questions and engage in conversation.",
    model="gpt-4"
)

# Создание треда (только один раз)
thread = client.beta.threads.create()

async def get_assistant_response(user_message: str) -> str:
    # Добавление сообщения в тред
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message
    )
    
    # Запуск ассистента
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions="Please answer the user's message."
    )
    
    # Ожидание завершения выполнения
    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == "completed":
            break
        elif run_status.status == "failed":
            return "Run failed: " + run_status.last_error
        time.sleep(2)  # wait for 2 seconds before checking again
    
    # Получение ответов ассистента
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    
    # Возврат ответа ассистента
    for msg in messages.data:
        if msg.role == 'assistant':
            return await get_tts_response(msg.content[0].text.value)

async def convert_to_ogg_opus(audio_data: bytes) -> bytes:
    # Преобразование байтов в объект soundfile
    with io.BytesIO(audio_data) as audio_file:
        with sf.SoundFile(audio_file) as sound:
            audio_data = sound.read(dtype='float32')
            sample_rate = sound.samplerate

    # Преобразование аудио в формат OGG с кодеком Opus
    with io.BytesIO() as ogg_opus_file:
        sf.write(ogg_opus_file, audio_data, sample_rate, format='OGG', subtype='OPUS')
        return ogg_opus_file.getvalue()

async def get_tts_response(text: str) -> bytes:
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        audio_data = response.content 
        ogg_opus_data = await convert_to_ogg_opus(audio_data)
        return ogg_opus_data
    except openai.Error as e:
        logging.error(f"Error during OpenAI request: {e}")
        return None  # Возвращаем None в случае ошибки

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("Привет! Я бот на Aiogram. Вы можете отправить мне текстовое сообщение или голосовое сообщение.")

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
            user_message = transcription.text
            response_audio = await get_assistant_response(user_message)
            
            if response_audio:
                # Сохраняем аудиоданные в файл
                voice_file_path = "response_audio.ogg"
                with open(voice_file_path, "wb") as audio_file:
                    audio_file.write(response_audio)

                # Отправляем голосовое сообщение, используя путь к файлу
                await bot.send_voice(message.chat.id, voice=FSInputFile(voice_file_path))  # Используем FSInputFile

            else:
                await message.answer("Извините, не удалось получить ответ от OpenAI.")
        except Exception as e:
            await handle_exception(message, e)

@dp.message(lambda message: message.content_type == ContentType.TEXT)
async def handle_text(message: types.Message):
    user_message = message.text
    response_audio = await get_assistant_response(user_message)
    if response_audio:
        # Сохраняем аудиоданные в файл
        voice_file_path = "response_audio.ogg"
        with open(voice_file_path, "wb") as audio_file:
            audio_file.write(response_audio)

        # Отправляем голосовое сообщение, используя путь к файлу
        await bot.send_voice(message.chat.id, voice=FSInputFile(voice_file_path))  # Используем FSInputFile
    else:
        await message.answer("Извините, не удалось получить ответ от OpenAI.")

async def main():
    # Запускаем диспетчер и бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
