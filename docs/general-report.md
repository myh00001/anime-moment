# 通用看图报道

默认使用 InternVL3-2B-Instruct Q8 读取同次摄像头原图，描述可见人物、动作、表情或环境；Qwen3-0.6B Q8 同时生成科技节背景句，组合为短报道。默认入口不使用服装分类器。图像和推理均留在本机，服务仅监听回环地址。

拍摄后保留定格和等待动画，暂时释放动漫及手势 BPU 模型，再用独占的 BPU 视觉编码器处理原图。语言解码器保持预热，编码进程清理与解码重叠；完成后恢复原模型预览和手势检测。无法使用 BPU 桥接时回退同一大模型的 CPU 视觉路径，记录 acceleration_fallback，耗时会增加。

优化前实拍报道 28.20 秒、含倒计时到 PDF 32.76 秒。候选两次真实拍照到可打印 PDF 为 11.148、13.140 秒，正式部署后连续两次为 14.424、10.968 秒；这些数字不含拍照前倒计时或打印机出纸时间，也不保证所有场景都低于 15 秒。测试使用 PDF-only 并恢复原打印设置，没有额外出纸。通用动作、表情和环境识别尚无独立大样本准确率，不能沿用旧服装分类准确率；遮挡、小目标和细手势仍可能误判。

权重留在板端 local-vlm，不随 Git 发布。需要 internvl2b-candidate 下的 language.gguf、mmproj.gguf、vision.hbm，以及 Qwen3-0.6B-Q8_0.gguf。默认 2B；FESTIVAL_GENERAL_VLM_SIZE=1B 可选择已有 1B CPU 路径。资源目录从服务文件所在位置定位。

BPU 视觉特征桥接使用可选 S100_VLM_EMBED_FILE，严格检查特征形状、长度和有限值；每次原图独立编码，禁用跨图提示缓存。已有 llama.cpp-b11669 源码时，可运行 scripts/build_general_report_bridge.py --root <服务目录>，构建隔离运行时 build-general-report；成功验证后才写入启用标记。原 CPU 运行时不覆盖。编码器只在拍摄后的独占阶段加载，预热只加载语言解码器。

## S100 语言 BPU 兼容性检查（2026-10-24）

本轮完成接口与模型格式检查，没有获得完整语言 BPU 推理或加速结果，未替换生产运行时。板端未发现 libxlm、oellm_build 或已编译的语言 HBM；现有 InternVL HBM 是视觉编码器。

核对官方 D-Robotics_LLM_S100_1.0.0_Doc.zip 中的 API 枚举，XLM_MODEL_TYPE_INTERNVL=0 注释明确为 `not support yet`。其 oellm_build 手册的模型选项只有 deepseek-qwen-1_5b、deepseek-qwen-7b、qwen2_5-1_5b、qwen2_5-7b、internlm2-1_8b、qwen2_5-omni-3b，没有 Qwen3。InternVL3-2B 的官方配置中 llm_config 为 Qwen2ForCausalLM，但这不能证明整个 VLM 或外部视觉特征注入已受 SDK 支持。未发现当前公开接口可以直接衔接现有 256×1536 视觉特征。

官方 oellm_server 的 model-type 0 名称也不能作为支持证据：README 明确当前 HTTP 接口只实现文字聊天，InternVL 图像输入需另外扩展。S600 的 Qwen3/InternVL 支持和性能表不可当作 S100 的可用模型或性能。上述结论限定于此次核对的公开 S100 SDK 1.0.0，不代表未来版本或其他适配永远不支持。

保留上一轮 BPU 视觉编码 + CPU 语言生成。后续只有取得适配 S100 nash-e 的编译器、权重和视觉输入接口后，才可对同图进行准确性与延迟对照；不能把更换成普通 Qwen2.5 文字模型当作同一个看图模型的加速。

来源：[S100 SDK](https://developer.d-robotics.cc/rdk_s_doc/Advanced_development/toolchain_development/LLM_Toolchain/rdk_s100/s100_LLM_Toolchain)、[API 枚举](https://developer.d-robotics.cc/oe_llm_s100p_doc/guide/api/api_details/structure_and_enumeration_type.html)、[编译器参数](https://developer.d-robotics.cc/oe_llm_s100p_doc/guide/tool_introduction/oellm_build)、[官方服务源码](https://github.com/D-Robotics/oellm_server/tree/develop)。

补充：通用编译器的第一阶段自适配已在板端运行真实 QKV 投影，见[实验记录](experimental-language-bpu.md)。这验证了单块计算可自行适配，不改变上述完整 SDK 接口限制，也尚未构成生产语言 BPU 后端。
