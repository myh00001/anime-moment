import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'service'))
import native_math


class NativeMathTests(unittest.TestCase):
    def test_sharpen_exact_and_fallback(self):
        rng = np.random.default_rng(420)
        for count in (1, 17, 262145, 1048579):
            source = rng.uniform(0, 255, count).astype(np.float32)
            blur = rng.uniform(0, 255, count).astype(np.float32)
            expected = np.clip(source * np.float32(.98) + np.float32(4) +
                               (source - blur) * np.float32(.22), 0, 255).astype(np.uint8)
            for enabled in (False, native_math.AVAILABLE):
                with patch.object(native_math, 'AVAILABLE', enabled):
                    actual = native_math.sharpen_exact(source.copy(), blur.copy())
                np.testing.assert_array_equal(actual, expected)

    def test_quarter_blend_all_pairs(self):
        # Every possible pair, also repeated above the parallel threshold.
        a = np.tile(np.repeat(np.arange(256, dtype=np.uint8), 256), 5)
        b = np.tile(np.arange(256, dtype=np.uint8), 256 * 5)
        expected = ((a.astype(np.uint16) + 3 * b.astype(np.uint16)) // 4).astype(np.uint8)
        np.testing.assert_array_equal(native_math.quarter_blend_exact(a.copy(), b), expected)

    def test_reject_wrong_dtype(self):
        with self.assertRaises(ValueError):
            native_math.sharpen_exact(np.zeros(5, np.float64), np.zeros(5, np.float32))


if __name__ == '__main__':
    unittest.main()
