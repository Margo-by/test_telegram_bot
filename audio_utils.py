from io import BytesIO
from soundfile import SoundFile, write

async def convert_to_ogg_opus(audio_data: bytes) -> bytes:
    with BytesIO(audio_data) as audio_file:
        with SoundFile(audio_file) as sound:
            audio_data = sound.read(dtype='float32')
            sample_rate = sound.samplerate

    with BytesIO() as ogg_opus_file:
        write(ogg_opus_file, audio_data, sample_rate, format='OGG', subtype='OPUS')
        return ogg_opus_file.getvalue()