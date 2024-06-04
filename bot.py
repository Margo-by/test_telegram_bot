import os
import logging
import asyncio
import io
import uuid

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ContentType
from aiogram.types.input_file import FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from openai import AsyncOpenAI
import soundfile as sf

from config import settings


# Включаем логирование
logging.basicConfig(level=logging.INFO)


# Используем настройки из Pydantic
API_TOKEN = settings.TELEGRAM_TOKEN
OPENAI_API_KEY = settings.OPENAI_API_KEY

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Инициализация AsyncOpenAI клиента
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


# Хранение тредов, ассистентов для каждого пользователя
user_threads = {}
user_assistants = {}


async def initialize_thread(chat_id):
    if chat_id not in user_threads:
        thread = await client.beta.threads.create()
        user_threads[chat_id] = thread
    return user_threads[chat_id]


async def initialize_assistant(chat_id):
    if chat_id not in user_assistants:
        assistant = await client.beta.assistants.create(
            name="Chat Assistant",
            instructions="You are a chat assistant. You can answer questions and engage in conversation.",
            model="gpt-4"
        )
        user_assistants[chat_id] = assistant
    return user_assistants[chat_id]


async def on_startup(dp):
    tasks = [initialize_assistant(chat_id) for chat_id in user_threads.keys()]
    await asyncio.gather(*tasks)


async def get_assistant_response(chat_id: int, user_message: str) -> bytes:

    thread = await initialize_thread(chat_id)
    assistant = await initialize_assistant(chat_id)

    attempt_limit = 3
    for attempt in range(attempt_limit):
        await client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )
        run = await client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant.id,
            instructions="Please answer the user's message."
        )
        run_status = await client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == "completed":
            break
        elif attempt == attempt_limit - 1:
            raise Exception("Failed to create assistant after multiple attempts")
        await asyncio.sleep(2)

    messages = await client.beta.threads.messages.list(thread_id=thread.id)

    for msg in messages.data:
        if msg.role == 'assistant':
            response_text = msg.content[0].text.value
            return await get_tts_response(response_text)


async def convert_to_ogg_opus(audio_data: bytes) -> bytes:
    with io.BytesIO(audio_data) as audio_file:
        with sf.SoundFile(audio_file) as sound:
            audio_data = sound.read(dtype='float32')
            sample_rate = sound.samplerate

    with io.BytesIO() as ogg_opus_file:
        sf.write(ogg_opus_file, audio_data, sample_rate, format='OGG', subtype='OPUS')
        return ogg_opus_file.getvalue()


async def get_tts_response(text: str) -> bytes:
    try:
        response = await client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        audio_data = response.content
        ogg_opus_data = await convert_to_ogg_opus(audio_data)
        return ogg_opus_data
    except openai.Error as e:
        logging.error(f"Error during OpenAI request: {e}")
        return None


@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("Привет! Я бот на Aiogram. Вы можете отправить мне текстовое сообщение или голосовое сообщение.")

@dp.message(lambda message: message.content_type == ContentType.VOICE)
async def handle_voice(message: types.Message):
    chat_id = message.chat.id
    voice = message.voice
    file_info = await bot.get_file(voice.file_id)
    file_path = file_info.file_path

    unique_filename = str(uuid.uuid4())+"_voice.ogg"

    await bot.download_file(file_path, unique_filename)
    try:
        with open(unique_filename, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            user_message = transcription.text
            response_audio_file = await get_assistant_response(chat_id, user_message)
            
            if response_audio_file:
                try:
                    # Сохраняем аудиофайл на диск
                    response_audio_path = str(uuid.uuid4())+"_response.ogg"
                    with open(response_audio_path, "wb") as response_file:
                        response_file.write(response_audio_file)
                    
                    # Отправляем голосовое сообщение
                    await bot.send_voice(message.chat.id, voice=FSInputFile(response_audio_path))
                    
                    # Удаляем сохраненный аудиофайл
                    os.remove(response_audio_path)
                    
                except Exception as e:
                    await handle_exception(message, e)
            else:
                await message.answer("Извините, не удалось получить ответ от OpenAI.")
    except Exception as e:
        await handle_exception(message, e)

    os.remove(unique_filename)

@dp.message(lambda message: message.content_type == ContentType.TEXT)
async def handle_text(message: types.Message):
    chat_id = message.chat.id
    user_message = message.text
    response_audio_file = await get_assistant_response(chat_id, user_message)
    if response_audio_file:
        try:
            # Save the audio file to disk
            response_audio_path = str(uuid.uuid4())+"_response.ogg"
            with open(response_audio_path, "wb") as response_file:
                response_file.write(response_audio_file)
            
            # Send the voice message
            await bot.send_voice(message.chat.id, voice=FSInputFile(response_audio_path))
            
            # Clean up the saved audio file
            os.remove(response_audio_path)
        except Exception as e:
            await handle_exception(message, e)
    else:
        await message.answer("Извините, не удалось получить ответ от OpenAI.")

async def main():
    await dp.start_polling(bot, on_startup=on_startup)


if __name__ == '__main__':
    asyncio.run(main())
