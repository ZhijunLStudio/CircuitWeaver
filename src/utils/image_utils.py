import base64
from PIL import Image
import io

def resize_and_encode_image(image_path: str, max_dim: int) -> str:
    """
    Resizes an image to fit within max_dim on its longest side,
    maintains aspect ratio, and returns a base64 encoded string.
    """
    try:
        with Image.open(image_path) as img:
            # Preserve transparency if exists
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGBA")
                output_format = "PNG"
            else:
                img = img.convert("RGB")
                output_format = "JPEG"

            width, height = img.size
            if width > max_dim or height > max_dim:
                if width > height:
                    new_width = max_dim
                    new_height = int(height * (max_dim / width))
                else:
                    new_height = max_dim
                    new_width = int(width * (max_dim / height))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            buffered = io.BytesIO()
            img.save(buffered, format=output_format)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except FileNotFoundError:
        print(f"Warning: Image file not found at {image_path}")
        return ""
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return ""