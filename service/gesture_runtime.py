"""Optional CPU gesture acceleration, retaining OpenCV as a same-frame fallback."""
from pathlib import Path
import sys
import time


class GestureNet:
    def __init__(self, path, fallback, ort):
        options = ort.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        options.add_session_config_entry('session.intra_op.allow_spinning', '0')
        options.add_session_config_entry('session.inter_op.allow_spinning', '0')
        self.session = ort.InferenceSession(str(path), sess_options=options,
                                           providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.names = tuple(value.name for value in self.session.get_outputs())
        self.fallback = fallback

    def setInput(self, value):
        self.value = value

    def getUnconnectedOutLayersNames(self):
        return self.names

    def forward(self, names):
        if self.session is not None:
            try:
                result = self.session.run(list(names), {self.input_name: self.value})
            except Exception:
                self.session = None
                print('GESTURE_RUNTIME OpenCV fallback', flush=True)
            else:
                # Yield CPU to image rendering while retaining faster global scans.
                time.sleep(.012)
                return result
        self.fallback.setInput(self.value)
        return self.fallback.forward(names)


def configure(palm, hand, root):
    runtime = Path(root) / 'local-vlm/gesture-ort/runtime'
    if not runtime.is_dir():
        return 'OpenCV'
    try:
        sys.path.insert(0, str(runtime))
        import onnxruntime as ort
        # Construct both before replacing either existing network.
        networks = [GestureNet(model.model_path, model.model, ort) for model in (palm, hand)]
    except Exception:
        return 'OpenCV'
    palm.model, hand.model = networks
    return 'ONNX Runtime CPU, cooperative yield'
