"""Display geometry and persistent camera options, independent of GTK."""
import json
import os
from pathlib import Path

DEFAULT_SETTINGS = {'width': 960, 'height': 540, 'rotation': 0, 'mirror': True}


def validate_settings(values):
    result = dict(DEFAULT_SETTINGS, **values)
    for key, minimum in [('width', 4), ('height', 4)]:
        value = result[key]
        if type(value) is not int or not minimum <= value <= 1920 or value % 4:
            raise ValueError(f'{key} must be a multiple of four between {minimum} and 1920')
    if max(result['width'],result['height']) < 320:
        raise ValueError('Output long edge must be at least 320')
    if type(result['rotation']) is not int or result['rotation'] not in (0, 90, 180, 270):
        raise ValueError('rotation must be 0, 90, 180 or 270')
    if type(result['mirror']) is not bool:
        raise ValueError('mirror must be boolean')
    return {key: result[key] for key in DEFAULT_SETTINGS}


def load_settings(path):
    try:
        return validate_settings(json.loads(Path(path).read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError):
        return dict(DEFAULT_SETTINGS)


def save_settings(path, values):
    values = validate_settings(values)
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(values, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return values


def cover_geometry(width, height, image_width, image_height):
    if min(width, height, image_width, image_height) <= 0:
        raise ValueError('Drawing dimensions must be positive')
    scale = max(width / image_width, height / image_height)
    return (width - image_width * scale) / 2, (height - image_height * scale) / 2, scale


def output_dimensions(width, height, long_edge):
    if min(width, height, long_edge) <= 0:
        raise ValueError('Output dimensions must be positive')
    scale = long_edge / max(width, height)
    return max(4, round(width * scale / 4) * 4), max(4, round(height * scale / 4) * 4)


def prepare_frame(frame, settings):
    import cv2
    rotation = settings['rotation']
    if rotation:
        frame = cv2.rotate(frame, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[rotation])
    # Resolution changes pixel density only. Crop once at display time, using
    # the window aspect, rather than cropping source and then cropping again.
    scale = min(1, 1280 / max(frame.shape[:2]))
    return cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
