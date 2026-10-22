# 第三方来源与许可

本仓库 MIT 许可仅适用于原创应用与部署代码，不覆盖外部模型、HBRT、系统库或 pip 依赖。运行依赖由安装脚本取得，权重不随仓库发布。

|用途|上游|许可说明|
|---|---|---|
|人脸结构模型 face_paint_512_v2|[bryandlee/animegan2-pytorch](https://github.com/bryandlee/animegan2-pytorch)|已取得的上游 MIT 文本保存在 `licenses/AnimeGAN2-MIT.txt`；使用权重时另核对其来源条款|
|场景和人脸动漫重绘 Ghibli|[TachibanaYoshino/AnimeGANv3](https://github.com/TachibanaYoshino/AnimeGANv3)、[portrait inference](https://github.com/TachibanaYoshino/AnimeGANv3_Portrait_Inference)|上游注明非商业用途；商业授权应向上游作者取得。未将权重按 MIT 重新授权|
|YuNet 人脸检测|[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)|对应许可文本见 `licenses/YuNet-MIT.txt`|
|头部语义解析模型|已部署的 `head_parse_512.hbm`，身份以清单 SHA256 确认|尚未在发布包中确证原始权重的完整授权来源，因此不分发权重、不对其授予本仓库许可|
|S100 HBM 运行时|D-Robotics RDK S100 / OE|由板卡系统提供，遵守厂商各自条款，本仓库不分发运行时安装包|

依赖包括 NumPy、OpenCV、Pillow、FastAPI、Uvicorn、GTK、PyGObject、Cairo，分别适用各自上游许可。安装后的 `vendor/` 不纳入版本管理。
