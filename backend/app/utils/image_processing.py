import base64
import logging

logger = logging.getLogger(__name__)

async def process_image_input(image_data):
    """
    Convert raw image (data URL, base64 string, or bytes) to a dict payload.
    """
    try:
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

        if not image_bytes:
            raise ValueError("Empty image data received")

        # Optionally verify image type
        try:
            import imghdr
            image_type = imghdr.what(None, h=image_bytes)
            if not image_type:
                raise ValueError("Invalid image data")
        except ImportError:
            image_type = None

        return {
            "mimeType": f"image/{image_type or 'jpeg'}",
            "data": base64.b64encode(image_bytes).decode('utf-8')
        }
    except Exception as e:
        logger.error(f"Image processing failed: {e}")
        raise ValueError(f"Could not process image: {e}")