import importlib.util
from pathlib import Path
import unittest
import numpy as np


class QkvExportTests(unittest.TestCase):
    def test_numeric_metrics_are_bounded_and_reject_invalid_outputs(self):
        path=Path(__file__).resolve().parents[1]/'scripts/benchmark_language_qkv.py'
        spec=importlib.util.spec_from_file_location('qkv_benchmark',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        value=np.random.default_rng(31).normal(size=(256,2048)).astype('float32')
        cosine,relative=module.error_metrics(value,value*1.001)
        self.assertLessEqual(cosine,1);self.assertGreater(cosine,.999999)
        self.assertAlmostEqual(relative,.000999,places=5)
        with self.assertRaises(ValueError):module.error_metrics(value,np.full_like(value,np.nan))

    def test_channel_token_mapping_and_bias_matches_linear(self):
        import onnxruntime as ort
        path=Path(__file__).resolve().parents[1]/'scripts/export_language_qkv.py'
        spec=importlib.util.spec_from_file_location('qkv_export',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        rng=np.random.default_rng(42)
        weight=rng.normal(size=(12,8)).astype('float32');bias=rng.normal(size=12).astype('float32')
        for tokens in [1,7,256]:
            hidden=rng.normal(size=(tokens,8)).astype('float32')
            model=module.projection_model(weight,bias,tokens)
            session=ort.InferenceSession(model.SerializeToString(),providers=['CPUExecutionProvider'])
            result=session.run(None,{'hidden':hidden.T[None,:,None,:]})[0][0,:,0,:].T
            np.testing.assert_allclose(result,hidden@weight.T+bias,rtol=1e-5,atol=2e-6)


if __name__=='__main__':unittest.main()
