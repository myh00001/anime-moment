"""Single-input, float-featuremap HBM runner for the S100 runtime."""
from pathlib import Path
import json
import numpy as np
from hbm_runtime import HB_HBMRuntime


class HbmRunner:
    def __init__(self, path):
        self.path = Path(path)
        config_path = self.path.parent / 'model-config.json'
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        self.output_tanh = config.get(self.path.stem, {}).get('output_tanh', False)
        self.runtime = HB_HBMRuntime(str(self.path))
        self.name = self.runtime.model_names[0]
        self.input_name = self.runtime.input_names[self.name][0]
        self.shape = tuple(self.runtime.input_shapes[self.name][self.input_name])

    def __call__(self, value):
        value = np.ascontiguousarray(value, dtype=np.float32)
        if tuple(value.shape) != self.shape:
            raise ValueError(f'{self.path.name}: expected {self.shape}, got {value.shape}')
        result = self.runtime.run({self.input_name: value}, model_name=self.name)
        outputs = result[self.name]
        arrays = [np.array(array, copy=True) for array in outputs.values()]
        if self.output_tanh:
            arrays[0] = np.tanh(arrays[0])
        return arrays
