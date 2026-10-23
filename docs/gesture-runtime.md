# Optional CPU gesture runtime

The palm and hand ONNX files, confidence thresholds, preprocessing, landmark
classification and global search windows remain unchanged. If the isolated
ONNX Runtime installation exists at `local-vlm/gesture-ort/runtime`, the camera
uses its CPU execution provider with one inference thread and no spinning.
Each inference yields 12 ms to rendering. Missing dependencies, model-load
errors or inference errors fall back to the original OpenCV networks; an
inference error retries the same input frame.

The tested S100 environment uses Python 3.10, NumPy 1.24.4 and ONNX Runtime
1.22.1. Install this optional dependency without changing system packages:

```sh
python3 -m pip install --no-deps --target local-vlm/gesture-ort/runtime onnxruntime==1.22.1
```

Two live ABBA comparisons at 1920×1080, with no detected faces, measured:

| Samples per run | OpenCV FPS | Candidate FPS | Palm scans/s, OpenCV | Candidate |
| --- | ---: | ---: | ---: | ---: |
| 25 seconds | 8.551 | 8.741 | 9.445 | 11.181 |
| 45 seconds | 8.527 | 8.657 | 9.395 | 11.029 |

This is a modest 1.5–2.2% output FPS improvement and roughly 17–18% faster palm
search in these scenes, not a general FPS guarantee. The 52-frame public hand
fixture preserved landmark tolerances and all V decisions, including three
positive frames. It does not establish a detection-distance guarantee.

The official quantized BPU gesture candidate was rejected because it missed
the three positive V frames. Gesture inference therefore remains on CPU;
the existing anime models continue using the BPU.
