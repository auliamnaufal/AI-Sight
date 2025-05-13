import asyncio
from typing import Optional
from fastapi import WebSocket
from google import genai
from ..core.config import logger, API_KEY
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

class ConnectionManager:
    """
    Manages a single WebSocket connection and Gemini live session.
    """
    def __init__(self):
        self.active_connection: Optional[WebSocket] = None
        self.session: Optional[genai.LiveSession] = None
        self.input_queue: asyncio.Queue = asyncio.Queue(maxsize=5)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connection = websocket
        logger.info("WebSocket connection established")

    def disconnect(self):
        self.active_connection = None
        logger.info("WebSocket connection closed")

    async def send_realtime(self):
        """Send queued inputs to Gemini as they arrive."""
        while True:
            try:
                input_data = await self.input_queue.get()
                if self.session:
                    if isinstance(input_data, str):
                        await self.session.send(input=input_data, end_of_turn=True)
                    else:
                        await self.session.send(input=input_data)
            except asyncio.CancelledError:
                # Task was cancelled, exit loop cleanly
                logger.info("send_realtime task cancelled, exiting loop")
                break
            except Exception as e:
                logger.error(f"Error sending to Gemini: {e}")
                await asyncio.sleep(0.1)

    async def receive_responses(self, websocket: WebSocket):
        """Receive responses from Gemini and forward to client."""
        while True:
            try:
                if not self.session:
                    await asyncio.sleep(0.1)
                    continue
                turn = self.session.receive()
                async for response in turn:
                    if response.data:
                        await websocket.send_bytes(response.data)
                    if response.text:
                        await websocket.send_json({"type": "text", "data": response.text})
                        
            except ConnectionClosedOK:
                logger.info("Gemini session closed normally (1000)")
                break
            except ConnectionClosedError as e:
                if e.code == 1011:
                    logger.error("Gemini session internal error (1011): Deadline expired before operation could complete.")
                else:
                    logger.error(f"WebSocket closed with code {e.code}: {e.reason}")
                break
            except Exception as e:
                logger.error(f"Error receiving from Gemini: {e}")
                await asyncio.sleep(0.1)