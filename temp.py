import logging
from openai import AsyncOpenAI
from config import settings
from asyncio import run as asyncio_run

async def initialize_assistant()-> str:
    try:
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
        return assistant.id
    except Exception as e:
        logging.error(f"Exception occurred: {e}")



async def update_assistant(id=settings.OPENAI_API_KEY):
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        vector_store = await client.beta.vector_stores.create(name="anxiety")

        file_paths = ["anxiety.docx"]
        
        file_streams = [open(path, "rb") for path in file_paths]

        await client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
        )

        [file_stream.close() for file_stream in file_streams]

        assistant_details = await client.beta.assistants.retrieve(id)

        current_instructions = assistant_details.instructions
        additional_instructions="""
            Always look for information using the `file_search` tool before giving an answer. 
            If `file_search` does not return relevant information, proceed with your own knowledge.
        """
        updated_instructions = f"{current_instructions}\n\n{additional_instructions}"
        
        current_tools = assistant_details.tools
        new_tools = [{"type": "file_search",}]        
        updated_tools = current_tools + new_tools

        await client.beta.assistants.update(
            assistant_id=id,
            tools=updated_tools,
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id],}},
            instructions=updated_instructions,
        )
    except Exception as e:
        logging.error(f"Exception occurred: {e}")