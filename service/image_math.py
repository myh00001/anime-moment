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
