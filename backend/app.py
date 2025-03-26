import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect # type: ignore
from google import genai
from backend.settings import get_settings
import logging
import numpy as np
import pyaudio # type: ignore
from typing import Optional
from fastapi.staticfiles import StaticFiles # type: ignore
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more verbose logging
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

static_path = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Audio configuration
SAMPLE_RATE = 24000
CHANNELS = 1
pyaudio_instance = pyaudio.PyAudio()
audio_stream = pyaudio_instance.open(
    format=pyaudio.paInt16,
    channels=CHANNELS,
    rate=SAMPLE_RATE,
    output=True
)

class ConnectionManager:
    def __init__(self):
        self.active_connection: Optional[WebSocket] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connection = websocket
        logger.info("New WebSocket connection established")

    def disconnect(self):
        if self.active_connection:
            self.active_connection = None
            logger.info("WebSocket connection closed")

manager = ConnectionManager()

async def handle_generation(text: str, websocket: WebSocket):
    try:
        logger.debug(f"Starting generation for text: {text}")

        # Initialize Gemini client
        client = genai.Client(
            api_key=get_settings().GEMINI_API_KEY,
            http_options={"api_version": "v1alpha"}
        )

        config = {
            "generation_config": {
                "response_modalities": ["AUDIO"],
                "audio_config": {
                    "audio_encoding": "LINEAR16",
                    "sample_rate_hertz": SAMPLE_RATE,
                }
            },
            "system_instruction": "Respond only with audio."
        }

        async with client.aio.live.connect(model="models/gemini-2.0-flash-exp", config=config) as session:
            logger.debug("Gemini session established")

            # Send text input
            await session.send(input=text, end_of_turn=True)
            logger.debug(f"Sent text to Gemini: {text}")

            # Receive response
            turn = session.receive()
            async for response in turn:
                logger.debug(f"Received response: {response}")

                if response.data:  # Audio data
                    logger.debug(f"Audio data received: {len(response.data)} bytes")
                    await websocket.send_bytes(response.data)
                    audio_stream.write(response.data)

                if response.text:  # Shouldn't happen with our config
                    logger.warning(f"Unexpected text response: {response.text}")
                    await websocket.send_json({"error": "Unexpected text response"})

            logger.debug("Generation completed")

    except Exception as e:
        logger.error(f"Error in generation: {str(e)}", exc_info=True)
        await websocket.send_json({"error": str(e)})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        logger.debug("Starting WebSocket communication")
        await websocket.send_json({"status": "connected"})

        while True:
            data = await websocket.receive()
            logger.debug(f"Received data: {data}")

            if "text" in data:
                text = data["text"]
                logger.info(f"Processing text: {text}")
                await handle_generation(text, websocket)

    except WebSocketDisconnect:
        logger.info("Client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
    finally:
        manager.disconnect()
        logger.debug("WebSocket handler cleanup complete")

@app.get("/")
async def serve_index():
    from fastapi.responses import FileResponse
    index_path = static_path / "index.html"
    if not index_path.exists():
        return {"error": "Index file not found"}
    return FileResponse(index_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
