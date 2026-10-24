# 通用看图报道

默认报道入口已经从 FashionSigLIP 服装分类和模板切换为两阶段本地大模型：

1. InternVL3-2B-Instruct Q8 读取本次拍摄的摄像头原图，提取可见人物状态、动作、表情或环境事实。
2. Qwen3-0.6B Q8 使用观察结果和科技节背景撰写一段中文短报道。

当前稳定路径使用 CPU 看图与 CPU 写作。实时动漫推理仍沿用原模型；拍后保持现有定格和等待流程。没有网络图像上传；写作服务仅监听回环地址。默认路径不调用服装分类器，失败时使用报纸既有固定说明继续生成 PDF，不会回退到服装分类报道。

测试：默认路由、原图路径、异常回退 2 项测试及原有 local_report 14 项测试通过。最终 InternVL3-2B 真实拍照链路：报道生成 28.20 秒，含模型加载；倒计时到可打印 PDF 共 32.76 秒。测试确认使用 original.jpg、生成状态成功、等待期间画面定格，测试临时 PDF-only 并恢复原打印设置；没有额外出纸。这不满足此前 10 秒目标。尚未完成通用表情、动作和环境独立准确率评估，不能沿用服装分类的旧准确率。遮挡、小目标和细手势仍可能误判。

权重保留板端 local-vlm，不随 Git 发布。需要 internvl2b-candidate/language.gguf、internvl2b-candidate/mmproj.gguf、Qwen3-0.6B-Q8_0.gguf 和支持 InternVL 的 llama-server。环境变量 FESTIVAL_GENERAL_VLM_SIZE=1B 可选择已有 1B 权重；默认 2B。report_general_vlm.py 从其所在服务目录定位资源，兼容运行目录更名。
