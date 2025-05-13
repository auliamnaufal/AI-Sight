import base64
import numpy as np
import logging

logger = logging.getLogger(__name__)

async def process_audio_input(audio_data, max_size_bytes: int = 2 * 1024 * 1024):
    """
    Convert raw audio (list, base64 string, or bytes) to a dict payload.
    """
    try:
        if isinstance(audio_data, list):
            audio_array = np.array(audio_data, dtype=np.int16)
            audio_bytes = audio_array.tobytes()
        elif isinstance(audio_data, str):
            audio_bytes = base64.b64decode(audio_data)
        else:
            audio_bytes = audio_data

        if len(audio_bytes) > max_size_bytes:
            raise ValueError("Audio too large")

        return {
            "mimeType": "audio/pcm",
            "data": base64.b64encode(audio_bytes).decode('utf-8')
        }
    except Exception as e:
        logger.error(f"Audio processing error: {e}")
        raise ValueError("Invalid audio data format")