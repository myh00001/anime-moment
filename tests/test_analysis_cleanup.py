"""Exercise the real render error path without models or a camera."""
import ast
import concurrent.futures
from pathlib import Path
import threading
import time
import unittest

import numpy as np


class AnalysisCleanupTests(unittest.TestCase):
    def test_generation_failure_joins_analysis_and_preserves_original_error(self):
        source = Path(__file__).resolve().parents[1] / 'service' / 'board_base.py'
        tree = ast.parse(source.read_text())
        camera_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AnimeCamera')
        render = next(n for n in camera_class.body if isinstance(n, ast.FunctionDef) and n.name == 'render')
        namespace = {'np': np}
        exec(compile(ast.Module(body=[render], type_ignores=[]), str(source), 'exec'), namespace)
        camera_type = type('CameraUnderTest', (), {'render': namespace['render']})
        for analysis_fails in (False, True):
            camera = camera_type()
            camera.scene_size = 640
            finished = threading.Event()

            def analyze(*args):
                try:
                    time.sleep(.02)
                    if analysis_fails:
                        raise ValueError('analysis failure')
                finally:
                    finished.set()

            def generate(*args):
                raise RuntimeError('original generation failure')

            camera.analyze_source = analyze
            camera.generate = generate
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                camera._analysis_pool = pool
                with self.assertRaisesRegex(RuntimeError, 'original generation failure'):
                    camera.render(np.zeros((32, 32, 3), np.uint8))
                self.assertTrue(finished.is_set())
                self.assertFalse(camera._scene_request)
