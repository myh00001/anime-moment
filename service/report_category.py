"""Local original-photo garment classification; model assets are installed separately.

YOLOX locates the largest visible person; FashionSigLIP compares that person's
original pixels with fixed garment text embeddings. Scores are similarities,
not calibrated probabilities. This module makes no color, identity or pose claims.
"""
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

LABELS = ('shirt', 't-shirt', 'sweater', 'cardigan', 'jacket', 'coat',
          'hoodie', 'vest', 'dress', 'jumpsuit', 'cape')
_engine = None
_lock = threading.Lock()


def asset_folder(root=None):
    return Path(root or Path(__file__).resolve().parent)/'local-vlm/report-category'


def available(root=None):
    folder = asset_folder(root)
    try:
        manifest = json.loads((folder/'manifest.json').read_text())
        return (manifest.get('validated') is True and manifest.get('schema') == 1
                and all((folder/name).is_file() for name in
                        ('person.onnx', 'vision.onnx', 'categories.npz')))
    except (OSError, ValueError):
        return False


def person_box(detections, width, height, scale, grids, strides):
    import numpy as np
    scores = detections[:, 4]*detections[:, 5]  # COCO class 0: person
    indices = np.where(scores > .35)[0]
    if not len(indices):
        return None
    centers = (detections[indices, :2]+grids[indices])*strides[indices]
    sizes = np.exp(detections[indices, 2:4])*strides[indices]
    boxes = np.concatenate([centers-sizes/2, sizes], axis=1)/scale
    i = int(np.argmax(np.minimum(boxes[:, 2], width)*np.minimum(boxes[:, 3], height)))
    x, y, w, h = boxes[i]
    pad = .04*max(w, h)
    box = [max(0, int(x-pad)), max(0, int(y-pad)),
           min(width, int(x+w+pad)), min(height, int(y+h+pad))]
    return box if box[2] > box[0] and box[3] > box[1] else None


class CategoryReporter:
    def __init__(self, root=None):
        import numpy as np
        root = Path(root or Path(__file__).resolve().parent)
        folder = asset_folder(root)
        manifest = json.loads((folder/'manifest.json').read_text())
        if not available(root):
            raise ValueError('Unvalidated report category assets')
        for name in ('person.onnx', 'vision.onnx', 'categories.npz'):
            if hashlib.sha256((folder/name).read_bytes()).hexdigest() != manifest['sha256'][name]:
                raise ValueError('Report category asset checksum mismatch')
        # Reuse the ARM runtime already installed for gesture detection.
        sys.path.insert(0, str(root/'local-vlm/gesture-ort/runtime'))
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 6
        options.inter_op_num_threads = 1
        options.add_session_config_entry('session.intra_op.allow_spinning', '0')
        self.person = ort.InferenceSession(str(folder/'person.onnx'), sess_options=options,
                                          providers=['CPUExecutionProvider'])
        self.vision = ort.InferenceSession(str(folder/'vision.onnx'), sess_options=options,
                                          providers=['CPUExecutionProvider'])
        with np.load(folder/'categories.npz', allow_pickle=False) as data:
            self.labels = tuple(str(x) for x in data['labels'])
            self.features = data['features'].copy()
        if self.labels != LABELS or self.features.shape != (len(LABELS), 768):
            raise ValueError('Unexpected report category vectors')
        grids, strides = [], []
        for stride in (8, 16, 32):
            y, x = np.meshgrid(np.arange(640//stride), np.arange(640//stride), indexing='ij')
            grids.append(np.stack([x, y], axis=-1).reshape(-1, 2))
            strides.append(np.full((len(grids[-1]), 1), stride))
        self.grids, self.strides = np.concatenate(grids), np.concatenate(strides)

    def classify(self, photo):
        import cv2
        import numpy as np
        from PIL import Image
        start = time.monotonic()
        with Image.open(photo) as source:
            image = source.convert('RGB')
        array = np.asarray(image)
        height, width = array.shape[:2]
        scale = min(640/width, 640/height)
        canvas = np.full((640, 640, 3), 114, np.float32)
        w, h = round(width*scale), round(height*scale)
        canvas[:h, :w] = cv2.resize(array, (w, h))
        detections = self.person.run(None, {self.person.get_inputs()[0].name:
                                          canvas.transpose(2, 0, 1)[None].copy()})[0][0]
        box = person_box(detections, width, height, scale, self.grids, self.strides)
        result = {'subject_visible': box is not None, 'category': None,
                  'model': 'Marqo-FashionSigLIP INT8 + YOLOX', 'decoder': 'fixed category similarity'}
        if box is not None:
            view = image.crop(box).resize((224, 224), Image.BICUBIC)
            pixels = (np.asarray(view, dtype=np.float32)/255-.5)/.5
            vector = self.vision.run(None, {self.vision.get_inputs()[0].name:
                                           pixels.transpose(2, 0, 1)[None].copy()})[0]
            vector /= np.linalg.norm(vector, axis=-1, keepdims=True)
            scores = (vector@self.features.T)[0]
            result.update(category=self.labels[int(np.argmax(scores))], source_box=box)
        result['seconds'] = round(time.monotonic()-start, 3)
        return result


def classify(photo):
    global _engine
    with _lock:
        if _engine is None:
            _engine = CategoryReporter()
        return _engine.classify(photo)
