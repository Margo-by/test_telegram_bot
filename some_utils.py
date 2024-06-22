import base64
import logging

from io import BytesIO
from soundfile import SoundFile, write

async def convert_to_ogg_opus(audio_data: bytes) -> bytes:
    try:
        with BytesIO(audio_data) as audio_file:
            with SoundFile(audio_file) as sound:
                audio_data = sound.read(dtype='float32')
                sample_rate = sound.samplerate

        with BytesIO() as ogg_opus_file:
            write(ogg_opus_file, audio_data, sample_rate, format='OGG', subtype='OPUS')
            return ogg_opus_file.getvalue()
    except Exception as e:
        logging.error(f"Exception occurred: {e}")

async def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Exception occurred: {e}")

