# 校园科技节拍照打印

## 推荐：ETH1 网线直连打印机

当前使用ETH1网口和IPP正式作业协议，USB可以拔掉。应用仍使用同名 `S100_Festival` 队列，地址为 `ipp://<打印机IPv4地址>:631/ipp/print`，使用IPP Everywhere能力配置。M452nw已验证支持PDF。此前9100传输出现打印后连接不结束、下一张被阻塞的问题，当前默认使用IPP。

直连时，S100的ETH1必须具有与打印机同网段的地址。先观察打印机广播或在打印机面板查看地址，再为ETH1建立独立、持久化的NetworkManager配置；保留ETH0远程连接与默认路由，ETH1不设置默认网关。不要盲目给两端套用固定示例IP。如果打印机使用DHCP，应配置稳定地址或DHCP保留，以免重启后地址变化。

确认路由走ETH1、631端口可达后，可以切换已有队列：

```sh
python3 scripts/configure_network_printer.py --host <打印机IPv4地址>
```

切换前检查 `lpstat -W not-completed -o S100_Festival`。已部分发送的旧任务可能出过纸，应核对后取消，避免重印。该脚本不会新增打印任务。切换后确认默认纸型A5、普通纸、竖版文档、单面和彩色。`--protocol socket`仅供兼容其他设备，不作为本型号现场的默认方式。

最新现场验证：连续两个IPP任务分别18.4秒、15.8秒完成，每次本地CUPS任务结束且打印机状态恢复为3（就绪）；用户确认连续出纸两张。ETH0远程连接正常。设备地址和私有配置备份不纳入仓库。

## 不再逐张确认介质

仅在电脑队列选择A5不够：打印机自身纸盒也必须登记为A5普通纸。现场此前纸盒仍为A4，导致每张等待按OK。配置命令：

```sh
python3 scripts/configure_hp_media.py --host <打印机IPv4地址>
```

此脚本通过该型号真实的内置网页表单，将纸盒1、2设为A5普通纸，关闭手动进纸、尺寸确认提示，保存A5横向进纸；其余表单字段保持不变。若更换纸张用途，请重新按实际装纸配置纸盒。

HP固件收到`Connection: close`时可能提前截断动态设置页面；脚本使用keep-alive读完表单，保存后逐项回读，不能把截断响应当作完整页面。程序打印时显式发送`media=iso_a5_148x210mm`、`media-type=stationery`、`media-source=auto`、`orientation-requested=3`和一份。

## 使用

### 左上角“照片墙与打印”

- 照片数量设为0时自动按屏幕可用高度容纳；可指定1至20张。数量越少照片越大、墙越宽，数量越多墙越窄，宽度最多占窗口45%，保留实时主画面。窗口横竖变化时重新适配。照片始终从新到旧、完整显示，无滚动条；超出可见数量只从墙上移出，不删除原图。
- 选择已配置的CUPS打印机；“刷新打印机”重新读取列表。未发现的已保存打印机仍显示出来，不会悄悄改用其他队列。
- 勾选“只生成PDF，不打印”后，后续拍照仍保存原有照片和A5报纸PDF，但不调用打印程序；任务记录为`pdf_only`。取消勾选后，后续拍照发送到选定打印机。
- 点击“应用并保存”，选项保存在`service/festival-settings.json`，重启后保留，该文件不进入Git。已进入后台处理的照片沿用拍摄时的选项，修改设置不会改变既有打印任务。

**M452nw横放A5纸的关键设置**：打印机内置网页“打印”页面的“A5进纸方向”必须选择“横向”（内部字段 `A5FeedOrientation=Landscape`），并点击应用。该选项决定实际进纸长短边，不能用CUPS的文档横/竖方向代替。报纸PDF和CUPS文档方向保持竖版（`orientation-requested=3`）。现场已回读确认进纸方向保存为横向；此前仅修改CUPS方向不能解决纸张提前走完、下半截缺失的问题。

打印机先开机并放置A5纸。比出✌并保持约半秒，倒计时3秒后拍摄新的动漫画面。放下手约一秒后才能再次触发，保持同一手势不会连续打印。按钮和空格也能触发。照片不包含倒计时、照片墙或信息面板。

每次拍照生成一张A5竖版PDF，包含学校提供的校徽、指定标题、日期和照片。照片墙从上往下按最新到最旧排列，不使用滚动条；默认自动适配可容纳的数量，可在左上角设置中指定显示数量，照片和PDF在本地 `service/captures/<时间-编号>/` 保存。目录不进入Git。`record.json` 保存打印提交结果；断电或提交结果不明时不自动重复提交。正常提交后的离线作业由CUPS等待打印机恢复，无须再次拍照。

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
sudo lpadmin -p S100_Festival -o media-default=iso_a5_148x210mm -o orientation-requested-default=3 -o sides-default=one-sided -o HPPJLColorAsGray-default=off -o print-color-mode-default=color -o printer-is-shared=false
```

程序每次用 `lp -d S100_Festival -n 1` 显式指定A5、竖版文档、单面和彩色。纸盒中的物理放纸方向与PDF页面方向是两件事，纸盒纸型必须设置为A5。断电或拔线时已有任务等待重连，不要重复发送同一照片。

现场测试可以向正在运行的显示进程发送一次SIGUSR1，走同一个倒计时/拍摄/打印流程；该信号仅为本地管理员测试入口。开机启动和手动关闭后不重开的策略未改。
