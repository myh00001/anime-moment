from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from image_math import normalized_pixels,decoded_pixels_owned,luminance_lut


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

    def test_luminance_lookup_matches_full_image_float32_arithmetic(self):
        rng=np.random.default_rng(42)
        image=rng.integers(0,256,(320,480),dtype=np.uint8)
        # Include all possible source values, narrow ranges and interpolated
        # percentile bounds, where truncation and dtype promotion matter.
        image.flat[:256]=np.arange(256,dtype=np.uint8)
        bounds=[(0.,255.),(20.25,210.75),(100.,140.),(50.,90.00001),(150.,150.)]
        bounds += [tuple(np.sort(rng.uniform(0,255,2))) for _ in range(50)]
        for low,high in bounds:
            values=image.astype(np.float32)
            if high-low>40:
                light=np.clip((values-low)*224/(high-low)+16,0,255)
                values=values*.35+light*.65
            expected=np.uint8(np.clip(values,0,255))
            np.testing.assert_array_equal(luminance_lut(low,high)[image],expected)


if __name__=='__main__':unittest.main()
