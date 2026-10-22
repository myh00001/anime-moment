# S100 实时动漫相机

在地瓜机器人 RDK S100 上，将 USB 摄像头画面实时转换为固定动漫风格，并在连接的屏幕上原生全屏显示。模型在板载 BPU 上执行，使用 GTK 显示，不依赖浏览器或另一台电脑。

## 功能

- 自动选择摄像头最高可用分辨率及该模式对应的最高帧率，断开后等待重连。
- 场景重绘、人脸结构生成、动漫化和语义解析，保留当前帧的姿态与表情。
- 受控双进程流水线：将前一帧 CPU 收尾与下一帧 BPU 推理重叠，最多两帧在途，每次取最新输入。
- 镜像输出、按比例全屏；Esc 退出全屏，F11 或 F 恢复全屏，窗口最大化按钮恢复无标题栏全屏。
- 鼠标移到左上角显示实时分辨率、真实输出 FPS、CPU/BPU 占用、频率、温度、内存和处理耗时；白字配半透明黑底。
- 自动铺满横屏或竖屏，比例不同时居中裁剪，不留上下或左右黑边。展开左上角“画面设置”可选择输出分辨率或自定义宽高、顺时针旋转0/90/180/270度、切换镜像；点击“应用并保存”后新帧生效，设置在重启后保留。
- 鼠标移到右下角隐藏，移开恢复；桌面登录时自动启动，手动关闭后不自行重新打开，双击桌面图标可再次启动。
- 不进行历史帧混合，不通过重复画面或插帧提高 FPS。

## 实测性能

RDK S100、系统 4.0.4-Beta、HBRT 4.2.11，输出 960×540，2026-10-22：

|场景|此前|当前|
|---|---:|---:|
|固定单人样本，前一轮实验|约 1.50 FPS|约 2.31 FPS|
|四种单人姿态、40 帧，调度优化|约 2.32 FPS|约 2.78 FPS|
|现场 USB 摄像头，无检测到的人脸|约 6.6 FPS|约 9.8～10.4 FPS|

本轮同样本对照：BPU平均读数约73%→88%，单帧平均延迟约586→642ms，完整画面逐像素一致；这次没有替换模型或量化版本。信息栏同时显示瞬时BPU和近几秒均值。以上是特定场景实测，不代表任意设备或场景的保证。摄像头标称30FPS不等于生成30FPS。细节见 [性能说明](docs/performance.md)。

输出尺寸范围为宽320～1920、高240～1920，均以4像素对齐。旋转在模型推理前进行，按目标输出比例居中裁剪原画；显示时再次按窗口比例铺满。较高输出尺寸会增加CPU处理量，实际模型原生尺寸不变。设置保存于 `service/display-settings.json`，该文件不纳入Git。

## 环境与模型

- RDK S100 / aarch64 Ubuntu 22.04 图形桌面，已安装匹配的 D-Robotics `hbm_runtime`（本项目验证 HBRT 4.2.11）。
- USB UVC 摄像头及连接到 S100 的显示器。
- Python 3.10；系统 GTK3、PyGObject、Cairo、V4L2 工具；Python 包版本见 `service/requirements.txt`。
- 四个编译好的 HBM 模型和 YuNet ONNX 检测器，校验值及输入尺寸见 [models-manifest.json](models-manifest.json)。

**本仓库发布程序代码，不附带模型权重、个人摄像头样本或校准图片。** 模型许可与程序许可不同，特别是 AnimeGANv3 上游包含非商业使用限制；来源及准备方式见 [模型说明](docs/models.md)。模型文件需单独取得后导入；只克隆代码不能直接运行推理。这里使用预训练模型近似动漫画风，并非对某张参考图的精确复现。

## 在 S100 运行

在 S100 桌面用户的终端操作，不要用 root 运行图形界面：

```bash
cd s100-anime-camera
# 目录中应包含清单要求的四个 .hbm 和 YuNet .onnx 文件
python3 scripts/import_models.py /path/to/model-files
bash scripts/install_dependencies.sh
python3 scripts/check_environment.py
python3 service/local_display.py
```

`install_dependencies.sh` 使用 apt 安装图形依赖，用系统 Python 将 Python 包装入 `service/vendor/`，不会安装或替换板卡固件、HBRT 或 Windows/WSL 工具链。

可选安装自启动与桌面图标：

```bash
python3 scripts/setup_desktop.py --start
```

未加 `--start` 时仅安装并启用下次图形会话自启动，不立即打开程序。服务设置 `Restart=no`，手动关闭后保持关闭。桌面快捷方式只执行 `start`，不会重启正在运行的实例。仓库移动后需要重新执行安装脚本。

若希望关闭屏幕自动休眠，可另外运行：

```bash
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
```

## 可选网页入口

```bash
bash service/start.sh
```

默认只监听 S100 的 `127.0.0.1:7860`，可通过 SSH 转发访问：

```bash
ssh -L 7860:127.0.0.1:7860 YOUR_USER@YOUR_BOARD_IP
```

打开 `http://127.0.0.1:7860/`。网页入口使用浏览器所在设备的摄像头，与板上 GTK 的 USB 摄像头入口不同；同时运行会共享 BPU 资源。此接口没有账户鉴权，请保持回环监听或 SSH 转发，不要直接暴露到公网。

## 目录

```text
service/                 S100 BPU 推理、USB 采集、GTK 显示及可选 HTTP 服务
scripts/                 模型导入、依赖安装、环境检查、桌面服务安装
docs/                    模型来源、架构与实测性能
licenses/                已取得的第三方许可文本
models-manifest.json     已验证运行模型的 SHA256 和尺寸
```

## 许可

本仓库原创应用与部署代码采用 [MIT](LICENSE)。已标明来源的第三方内容适用其各自许可；模型权重不适用本仓库 MIT 许可，不能据此推定模型可自由商用。见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
