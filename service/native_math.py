"""Optional exact image kernels; NumPy/OpenCV remain the portable fallback."""
import ctypes
from pathlib import Path

import numpy as np

try:
    _lib = ctypes.CDLL(str(Path(__file__).with_name('_image_kernels.so')))
except OSError:
    _lib = None
AVAILABLE = _lib is not None
_fp = ctypes.POINTER(ctypes.c_float)
_up = ctypes.POINTER(ctypes.c_uint8)
if AVAILABLE:
    _lib.sharpen_exact.argtypes = [_fp, _fp, _up, ctypes.c_size_t]
    _lib.sharpen_exact.restype = None
    _lib.quarter_blend_exact.argtypes = [_up, _up, ctypes.c_size_t]
    _lib.quarter_blend_exact.restype = None


def sharpen_exact(source, blur):
    """Consume writable float32 arrays, preserving the original operation order."""
    if source.dtype != np.float32 or blur.dtype != np.float32 or source.shape != blur.shape:
        raise ValueError('Expected equally shaped float32 arrays')
    if AVAILABLE and source.flags.c_contiguous and blur.flags.c_contiguous:
        output = np.empty(source.shape, np.uint8)
        _lib.sharpen_exact(source.ctypes.data_as(_fp), blur.ctypes.data_as(_fp),
                           output.ctypes.data_as(_up), source.size)
        return output
    np.subtract(source, blur, out=blur)
    np.multiply(source, 0.98, out=source)
    np.add(source, 4, out=source)
    np.multiply(blur, 0.22, out=blur)
    np.add(source, blur, out=source)
    np.clip(source, 0, 255, out=source)
    return source.astype(np.uint8)


def quarter_blend_exact(target, source):
    """Blend uint8 LAB arrays with truncation, preserving target ownership."""
    if target.dtype != np.uint8 or source.dtype != np.uint8 or target.shape != source.shape:
        raise ValueError('Expected equally shaped uint8 arrays')
    if AVAILABLE and target.flags.c_contiguous and source.flags.c_contiguous:
        _lib.quarter_blend_exact(target.ctypes.data_as(_up), source.ctypes.data_as(_up), target.size)
        return target
    import cv2
    return cv2.addWeighted(target, 0.25, source, 0.75, 0, dtype=cv2.CV_32F).astype(np.uint8)
