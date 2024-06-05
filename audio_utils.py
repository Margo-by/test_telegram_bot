import io
import soundfile as sf

async def convert_to_ogg_opus(audio_data: bytes) -> bytes:
    with io.BytesIO(audio_data) as audio_file:
        with sf.SoundFile(audio_file) as sound:
            audio_data = sound.read(dtype='float32')
            sample_rate = sound.samplerate

    with io.BytesIO() as ogg_opus_file:
        sf.write(ogg_opus_file, audio_data, sample_rate, format='OGG', subtype='OPUS')
        return ogg_opus_file.getvalue()
