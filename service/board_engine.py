import concurrent.futures
from native_math import quarter_blend_exact
import cv2
import numpy as np
from board_base import AnimeCamera,ROOT
from hbm_runner import HbmRunner
from image_math import normalized_pixels,decoded_pixels_owned,luminance_lut
from display_settings import DEFAULT_SETTINGS
_LABEL_TABLES = {}
_YY, _XX = np.mgrid[:512, :512].astype(np.float32)

def luminance_percentiles(values):
    hist = np.bincount(values.astype(np.uint8).ravel(), minlength=256)
    cdf = hist.cumsum()
    indices = (values.size - 1) * np.array([0.02, 0.98])
    lower = np.floor(indices).astype(int)
    upper = np.ceil(indices).astype(int)
    lo, hi = np.searchsorted(cdf, lower + 1), np.searchsorted(cdf, upper + 1)
    return lo + (hi - lo) * (indices - lower)

def label_in(labels, ids):
    if labels.dtype != np.uint8:
        return np.isin(labels, ids)
    key = tuple(ids)
    if key not in _LABEL_TABLES:
        table = np.zeros(256, dtype=bool)
        table[list(key)] = True
        _LABEL_TABLES[key] = table
    return _LABEL_TABLES[key][labels]
class BoardCamera(AnimeCamera):

    def __init__(self):
        super().__init__()
        self._source_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        cv2.setNumThreads(6)
        self.scene_size = max(DEFAULT_SETTINGS['width'],DEFAULT_SETTINGS['height'])
        self.face_detail_fallbacks = self.stable_faces = 0
        self.alignment_template = np.float32([[192.98138, 239.94708], [318.90277, 240.1936], [256.63416, 314.01935], [201.26117, 371.41043], [313.08905, 371.15118]])
        self.trt = {key: HbmRunner(ROOT / 'models' / file) for key, file in {'portrait_v2_512': 'portrait_structure_512.hbm', 'portrait_anime': 'portrait_anime_512.hbm', 'scene': 'scene_640.hbm', 'parser': 'head_parse_512.hbm'}.items()}
        self._portrait_labels = None
        self.trt_calls = self.ort_calls = self.torch_calls = 0

    def run_ghibli(self, x):
        self.trt_calls += 1
        if x.shape[1:3] == (512, 512):
            return self.trt['portrait_anime'](x)[0]
        h, w = x.shape[1:3]
        if (h, w) == (360, 640):
            return self.trt['scene'](x)[0]
        scale = min(640 / w, 360 / h)
        nw, nh = (round(w * scale), round(h * scale))
        left, top = ((640 - nw) // 2, (360 - nh) // 2)
        resized = cv2.resize(x[0], (nw, nh), interpolation=cv2.INTER_AREA)
        padded = cv2.copyMakeBorder(resized, top, 360 - nh - top, left, 640 - nw - left, cv2.BORDER_REFLECT_101)
        y = self.trt['scene'](padded[None])[0][0, top:top + nh, left:left + nw]
        return cv2.resize(y, (w, h), interpolation=cv2.INTER_CUBIC)[None]

    def parse_labels(self, image, size=512):
        x = normalized_pixels(image).transpose(2, 0, 1)[None]
        self.trt_calls += 1
        logits = self.trt['parser'](x)[0]
        labels = logits[0].astype(np.uint8) if logits.ndim == 3 else logits.argmax(axis=1)[0]
        if getattr(self, '_remaining_faces', -1) == 0 and getattr(self, 'on_bpu_chain_done', None):
            self.on_bpu_chain_done()
        return labels

    def face_mask(self, crop, refined):
        generated_labels = self._portrait_labels
        self._portrait_labels = None
        if generated_labels is None:
            generated_labels = self.parse_labels(refined)
        mask = label_in(generated_labels, list(range(1, 14)) + [15]).astype(np.uint8)
        if not 0.03 < float(mask.mean()) < 0.9:
            mask = label_in(self.parse_labels(crop), list(range(1, 14)) + [15]).astype(np.uint8)
            if not 0.03 < float(mask.mean()) < 0.9:
                return super().face_mask(crop, refined)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
        mask[:6] = 0
        mask[-6:] = 0
        mask[:, :6] = 0
        mask[:, -6:] = 0
        return np.clip(cv2.distanceTransform(mask, cv2.DIST_L2, 3) / 3, 0, 1).astype(np.float32)

    @staticmethod
    def face_detail(image):
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        regions = [gray[222:258, 165:220], gray[222:258, 292:345], gray[348:390, 220:292]]
        return float(np.mean([cv2.Laplacian(region, cv2.CV_32F).var() for region in regions]))

    @staticmethod
    def anime_proportions(image, labels):
        yy, xx = _YY, _XX
        mx = xx.copy()
        my = yy.copy()
        for ids, sx, sy in [([4], 1.18, 1.34), ([5], 1.18, 1.34), ([2], 0.92, 0.94), ([10, 11, 12], 0.94, 0.86)]:
            y, x = np.where(label_in(labels, ids))
            if len(x) < 12:
                continue
            cx, cy = ((x.min() + x.max()) * 0.5, (y.min() + y.max()) * 0.5)
            rx = max(12.0, (x.max() - x.min()) * 1.15)
            ry = max(10.0, (y.max() - y.min()) * 1.6)
            left, right = (max(0, int(cx - rx)), min(512, int(cx + rx) + 1))
            top, bottom = (max(0, int(cy - ry)), min(512, int(cy + ry) + 1))
            local_x = xx[top:bottom, left:right]
            local_y = yy[top:bottom, left:right]
            radius = ((local_x - cx) / rx) ** 2 + ((local_y - cy) / ry) ** 2
            weight = np.maximum(0, 1 - radius) ** 2
            mx[top:bottom, left:right] += (local_x - cx) * (1 / sx - 1) * weight
            my[top:bottom, left:right] += (local_y - cy) * (1 / sy - 1) * weight
        return cv2.remap(image, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)

    def generate(self, rgb, size):
        if size == 512 and rgb.shape[:2] == (512, 512) and (not getattr(self, '_scene_request', False)):
            if 'portrait_v2_512' in self.trt:
                self.trt_calls += 1
                x = normalized_pixels(rgb).transpose(2, 0, 1)[None]
                y = self.trt['portrait_v2_512'](x)[0][0].transpose(1, 2, 0)
                out = decoded_pixels_owned(y)
            else:
                self.torch_calls += 1
                out = super().generate(rgb, 512)
            x = normalized_pixels(out)[None]
            y = self.run_ghibli(x)[0]
            out = decoded_pixels_owned(y)
            if out.shape[:2] != (512, 512):
                out = cv2.resize(out, (512, 512), interpolation=cv2.INTER_CUBIC)
            out = cv2.resize(cv2.bilateralFilter(cv2.resize(out, (256, 256), interpolation=cv2.INTER_AREA), 5, 55, 3.5), (512, 512), interpolation=cv2.INTER_LINEAR)
            labels = self.parse_labels(out)
            self._portrait_labels = labels
            out = self.anime_proportions(out, labels)
            lab = cv2.cvtColor(out, cv2.COLOR_RGB2LAB).astype(np.float32)
            warm = (out[:, :, 0].astype(np.float32) > out[:, :, 1] * 1.025) & (out[:, :, 0].astype(np.float32) > out[:, :, 2] * 1.04)
            skin = (label_in(labels, [1, 2, 8, 9]) & warm & (lab[:, :, 0] > 65)).astype(np.uint8)
            skin = cv2.erode(skin, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
            alpha = cv2.GaussianBlur(skin.astype(np.float32), (9, 9), 2)
            light = lab[:, :, 0]
            smooth = cv2.resize(cv2.bilateralFilter(cv2.resize(light, (256, 256), interpolation=cv2.INTER_AREA), 9, 32, 6), (512, 512), interpolation=cv2.INTER_LINEAR)
            valid = (skin > 0) & (light > 65)
            middle = float(np.median(light[valid])) if valid.any() else 165.0
            flat = max(middle, 145) + (smooth - middle) * 0.45 + 8
            flat = flat * 0.65 + np.round(flat / 16) * 16 * 0.35
            lab[:, :, 0] = light * (1 - alpha * 0.65) + flat * (alpha * 0.65)
            lab[:, :, 0] = 255 * np.power(np.clip(lab[:, :, 0] / 255, 0, 1), 0.88)
            lab[:, :, 1] = lab[:, :, 1] * (1 - alpha * 0.18) + 132 * (alpha * 0.18)
            lab[:, :, 2] = lab[:, :, 2] * (1 - alpha * 0.2) + 136 * (alpha * 0.2)
            lips = label_in(labels, [11, 12]).astype(np.float32)
            lips = cv2.GaussianBlur(lips, (7, 7), 1.4) * 0.2
            if valid.any():
                skin_tone = np.median(lab[valid], axis=0)
                lip_y, lip_x = np.where(lips > 0)
                if len(lip_x):
                    sy = slice(lip_y.min(), lip_y.max() + 1)
                    sx = slice(lip_x.min(), lip_x.max() + 1)
                    amount = lips[sy, sx, None]
                    lab[sy, sx] = lab[sy, sx] * (1 - amount) + skin_tone * amount
                brows = label_in(labels, [6, 7]).astype(np.uint8)
                distance = cv2.distanceTransform(brows, cv2.DIST_L2, 3)
                edge = np.clip(1 - distance / 3, 0, 1)
                amount = brows.astype(np.float32) * (0.24 + 0.32 * edge)
                feather = cv2.GaussianBlur(brows.astype(np.float32), (3, 3), 0.55)
                brow_y, brow_x = np.where(feather > 0)
                if len(brow_x):
                    sy = slice(brow_y.min(), brow_y.max() + 1)
                    sx = slice(brow_x.min(), brow_x.max() + 1)
                    region = lab[sy, sx]
                    brow_tone = region.copy()
                    brow_tone[:, :, 0] = np.minimum(region[:, :, 0] * 0.72 + 42, region[:, :, 0] + 40)
                    local_amount = amount[sy, sx, None]
                    local_feather = feather[sy, sx, None]
                    brow_tone = brow_tone * (1 - local_amount) + skin_tone * local_amount
                    lab[sy, sx] = region * (1 - local_feather) + brow_tone * local_feather
            self.stable_faces += 1
            return cv2.cvtColor(np.uint8(np.clip(lab, 0, 255)), cv2.COLOR_LAB2RGB)
        h, w = rgb.shape[:2]
        nw, nh = (max(32, round(w * size / max(w, h) / 4) * 4), max(32, round(h * size / max(w, h) / 4) * 4))
        small = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        padded = cv2.copyMakeBorder(small, 0, -nh % 8, 0, -nw % 8, cv2.BORDER_REFLECT_101)
        x = normalized_pixels(padded)[None]
        y = self.run_ghibli(x)[0, :nh, :nw]
        out = decoded_pixels_owned(y)
        return out

    def render_partial(self, rgb):
        self.face_detail_fallbacks = 0
        self.stable_faces = 0
        self._portrait_labels = None
        self.trt_calls = self.ort_calls = self.torch_calls = 0
        generated = super().render(rgb)
        self.last_face_stats['detail_fallbacks'] = self.face_detail_fallbacks
        self.last_face_stats['stable_faces'] = self.stable_faces
        self.last_face_stats['backend'] = 'S100 BPU'
        return generated, self.current_face_coverage

    @staticmethod
    def prepare_source_lab(rgb, size):
        source = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
        source = cv2.bilateralFilter(source, 5, 24, 4)
        return cv2.cvtColor(source, cv2.COLOR_RGB2LAB)

    def render(self, rgb):
        h, w = rgb.shape[:2]
        size = (max(32, round(w * self.scene_size / max(w, h) / 4) * 4),
                max(32, round(h * self.scene_size / max(w, h) / 4) * 4))
        future = self._source_pool.submit(self.prepare_source_lab, rgb, size)
        try:
            generated, coverage = self.render_partial(rgb)
            source_lab = future.result()
        except BaseException:
            future.result()
            raise
        if source_lab.shape[:2] != generated.shape[:2]:
            raise RuntimeError('Prefetched source size differs from generated size')
        return self.finish_render(rgb, generated, coverage, source_lab)

    @staticmethod
    def finish_render(rgb, generated, coverage, source_lab=None):
        h, w = generated.shape[:2]
        if source_lab is None:
            source = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA)
            source = cv2.bilateralFilter(source, 5, 24, 4)
            source_lab = cv2.cvtColor(source, cv2.COLOR_RGB2LAB)
        lab = cv2.cvtColor(generated, cv2.COLOR_RGB2LAB)
        original = source_lab
        light_channel = lab[:, :, 0].copy()
        # Quarter weights are exact in binary. CV_32F preserves the original
        # float result; cast afterwards to truncate, rather than rounding to u8.
        lab = quarter_blend_exact(lab, original)
        histogram = cv2.calcHist([light_channel], [0], None, [256], [0, 256]).ravel().astype(np.int64)
        cdf = histogram.cumsum()
        indices = (light_channel.size - 1) * np.array([0.02, 0.98])
        lower, upper = np.floor(indices).astype(int), np.ceil(indices).astype(int)
        lo, hi = np.searchsorted(cdf, lower + 1), np.searchsorted(cdf, upper + 1)
        low, high = lo + (hi - lo) * (indices - lower)
        if high - low > 40:
            # The source L channel is uint8: evaluate the existing float32
            # expression for its 256 possible values, then apply it exactly.
            light_channel = cv2.LUT(light_channel, luminance_lut(low, high))
        lab[:, :, 0] = light_channel
        out = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        gray = cv2.cvtColor(out, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0.55), 75, 150)
        # Canny emits only 0 or 255. Non-edge pixels are unchanged, so avoid
        # three full-resolution float images for this sparse operation.
        ys, xs = np.nonzero(edges)
        strength = 0.3 * (1 - 0.85 * coverage[ys, xs])
        out[ys, xs] = np.uint8(np.clip(out[ys, xs].astype(np.float32) * (1 - strength[:, None]), 0, 255))
        return out
