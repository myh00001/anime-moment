import importlib.util
from pathlib import Path
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


class FfnTests(unittest.TestCase):
    def test_swiglu_graph_and_padded_tokens_match_reference(self):
        import onnxruntime as ort
        exporter=module('ffn_export',ROOT/'scripts/export_language_ffn.py')
        random=np.random.default_rng(31)
        up=random.normal(size=(12,8)).astype('float32')
        gate=random.normal(size=(12,8)).astype('float32')
        down=random.normal(size=(8,12)).astype('float32')
        hidden=random.normal(size=(7,8)).astype('float32')
        raw=hidden@gate.T
        expected=(raw/(1+np.exp(-raw))*(hidden@up.T))@down.T
        for bucket in [7,16]:
            inputs=np.zeros((1,8,1,bucket),np.float32);inputs[0,:,0,:7]=hidden.T
            session=ort.InferenceSession(exporter.ffn_model(up,gate,down,bucket).SerializeToString(),providers=['CPUExecutionProvider'])
            actual=session.run(None,{'hidden':inputs})[0][0,:,0,:7].T
            np.testing.assert_allclose(actual,expected,rtol=1e-5,atol=3e-5)

    def test_socket_packets_accept_fragmentation_and_detect_truncation(self):
        worker=module('ffn_worker',ROOT/'scripts/ffn_bridge_worker.py')
        class Connection:
            def __init__(self,blocks):self.blocks=iter(blocks)
            def recv(self,length):return next(self.blocks,b'')
        self.assertEqual(worker.receive(Connection([b'a',b'bc',b'd']),4),b'abcd')
        with self.assertRaises(EOFError):worker.receive(Connection([b'ab']),4)

    def test_builder_rejects_unrecognized_graph_and_is_idempotent(self):
        builder=module('ffn_builder',ROOT/'scripts/build_language_ffn_bridge.py')
        with self.assertRaises(ValueError):builder.patch_qwen_source('different graph')
        original='#include "models.h"\n'+builder.START+'                placeholder,\n'+builder.END
        patched=builder.patch_qwen_source(original)
        self.assertEqual(builder.patch_qwen_source(patched),patched)
        self.assertIn('else {',patched)


if __name__=='__main__':unittest.main()
