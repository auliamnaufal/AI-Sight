import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# API key for Gemini
API_KEY = os.getenv("API_KEY")

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)