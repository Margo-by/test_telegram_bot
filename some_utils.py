import base64

from io import BytesIO
from soundfile import SoundFile, write

import os

async def convert_to_ogg_opus(audio_data: bytes) -> bytes:
    with BytesIO(audio_data) as audio_file:
        with SoundFile(audio_file) as sound:
            audio_data = sound.read(dtype='float32')
            sample_rate = sound.samplerate

    with BytesIO() as ogg_opus_file:
        write(ogg_opus_file, audio_data, sample_rate, format='OGG', subtype='OPUS')
        return ogg_opus_file.getvalue()


# Function to encode the image
async def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')