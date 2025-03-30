import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles 
from google import genai
from backend.settings import get_settings
import logging
import pyaudio
from typing import Optional
import base64
import json
import numpy as np
from enum import Enum

class InputType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_RATE = 24000
CHANNELS = 1
AUDIO_OUTPUT_SAMPLE_RATE = 16000
AUDIO_INPUT_SAMPLE_RATE = 16000
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
        self.session: Optional[genai.LiveSession] = None
        self.audio_in_queue: asyncio.Queue = asyncio.Queue()
        self.input_queue: asyncio.Queue = asyncio.Queue(maxsize=5)
        self._task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connection = websocket
        logger.info("New WebSocket connection established")

    def disconnect(self):
        if self.active_connection:
            self.active_connection = None
            logger.info("WebSocket connection closed")

    async def send_realtime(self):
        """Send inputs to Gemini as they arrive"""
        while True:
            try:
                input_data = await self.input_queue.get()
                if self.session:
                    
                    if isinstance(input_data, str):  
                        
                        await self.session.send(input=input_data, end_of_turn=True)
                    elif isinstance(input_data, dict):  
                        await self.session.send(input=input_data)
            except Exception as e:
                logger.error(f"Error sending to Gemini: {e}")
                await asyncio.sleep(0.1)

    async def process_text_input(self, text: str):
        """Process text input for Gemini"""
        
        return text

    async def process_audio_input(self, audio_data, sample_rate: int):
        """Process audio input for Gemini with correct format"""
        try:
            
            if isinstance(audio_data, list):
                
                audio_array = np.array(audio_data, dtype=np.int16)
                audio_bytes = audio_array.tobytes()
            elif isinstance(audio_data, str):
                
                audio_bytes = base64.b64decode(audio_data)
            else:
                
                audio_bytes = audio_data

            
            return {
                "mimeType": "audio/pcm",  
                "data": base64.b64encode(audio_bytes).decode('utf-8')  
            }
            
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            raise

    async def process_image_input(self, image_data):
        """Process image input with complete error handling"""
        try:
            
            logger.debug(f"Received image data type: {type(image_data)}")
            
            
            if isinstance(image_data, str):
                
                if image_data.startswith('data:image'):
                    parts = image_data.split(',')
                    if len(parts) < 2:
                        raise ValueError("Invalid data URL format")
                    base64_data = parts[1]
                
                else:
                    base64_data = image_data
                
                image_bytes = base64.b64decode(base64_data)
            
            elif isinstance(image_data, bytes):
                image_bytes = image_data
                
            else:
                raise ValueError(f"Unsupported image data type: {type(image_data)}")
            
            if not image_bytes or len(image_bytes) == 0:
                raise ValueError("Empty image data received")
            
            try:
                import imghdr
                image_type = imghdr.what(None, h=image_bytes)
                if not image_type:
                    raise ValueError("Invalid image data")
            except ImportError:
                pass  

            return {
                "mimeType": f"image/{image_type or 'jpeg'}",  
                "data": base64.b64encode(image_bytes).decode('utf-8')
            }

        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}")
            raise ValueError(f"Could not process image: {str(e)}")

    async def receive_responses(self, websocket: WebSocket):
        """Receive responses from Gemini and send to client"""
        while True:
            try:
                if not self.session:
                    await asyncio.sleep(0.1)
                    continue

                turn = self.session.receive()
                async for response in turn:
                    if response.data:  
                        await websocket.send_bytes(response.data)
                        # audio_stream.write(response.data)
                    if response.text:  
                        await websocket.send_json({
                            "type": "text",
                            "data": response.text
                        })
            except Exception as e:
                logger.error(f"Error receiving from Gemini: {e}")
                await asyncio.sleep(0.1)

manager = ConnectionManager()

async def generate_audio_response(text: str, websocket: WebSocket):
    try:
        logger.debug(f"Generating audio for text: {text}")
        
        config = {
            "generation_config": {
                "response_modalities": ["AUDIO"],
                "audio_config": {
                    "audio_encoding": "LINEAR16",
                    "sample_rate_hertz": 24000,  # Match frontend
                    "chunk_size": 4096  # Add chunk size for smoother streaming
                }
            }
        }
        
        async with manager.client.aio.live.connect(model="models/gemini-2.0-flash-exp", config=config) as session:
            logger.debug("Gemini session started")
            
            await session.send(input={"text": text}, end_of_turn=True)
            logger.debug("Text sent to Gemini")
            
            turn = session.receive()
            async for response in turn:
                if not response:
                    logger.warning("Empty response received")
                    continue
                    
                if hasattr(response, 'data') and response.data:
                    logger.debug(f"Received audio data: {len(response.data)} bytes")
                    try:
                        await websocket.send_bytes(response.data)
                        audio_stream.write(response.data)
                    except Exception as e:
                        logger.error(f"Error sending audio: {str(e)}")
                
                if hasattr(response, 'text') and response.text:
                    logger.info(f"Transcript: {response.text}")
                    await websocket.send_json({"transcript": response.text})
            
            logger.debug("Generation completed")
    
    except Exception as e:
        logger.error(f"Generation error: {str(e)}", exc_info=True)
        await websocket.send_json({"error": str(e)})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    manager = ConnectionManager()  
    await manager.connect(websocket)
    
    send_task = None
    receive_task = None
    session = None
    
    try:
        await websocket.send_json({"status": "connected"})
        
        client = genai.Client(
            api_key=get_settings().GEMINI_API_KEY,
            http_options={"api_version": "v1alpha"}
        )
        
        config = {
            "generation_config": {
                "response_modalities": ["AUDIO"],
                "audio_config": {
                    "audio_encoding": "LINEAR16",
                    "sample_rate_hertz": 24000,  # Match frontend
                    "chunk_size": 4096  # Add chunk size for smoother streaming
                }
            },
            "system_instruction": (
                "You are AI-Sight, a compassionate visual assistant designed to empower visually impaired users through real-time environmental awareness. Your role is to:"
                "1. **Provide Concise, Actionable Descriptions**:"
                "- Offer clear, succinct auditory descriptions of surroundings (objects, people, text)"
                "- Prioritize essential information for navigation and safety"
                "2. **Social Interaction Support**:"
                "- Identify people when possible (if user provides consent/known contacts)"
                "- Describe facial expressions and body language"
                "3. **Text Interpretation**:"
                "- Read text naturally with context awareness"
                "- Highlight important information (dates, warnings, names)"
                "4. **Navigation Assistance**:"
                "- Give directional cues using clock positions"
                "- Note obstacles and pathways"
                "5. **Interaction Principles**:"
                "- Use natural, conversational language"
                "- Keep responses under 15 words for urgent information"
                "- Provide expanded details (30-50 words) when user requests 'Tell me more'"
                "- Always maintain a supportive, empowering tone"
                "6. **Safety First Protocol**:"
                "- Immediately prioritize and emphasize hazards"
                "- Repeat critical warnings when necessary"
                "Current Context: [This will be dynamically updated with: Location/Environment, Known People Present, User Preferences]"
            )
        }
        
        session_context = client.aio.live.connect(
            model="models/gemini-2.0-flash-exp", 
            config=config
        )
        session = await session_context.__aenter__()
        manager.session = session
        
        
        send_task = asyncio.create_task(manager.send_realtime())
        receive_task = asyncio.create_task(manager.receive_responses(websocket))
        
        while True:
            try:
                message = await websocket.receive()
                
                if message["type"] == "websocket.receive":
                    try:
                        data = json.loads(message["text"])
                        
                        if data.get("type") == InputType.TEXT and data.get("data"):
                            await manager.input_queue.put(data["data"])
                            
                        elif data.get("type") == InputType.AUDIO and data.get("data"):
                        
                            processed_audio = await manager.process_audio_input(
                                data["data"],  
                                data.get("sample_rate", AUDIO_INPUT_SAMPLE_RATE)
                            )
                            await manager.input_queue.put(processed_audio)
                            
                        elif data.get("type") == InputType.IMAGE and data.get("data"):
                            image_bytes = data["data"]
                            processed_image = await manager.process_image_input(image_bytes)
                            await manager.input_queue.put(processed_image)
                            
                    except json.JSONDecodeError:
                        logger.error("Received invalid JSON")
                        await websocket.send_json({"error": "Invalid JSON format"})
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        await websocket.send_json({"error": str(e)})
                        
                elif message["type"] == "websocket.disconnect":
                    logger.info("Client disconnected")
                    break
                    
            except WebSocketDisconnect:
                logger.info("Client disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                try:
                    await websocket.send_json({"error": str(e)})
                except:
                    break
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass
    finally:
        
        if send_task:
            send_task.cancel()
            try:
                await send_task
            except:
                pass
                
        if receive_task:
            receive_task.cancel()
            try:
                await receive_task
            except:
                pass
        
        if session:
            try:
                await session.close()
            except:
                pass
            manager.session = None
        
        manager.disconnect()
        
        try:
            await websocket.close()
        except:
            pass
            
        logger.debug("WebSocket handler cleanup complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")