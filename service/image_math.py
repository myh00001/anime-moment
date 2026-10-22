"""Exact float32 conversions without full-image arithmetic temporaries."""
import numpy as np


def normalized_pixels(image):
    value = image.astype(np.float32)
    np.divide(value, 127.5, out=value)
    np.subtract(value, 1, out=value)
    return value


def decoded_pixels_owned(value):
    """Consume a writable float32 model output/view; return uint8 pixels."""
    np.add(value, 1, out=value)
    np.multiply(value, 127.5, out=value)
    np.clip(value, 0, 255, out=value)
    return value.astype(np.uint8)


def luminance_lut(low, high):
    """Map every uint8 luminance with the original float32 contrast formula."""
    values = np.arange(256, dtype=np.float32)
    if high - low <= 40:
        return values.astype(np.uint8)
    light = np.clip((values - low) * 224 / (high - low) + 16, 0, 255)
    return np.uint8(np.clip(values * 0.35 + light * 0.65, 0, 255))
