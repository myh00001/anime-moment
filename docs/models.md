# 模型准备与兼容性

当前部署使用四个 HBM 和一个 YuNet ONNX，文件名、输入尺寸、字节数和 SHA256 见根目录 `models-manifest.json`。所有图像输入为 RGB，生成器使用 float32 `RGB / 127.5 - 1`。HBM 内部保留输出 Tanh，`service/models/model-config.json` 的 `output_tanh` 全为 `false`，不要再次应用 Tanh。

|文件|用途|布局|
|---|---|---|
|scene_640.hbm|全场景动漫重绘|NHWC 640×360|
|portrait_structure_512.hbm|人脸结构，卷积 INT8、关键归一化及仿射 INT16|NCHW 512×512|
|portrait_anime_512.hbm|人脸动漫重绘|NHWC 512×512|
|head_parse_512.hbm|头部和五官语义标签|NCHW 512×512|
|face_detection_yunet_2023mar.onnx|人脸及五点检测|OpenCV FaceDetectorYN|

## 使用已有模型包

将这五个文件放在同一个目录，然后执行：

```bash
python3 scripts/import_models.py /path/to/model-files
```

脚本先校验全部文件，再复制到 `service/models/`。不匹配时不会开始复制。模型包是独立资产，本仓库不含下载令牌、个人摄像头校准图片或私有下载地址；首次使用者需自行取得符合许可的模型包。

## 原始来源

- 人脸结构：<https://github.com/bryandlee/animegan2-pytorch> 的 `face_paint_512_v2`。
- Ghibli 生成器：<https://github.com/TachibanaYoshino/AnimeGANv3_Portrait_Inference/releases/download/1.0/AnimeGANv3_large_Ghibli_c1_e299.onnx>。
- Ghibli 上游许可说明：<https://github.com/TachibanaYoshino/AnimeGANv3#scroll-license>。
- YuNet：<https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet>。
- 头部解析 HBM 对应的原始权重授权来源尚未在本发布中确证；该二进制不分发。

## 重新编译的注意点

已验证的是 OE 3.2.0 / hbdk4 4.2.11 生成的 nash-e HBM 和板端 HBRT 4.2.11。HBM 并非通用 ONNX，不能直接用于 CUDA、其他型号 BPU 或任意 HBRT 版本。

原部署对模型图做过反射填充显式化、空间均值分层池化、归一化保持四维、通道仿射转逐通道 1×1 卷积等变换，并进行了真实板端画质验证。仅用同名上游 ONNX 直接转换不保证得到相同效果；GroupNorm 全 INT8 曾出现明显暗脸，Resize 坐标模式及额外 Tanh 也会改变画质。

本次代码仓库不是完整量化训练/校准工程，也不包含原始权重和校准数据，不能声称仅凭本仓库能重建位级相同的 HBM。不同模型需重新评估图算子、量化精度、输出范围和板端画质；不要绕过导入校验后将其视为已验证模型。
