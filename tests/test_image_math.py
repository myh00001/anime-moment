from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from image_math import normalized_pixels,decoded_pixels_owned


class ImageMathTests(unittest.TestCase):
    def test_normalization_is_exact_and_keeps_source_intact(self):
        image=np.arange(256,dtype=np.uint8).reshape(16,16)
        original=image.copy()
        np.testing.assert_array_equal(normalized_pixels(image),image.astype(np.float32)/127.5-1)
        np.testing.assert_array_equal(image,original)

    def test_decode_matches_original_for_clipped_contiguous_and_strided_data(self):
        random=np.random.default_rng(123)
        for shape in [(1,3,32,32),(32,32,3)]:
            raw=random.uniform(-2,2,shape).astype(np.float32)
            for value in [raw.copy(),raw.copy().swapaxes(0,-1)]:
                expected=np.clip((value+1)*127.5,0,255).astype(np.uint8)
                np.testing.assert_array_equal(decoded_pixels_owned(value),expected)


if __name__=='__main__':unittest.main()
