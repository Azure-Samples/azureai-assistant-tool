# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import io, re
from PIL import Image
from azure.ai.assistant.management.logger_module import logger


def _extract_image_urls(message: str) -> list:
    urls = re.findall(r'(https?://\S+)', message)
    image_urls = [url for url in urls if url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
    return image_urls

def _resize_image(image_data: bytes, target_width: float, target_height: float) -> bytes:
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            new_width = int(img.width * target_width)
            new_height = int(img.height * target_height)
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            resized_img.save(buffer, format="PNG")
            return buffer.getvalue()
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        return None

def _save_image(image_data: bytes, file_path: str) -> str:
    try:
        with open(file_path, 'wb') as f:
            f.write(image_data)
        return file_path
    except Exception as e:
        logger.error(f"Error saving image: {e}")
        return None
