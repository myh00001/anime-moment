# 校园科技节拍照打印

## 推荐：ETH1 网线直连打印机

当前现场已切换至网口打印，USB可以拔掉。应用仍使用同名 `S100_Festival` 队列，沿用M452 PostScript驱动和纸型设置；连接地址改为 `socket://<打印机IPv4地址>:9100`。不需要重启相机程序，不改变动漫模型或自启动策略。

直连时，S100的ETH1必须具有与打印机同网段的地址。先观察打印机广播或在打印机面板查看地址，再为ETH1建立独立、持久化的NetworkManager配置；保留ETH0远程连接与默认路由，ETH1不设置默认网关。不要盲目给两端套用固定示例IP。如果打印机使用DHCP，应配置稳定地址或DHCP保留，以免重启后地址变化。

确认路由走ETH1、9100端口可达后，可以切换已有队列：

```sh
python3 scripts/configure_network_printer.py --host <打印机IPv4地址>
```

切换前检查 `lpstat -W not-completed -o S100_Festival`。已部分发送的旧USB任务可能出过纸，应人工核对后取消，避免切换传输方式时重印；尚未发送的排队任务可沿用。该脚本不会新增打印任务，也不会改动已有页面设置。

现场验证：切换后两个原有待打印任务通过网口完成，各1页；ETH0远程连接保持正常。设备地址和私有配置备份不纳入仓库。

## 使用

打印机先开机并放置A5纸。比出✌并保持约半秒，倒计时3秒后拍摄新的动漫画面。放下手约一秒后才能再次触发，保持同一手势不会连续打印。按钮和空格也能触发。照片不包含倒计时、照片墙或信息面板。

每次拍照生成一张A5竖版PDF，包含学校提供的校徽、指定标题、日期和照片。照片墙按时间从上往下排列、显示最近8张、自动向下滚动，照片和PDF在本地 `service/captures/<时间-编号>/` 保存。目录不进入Git。`record.json` 保存打印提交结果；断电或提交结果不明时不自动重复提交。正常提交后的离线作业由CUPS等待打印机恢复，无须再次拍照。

## 模型

安装项目依赖后，将以下文件下载到 `service/models/`（不要提交模型到Git）：

- https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/palm_detection_mediapipe/palm_detection_mediapipe_2023feb.onnx
- https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/handpose_estimation_mediapipe/handpose_estimation_mediapipe_2023feb.onnx

对应Python实现与Apache许可证在 `service/festival_vendor/`。校徽版权归所属学校，项目MIT许可不授予校徽使用权。

## HP Color LaserJet Pro M452nw USB

板端HPLIP 3.21.12的型号库明确支持该型号、PostScript打印、无需专有插件；最低HPLIP版本3.15.11。需要 `cups`、`cups-client`、`hplip`、`printer-driver-hpcups`，报纸需要 `reportlab`、`Pillow`、`fonts-wqy-zenhei`。

使用 `sudo lpinfo -v` 找到实际USB URI，使用 `sudo lpinfo -m` 找到 `hp-color_laserjet_m452-ps.ppd` 的确切驱动ID，然后配置队列：

```sh
sudo lpadmin -p S100_Festival -E -v '<实际USB URI>' -m '<实际M452 PostScript驱动ID>'
sudo lpadmin -p S100_Festival -o media-default=iso_a5_148x210mm -o orientation-requested-default=4 -o sides-default=one-sided -o HPPJLColorAsGray-default=off -o print-color-mode-default=color -o printer-is-shared=false
```

程序每次用 `lp -d S100_Festival -n 1` 显式指定A5、横向纸张、单面和彩色（PDF内容保持竖版）。纸盒中的物理放纸方向与PDF页面方向是两件事，纸盒纸型必须设置为A5。断电或拔线时已有任务等待重连，不要重复发送同一照片。

现场测试可以向正在运行的显示进程发送一次SIGUSR1，走同一个倒计时/拍摄/打印流程；该信号仅为本地管理员测试入口。开机启动和手动关闭后不重开的策略未改。
