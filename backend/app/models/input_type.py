from enum import Enum

class InputType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"