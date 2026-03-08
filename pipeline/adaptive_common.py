"""Shared helpers for adaptive encrypt/decrypt pipelines."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import numpy as np


def b64_encode_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64_decode_bytes(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def load_image(image_path: str) -> np.ndarray:
    try:
        import cv2
    except ImportError:
        cv2 = None

    if cv2 is not None:
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Unable to read image: {image_path}")
        return image

    from PIL import Image

    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        arr = np.array(rgb, dtype=np.uint8)
    return arr[..., ::-1].copy()


def save_image(image_path: str, image: np.ndarray) -> None:
    try:
        import cv2
    except ImportError:
        cv2 = None

    output_path = Path(image_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if cv2 is not None:
        if not cv2.imwrite(str(output_path), image):
            raise OSError(f"Failed to write image: {image_path}")
        return

    from PIL import Image

    rgb = image[..., ::-1]
    Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(str(output_path))


def pad_to_square(image: np.ndarray) -> tuple[np.ndarray, int, int]:
    if image.ndim not in {2, 3}:
        raise ValueError("Expected 2D or 3D image array.")

    height, width = image.shape[:2]
    side = max(height, width)

    if image.ndim == 2:
        padded = np.zeros((side, side), dtype=image.dtype)
        padded[:height, :width] = image
    else:
        channels = image.shape[2]
        padded = np.zeros((side, side, channels), dtype=image.dtype)
        padded[:height, :width, :] = image

    return padded, height, width


def unpad_from_square(image: np.ndarray, original_height: int, original_width: int) -> np.ndarray:
    return image[:original_height, :original_width].copy()


def image_sha256_digest(image: np.ndarray) -> bytes:
    """Hash image content with shape/dtype context for deterministic binding."""

    if image is None or image.size == 0:
        raise ValueError("Input image is empty.")
    context = f"{image.shape}|{image.dtype}".encode("utf-8")
    return hashlib.sha256(context + image.tobytes()).digest()
