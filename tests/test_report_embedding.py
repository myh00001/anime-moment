import struct
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from report_vision_worker import write_embedding


class EmbeddingTests(unittest.TestCase):
    def test_header_shape_bytes_and_atomic_replacement(self):
        features=np.linspace(-1,1,256*1536,dtype=np.float32).reshape(1,256,1536)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'embedding.bin';path.write_bytes(b'old')
            details=write_embedding(features,path);data=path.read_bytes()
            self.assertEqual(struct.unpack('<III',data[:12]),(0x53313030,256,1536))
            np.testing.assert_array_equal(np.frombuffer(data[12:],dtype='<f4'),features.ravel())
            self.assertFalse(path.with_suffix('.tmp').exists())
            self.assertGreater(details['feature_std'],0)

    def test_invalid_features_never_replace_last_good_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'embedding.bin';path.write_bytes(b'good')
            for features in [np.zeros((1,256,1536)),np.full((1,256,1536),np.nan),np.zeros((1,256,896))]:
                with self.assertRaises(ValueError):write_embedding(features,path)
                self.assertEqual(path.read_bytes(),b'good')


if __name__=='__main__':unittest.main()
