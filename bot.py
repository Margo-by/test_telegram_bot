import logging

from os import remove
from uuid import uuid4
from asyncio import run as asyncio_run
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ContentType
from aiogram.types.input_file import FSInputFile

from openai_client import get_assistant_response, transcribe_audio_file, initialize_client_assistant, get_mood, get_tts_response
from config import settings
from amplitude_client import track_user_event
#from aioredis import Redis
#from redis.client import Redis

from aiogram.fsm.storage.redis  import RedisStorage  #вызывает проблемы
from aiogram.fsm.context import FSMContext
'''
 File "D:\trainee\myenv\Lib\site-packages\aiogram\fsm\storage\redis.py", line 5, in <module>
    from redis.asyncio.client import Redis
ModuleNotFoundError: No module named 'redis'
'''
from redis.asyncio import Redis, ConnectionPool
from urllib.parse import urlparse
# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Используем настройки из Pydantic
API_TOKEN = settings.TELEGRAM_TOKEN

# Разбор URL
parsed_url = urlparse(settings.REDIS_URL)
r_client = Redis(host=parsed_url.hostname, port=parsed_url.port,password=parsed_url.password)
#await r_client.aclose()

# Инициализация хранилища RedisStorage
storage = RedisStorage(r_client)

# Инициализация бота и диспетчера
bot = Bot(API_TOKEN)
dp = Dispatcher(storage=storage)


async def handle_exception(message, exception):
    logging.error(f"Exception occurred: {exception}")
    await message.answer("Sorry, an error occurred. Please try again later.")



async def send_bot_voice_response(message, response_audio_file):
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


@dp.message(lambda message: message.content_type == ContentType.PHOTO)
async def handle_photo_message(message: types.Message):

    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    file_path = file_info.file_path    
    file_extension = file_path.split('.')[-1]

    unique_filename = f"{uuid4()}.{file_extension}"
    await bot.download_file(file_path, unique_filename)  
    #делаем запрос в gpt-4o 
    mood = await get_mood(unique_filename) 
    if(mood):
        try:
            response_audio_file=await get_tts_response(mood)
            await send_bot_voice_response(message, response_audio_file)
            track_user_event('send_photo', message.from_user.id, {'mood': mood})
        except Exception as e:
            await handle_exception(message, e)
    remove(unique_filename)

@dp.message(Command("start"))
async def send_welcome_message(message: types.Message, state: FSMContext):
    
    user_message_text = "Say hello to me and describe what you can do"
    response_audio_file= await get_assistant_response(message.chat.id, user_message_text, state)
    await send_bot_voice_response(message, response_audio_file)
    track_user_event('user_started', message.from_user.id, {'command': 'start'})

@dp.message(lambda message: message.content_type == ContentType.TEXT)
async def handle_text_message(message: types.Message, state: FSMContext):
    response_audio_file=await get_assistant_response(message.chat.id, message.text,state)
    await send_bot_voice_response(message, response_audio_file)
    track_user_event('send_text', message.from_user.id, {'text': message.text})

@dp.message(lambda message: message.content_type == ContentType.VOICE)
async def handle_voice_message(message: types.Message, state: FSMContext):
    voice = message.voice
    file_info = await bot.get_file(voice.file_id)
    file_path = file_info.file_path
    unique_filename = str(uuid4())+"_voice.ogg"
    await bot.download_file(file_path, unique_filename)

    user_message_text = await transcribe_audio_file(unique_filename)
    response_audio_file=await get_assistant_response(message.chat.id, user_message_text,state)
    await send_bot_voice_response(message, response_audio_file)
    track_user_event('send_voice', message.from_user.id, {'transcription': user_message_text})
    remove(unique_filename)


async def main():
    print(f"Ping successful: {await r_client.ping()}")
    await initialize_client_assistant()  
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio_run(main())
