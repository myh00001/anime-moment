import sys
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'service'))
from gesture_runtime import GestureNet, configure


class GestureRuntimeTests(unittest.TestCase):
    def test_runtime_failure_retries_same_frame_with_original_network(self):
        frame = object()
        calls = []
        fallback = SimpleNamespace(setInput=lambda value: calls.append(value),
                                   forward=lambda names: ('opencv', names))
        net = GestureNet.__new__(GestureNet)
        def fail(*args):
            raise RuntimeError('runtime unavailable')
        net.session = SimpleNamespace(run=fail)
        net.input_name = 'image'
        net.fallback = fallback
        net.setInput(frame)
        self.assertEqual(net.forward(('Identity',)), ('opencv', ('Identity',)))
        self.assertIs(calls[0], frame)
        self.assertIsNone(net.session)

    def test_second_model_failure_keeps_both_original_networks(self):
        palm = SimpleNamespace(model_path='palm', model=object())
        hand = SimpleNamespace(model_path='hand', model=object())
        original = palm.model, hand.model
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'local-vlm/gesture-ort/runtime').mkdir(parents=True)
            with patch.dict(sys.modules, {'onnxruntime': SimpleNamespace()}):
                with patch('gesture_runtime.GestureNet', side_effect=[object(), RuntimeError('hand failed')]):
                    self.assertEqual(configure(palm, hand, folder), 'OpenCV')
        self.assertEqual((palm.model, hand.model), original)


if __name__ == '__main__':
    unittest.main()
