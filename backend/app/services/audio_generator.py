import logging
from google import genai
from fastapi import WebSocket
from ..core.config import API_KEY

logger = logging.getLogger(__name__)

async def generate_audio_response(text: str, websocket: WebSocket):
    """Generate and stream audio from text via Gemini."""
    try:
        logger.debug(f"Generating audio for text: {text}")
        config = {
            "generation_config": {
                "response_modalities": ["AUDIO"],
                "audio_config": {
                    "audio_encoding": "LINEAR16",
                    "sample_rate_hertz": 24000,
                    "chunk_size": 4096
                }
            }
        }
        client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1alpha"})
        async with client.aio.live.connect(model="models/gemini-2.0-flash-exp", config=config) as session:
            await session.send(input={"text": text}, end_of_turn=True)
            turn = session.receive()
            async for response in turn:
                if response.data:
                    await websocket.send_bytes(response.data)
                if response.text:
                    await websocket.send_json({"transcript": response.text})
    except Exception as e:
        logger.error(f"Audio generation error: {e}", exc_info=True)
        await websocket.send_json({"error": str(e)})