import json
import asyncio
from contextlib import suppress
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services.connection import ConnectionManager
from ..core.transalation import SYSTEM_INSTRUCTIONS
from ..utils.audio_processing import process_audio_input
from ..utils.image_processing import process_image_input
from ..models.input_type import InputType
from ..services.audio_generator import generate_audio_response
from ..core.constant import AUDIO_INPUT_SAMPLE_RATE

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    lang = websocket.query_params.get("lang", "en")
    manager = ConnectionManager()
    await manager.connect(websocket)
    send_task = receive_task = None
    try:
        await websocket.send_json({"status": "connected"})
        # Prepare Gemini live session
        from ..core.config import API_KEY, logger
        from google import genai
        client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1alpha"})
        system_instruction = SYSTEM_INSTRUCTIONS.get(lang, SYSTEM_INSTRUCTIONS["en"] )
        config = {"generation_config": {"response_modalities": ["AUDIO"],
                                         "audio_config": {"audio_encoding": "LINEAR16",
                                                           "sample_rate_hertz": 24000,
                                                           "chunk_size": 4096}},
                  "system_instruction": system_instruction}
        session_ctx = client.aio.live.connect(model="models/gemini-2.0-flash-exp", config=config)
        manager.session = await session_ctx.__aenter__()

        # Start send/receive loops
        send_task = asyncio.create_task(manager.send_realtime())
        receive_task = asyncio.create_task(manager.receive_responses(websocket))

        # Main message loop
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.receive":
                try:
                    data = json.loads(msg.get("text", "{}"))
                    if data.get("type") == InputType.TEXT and data.get("data"):
                        await manager.input_queue.put(data["data"])
                    elif data.get("type") == InputType.AUDIO and data.get("data"):
                        processed = await process_audio_input(data["data"], AUDIO_INPUT_SAMPLE_RATE)
                        await manager.input_queue.put(processed)
                    elif data.get("type") == InputType.IMAGE and data.get("data"):
                        processed = await process_image_input(data["data"])
                        await manager.input_queue.put(processed)
                except json.JSONDecodeError:
                    await websocket.send_json({"error": "Invalid JSON format"})
                except Exception as e:
                    await websocket.send_json({"error": str(e)})
            elif msg["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup tasks and session
        for task in (send_task, receive_task):
            if task:
                task.cancel()
                with suppress(Exception): await task
        if manager.session:
            with suppress(Exception): await manager.session.close()
        manager.disconnect()
        with suppress(Exception): await websocket.close()