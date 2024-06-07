import logging
from asyncio import sleep as asyncio_sleep
from openai import AsyncOpenAI, OpenAIError

from config import settings
from audio_utils import convert_to_ogg_opus

# Хранение тредов для каждого пользователя
user_threads = {}

# Глобальные переменные для хранения клиента и ассистента
client = None
assistant = None


async def initialize_client_assistant():
    global client, assistant
    try:
        # Инициализация AsyncOpenAI клиента
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        assistant = await client.beta.assistants.create(
            name="Chat Assistant",
            instructions="You are a chat assistant. You can answer questions and engage in conversation.",
            model="gpt-4"
        )
    except OpenAIError as e:
        logging.error(f"Exception occurred: {e}")

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
    except OpenAIError as e:
        logging.error(f"Error while tts: {e}")
        return None

async def transcribe_audio_file(unique_filename):
    try:
        with open(unique_filename, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            return transcription.text
    except OpenAIError as e:
        logging.error(f"Error while transcribe audio file: {e}")
        return None

async def get_assistant_response(chat_id, user_message: str) -> str:
    if chat_id not in user_threads:
        thread = await client.beta.threads.create()
        user_threads[chat_id] = thread
    else:
        thread = user_threads[chat_id]
    try:
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
            if run.status == "completed":
                break
            elif attempt == attempt_limit - 1:
                raise Exception("Failed to create assistant after multiple attempts")
            await asyncio_sleep(2)

        messages = await client.beta.threads.messages.list(thread_id=thread.id)

        for msg in messages.data:
            if msg.role == 'assistant':
                response_text = msg.content[0].text.value
                return await get_tts_response(response_text)

    except Exception as e:
        logging.error(f"Error while getting assistant response: {e}")
        return None