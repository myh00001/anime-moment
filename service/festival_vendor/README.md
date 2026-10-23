# OpenCV Zoo hand gesture models

`mp_palmdet.py` and `mp_handpose.py` are from OpenCV Zoo:
https://github.com/opencv/opencv_zoo/tree/main/models/palm_detection_mediapipe
https://github.com/opencv/opencv_zoo/tree/main/models/handpose_estimation_mediapipe

Corresponding Apache 2.0 licenses are included alongside the source files.
Download the FP32 2023feb ONNX files from those directories into `service/models/`.
Models are excluded from this repository. This uses CPU inference, throttled to
roughly three observations per second; the existing anime models remain on BPU.

The school emblem in `../assets/` is user-provided. Rights to school branding
remain with its owner and are not granted by the project's source-code license.
