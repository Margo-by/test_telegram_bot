import logging
import json

from asyncio import sleep as asyncio_sleep
from openai import AsyncOpenAI, OpenAIError
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import State, StatesGroup

from config import settings
from some_utils import convert_to_ogg_opus, encode_image
from database import save_user_value

# Глобальные переменные для хранения клиента и ассистента
client = None
assistant = None

class ThreadId(StatesGroup):
    id = State()

async def initialize_client_assistant():
    global client, assistant
    try:
        # Инициализация AsyncOpenAI клиента
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        assistant = await client.beta.assistants.create(
            name="Chat Assistant",
            instructions = """
                You are the chat assistant. You can answer questions and participate in the conversation. 
                Analyze the user messages and try to identify the user's key life values based on your
                communication. If any values are found, then call the save_value function. Don't forget 
                to continue your ordinary dialogue with the user after you call save_value function.
            """,
            model="gpt-4o",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "save_value",
                        "description": "Validate and save the identified key life values",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "values": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "The list of key life values identified in the user's message"
                                }
                            },
                            "required": ["values"]
                        }
                    }
                }
            ]
        )

        # Create a vector store 
        vector_store = await client.beta.vector_stores.create(name="anxiety")
        # Ready the files for upload
        file_paths = ["anxiety.docx"]
        file_streams = [open(path, "rb") for path in file_paths]

        # Use the upload and poll SDK helper to upload the files, add them to the vector store,
        # and poll the status of the file batch for completion.
        file_batch = await client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
        )

        # You can print the status and the file counts of the batch to see the result of this operation.
        #print(file_batch.status)
        #print(file_batch.file_counts)
        assistant_details = await client.beta.assistants.retrieve(assistant.id)
        current_instructions = assistant_details.instructions
        additional_instructions= """
            if the user asks a question about anxiety, then use the file_search
            function to find the answer, when sending the answer to the user,
            always add the file name after the quoted text
        """
        updated_instructions = f"{current_instructions}\n\n{additional_instructions}"
        current_tools = assistant_details.tools
        new_tools = [
            {
                "type": "file_search",
            }
        ]        
        updated_tools = current_tools + new_tools
        assistant = await client.beta.assistants.update(
            assistant_id=assistant.id,
            tools=updated_tools,
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
            instructions=updated_instructions,
        )
    except OpenAIError as e:
        logging.error(f"Exception occurred: {e}")



async def get_mood(file_path):
    # Getting the base64 string
    base64_image = await encode_image(file_path)
    try:
        response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
            "role": "user",
            "content": [
                {
                "type": "text",
                "text": "determine the mood from the photo, return only the type of mood in a few words without explanatory comments"
                },
                {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
                }
            ]
            }
        ],
        max_tokens=300,
        )

        content = response.choices[0].message.content
        return str(content)
    except Exception as e:
        logging.error("Failed to get mood:", e)
        return None
    
async def get_assistant_response(chat_id, user_message: str, state: FSMContext) -> str:
    # Получаем текущее состояние пользователя
    data = await state.get_data()    
    # Получаем значение поля 'id' из данных состояния
    thread_id = data.get('id')
    # Если нет thread_id в состоянии, создаем новый поток
    if not thread_id:
        try:
            thread = await client.beta.threads.create()
            thread_id = thread.id
            await state.update_data(id=thread_id)
        except Exception as e:
            logging.error(f"Failed to create thread for chat_id {chat_id}: {e}")
            return None
    try:
        attempt_limit = 3
        for attempt in range(attempt_limit):
            await client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_message
            )
            run = await client.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=assistant.id
            )
            if run.status == 'requires_action':
                tool_outputs = []
                userid_and_values = []
                for tool in run.required_action.submit_tool_outputs.tool_calls:
                    value_dict = json.loads(tool.function.arguments)
                    values = value_dict.get('values', [])
                    tool_outputs.append({
                        "tool_call_id": tool.id,
                        "output": tool.function.arguments
                    })
                    #отправятся на валидацию
                    userid_and_values.append({
                        "values": values,
                        "chat_id": chat_id
                    })
                if tool_outputs:
                    try:
                        run = await client.beta.threads.runs.submit_tool_outputs_and_poll(
                            thread_id=thread_id,
                            run_id=run.id,
                            tool_outputs=tool_outputs
                        )
                    except Exception as e:
                        logging.error("Failed to submit tool outputs:", e)
                else:
                    logging.info("No tool outputs to submit.")
                #проверяем значения на корректность и сохраняем в бд, если корректны
                await validate_values(userid_and_values)
            if run.status == "completed":
                break
                
            # Если превышен лимит попыток, генерируем исключение
            elif attempt == attempt_limit - 1:
                raise Exception("Failed to create assistant after multiple attempts")
            await asyncio_sleep(2)
        messages = await client.beta.threads.messages.list(thread_id=thread_id)

        # Поиск ответа ассистента в сообщениях
        for msg in messages.data:
            if msg.role == 'assistant':
                response_text = msg.content[0].text.value
                return await get_tts_response(response_text)

    except Exception as e:
        logging.error(f"Error while getting assistant response: {e}")
        return None

async def validate_values(userid_and_values):
    for item in userid_and_values:
        for value in item['values']:
            is_valid = await is_life_value(value)
            if is_valid:
                logging.info(f"Chat ID: {item['chat_id']}, Value: {value}")
                #сохраняем в бд корректную жизеннную ценность
                await save_user_value(user_id=item['chat_id'], value=value)
            else:
                logging.info(f"Value '{value}' is not a key life value for user ID {item['chat_id']}")
    logging.info("Values saved to database")

async def is_life_value(value: str) -> bool:
    messages=[
        {"role": "user", "content": f"Is '{value}' a key life value? Answer only true or false."}
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "is_life_value",
                "description": "Check if the given value is a key life value",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "true_false": {
                            "type": "string",
                            "description": """
                                    Contains only 'true' or 'false' string.                             
                                    This string represents the answer to the user's question is whether the
                                    provided value is a valid life value or contains nonsense.
                                    Contains 'true' means values are defined correctly, do not contain nonsense. 
                                    Contains 'false' — the value is determined incorrectly or the string is empty.
                                    The true_false should be returned in plain text, not in JSON.
                                    """,
                        }
                    },
                    "required": ["true_false"],
                },
            }
        }
    ]
    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=tools
        )
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            for tool_call in tool_calls:
                if tool_call.function:
                    function_arguments = json.loads(tool_call.function.arguments)
                    true_false_value = function_arguments.get('true_false')
        return true_false_value in ["true"]
    except Exception as e:
        logging.error(f"Error while checking if '{value}' is a key life value: {e}")
        return False


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
    


