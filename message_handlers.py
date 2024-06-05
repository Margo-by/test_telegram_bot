import os
import uuid
import logging
from aiogram.types.input_file import FSInputFile
from openai_client import initialize_assistant, initialize_thread, get_assistant_response,transcribe_audio_file
from config import settings

# Используем настройки из Pydantic
API_TOKEN = settings.TELEGRAM_TOKEN

async def handle_exception(message, exception):
    logging.error(f"Exception occurred: {exception}")
    await message.answer("Sorry, an error occurred. Please try again later.")

async def send_welcome(message, bot, user_threads):
    chat_id = message.chat.id
    user_message = "Say hello to user and describe what you can do"
   
    thread = await initialize_thread(chat_id, user_threads)
    assistant = await initialize_assistant(chat_id)

    response_audio_file = await get_assistant_response(user_threads[chat_id].id, assistant.id, user_message)
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
        await message.answer("Sorry, failed to get response from OpenAI.")

async def handle_text(message, bot, user_threads):
    chat_id = message.chat.id
    user_message = message.text

    thread = await initialize_thread(chat_id, user_threads)
    assistant = await initialize_assistant(chat_id)

    response_audio_file = await get_assistant_response(user_threads[chat_id].id, assistant.id, user_message)
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
        await message.answer("Sorry, failed to get response from OpenAI.")

async def handle_voice(message, bot, user_threads):
    chat_id = message.chat.id
    voice = message.voice
    file_info = await bot.get_file(voice.file_id)
    file_path = file_info.file_path

    unique_filename = str(uuid.uuid4())+"_voice.ogg"

    await bot.download_file(file_path, unique_filename)
    user_message = await transcribe_audio_file(unique_filename)

    if user_message:
        thread = await initialize_thread(chat_id, user_threads)
        assistant = await initialize_assistant(chat_id)

        response_audio_file = await get_assistant_response(user_threads[chat_id].id, assistant.id, user_message)
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
            await message.answer("Sorry, failed to get response from OpenAI.")
    else:
        await message.answer("Sorry, failed to transcribe audio.")

    os.remove(unique_filename)