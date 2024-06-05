import asyncio
from openai import AsyncOpenAI

from config import settings
from audio_utils import convert_to_ogg_opus

# Инициализация AsyncOpenAI клиента
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
user_assistants = {}

async def initialize_assistant(chat_id):
    if chat_id not in user_assistants:
        assistant = await client.beta.assistants.create(
            name="Chat Assistant",
            instructions="You are a chat assistant. You can answer questions and engage in conversation.",
            model="gpt-4"
        )
        user_assistants[chat_id] = assistant
    return user_assistants[chat_id]

async def initialize_thread(chat_id, user_threads):
    if chat_id not in user_threads:
        thread = await client.beta.threads.create()
        user_threads[chat_id] = thread
    return user_threads[chat_id]

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

async def transcribe_audio_file(unique_filename):
    try:
        with open(unique_filename, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            return transcription.text
    except openai.Error as e:
        logging.error(f"Error during OpenAI transcription request: {e}")
        return None

async def get_assistant_response(thread_id: str, assistant_id: str, user_message: str) -> str:
    attempt_limit = 3
    for attempt in range(attempt_limit):
        await client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_message
        )
        run = await client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id,
            instructions="Please answer the user's message."
        )
        run_status = await client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        if run_status.status == "completed":
            break
        elif attempt == attempt_limit - 1:
            raise Exception("Failed to create assistant after multiple attempts")
        await asyncio.sleep(2)

    messages = await client.beta.threads.messages.list(thread_id=thread_id)

    for msg in messages.data:
        if msg.role == 'assistant':
            response_text = msg.content[0].text.value
            return await get_tts_response(response_text)
