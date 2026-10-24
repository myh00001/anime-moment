# 自适配语言 BPU：第一阶段

2026-10-24，绕开尚未支持完整 InternVL3 的官方 LLM SDK，使用已安装的通用 hb_compile/hbdk4 工具链，为 S100 nash-e 编译并运行当前 InternVL3-2B Q8 GGUF 中第一层的真实 Q/K/V 权重。

这不是完整的语言 BPU 后端。生产程序仍使用 BPU 视觉编码 + CPU 语言生成；没有替换模型、风格、界面或打印配置。

## 已验证的范围

Q、K、V 的三个线性投影合并成一个 2048×1536 投影，将 token 轴作为空间轴，用 1×1 Conv 执行。包含原始 bias，数值与逐 token 的线性投影相同；单元测试覆盖单 token、多 token 的布局和 bias。输入为 FLOAT32 NCHW，256 token 时为 1×1536×1×256。编译器报告核心 Conv 位于 BPU，辅助处理包含 VPU。

使用真实视觉编码结果并经过第一层原始 RMSNorm 权重归一化：六份板端已有原图特征中，三份用于校准，另外三份用于数值验证。不生成新照片、不出纸，不公开图片、特征、权重或逐图内容。三份验证特征曾在最初的合成校准版本上测试过，因此这些数值不是独立识图准确率实验。

| 单块实验 | BPU 调用中位耗时（包含 Python 封装与数据复制） | CPU 浮点 NumPy BLAS 参考 |
|---|---:|---:|
| 256 token，真实特征，真实校准 | 1.643–1.671 ms | 13.419–14.003 ms |
| 1 token，合成特征，合成校准 | 0.650–0.718 ms | 0.341–0.346 ms |

真实特征校准后的三份验证结果：余弦相似度 0.9999802–0.9999809，relative L2 误差 0.6175%–0.6290%。合成校准时，六份真实特征的 relative L2 为 1.33%–2.73%，说明必须使用真实激活校准。最大幅值更大的输入仍可能裁剪，后续层也会累积误差。

CPU 参考是浮点矩阵乘法，不是生产 llama.cpp 的 Q8 解码器；这不能推导出整个模型快八倍。单 token 的 BPU 调用反而更慢，后续应优先验证成批预填充，不能把所有小矩阵逐个交给 BPU。

## 复现实验

依赖：导出端 gguf/numpy/onnx，单元测试 onnxruntime，Linux 编译端已有匹配 nash-e 的 hb_compile，板端已有 HB_HBMRuntime。模型权重和中间产物必须保存在 Git 仓库之外，优先 D 盘或板端私有目录。导出器也会在输出目录写入忽略所有文件的 .gitignore。

```sh
python scripts/export_language_qkv.py \
  --gguf /private/InternVL3-language-Q8_0.gguf \
  --output /private/qkv-prefill --tokens 256
```

对单 token 使用 `--tokens 1` 和独立输出目录。导出包括 ONNX、真实投影/RMSNorm 权重、合成校准样本和维度说明。不是重新训练模型，也没有把模型换成服装分类器。

256 token 的 hb_compile 配置示例：

```yaml
model_parameters:
  onnx_model: /private/qkv-prefill/layer0_qkv_t256.onnx
  march: nash-e
  working_dir: /private/qkv-prefill/build
  output_model_file_prefix: layer0_qkv_t256
input_parameters:
  input_name: hidden
  input_type_rt: featuremap
  input_type_train: featuremap
  input_layout_train: NCHW
  input_shape: 1x1536x1x256
calibration_parameters:
  cal_data_dir: /private/qkv-prefill/calibration
  calibration_type: max
compiler_parameters:
  compile_mode: latency
  optimize_level: O2
  core_num: 1
  jobs: 2
```

运行 `hb_compile -c config.yaml`。真实校准改用另存的实际 post-RMSNorm NCHW 激活目录，并使用独立 build 目录，保留原始版本供对照。

将 HBM、projection-private.npz 和基准脚本放到板端私有实验目录，停止竞争的 BPU 工作负载后执行：

```sh
python benchmark_language_qkv.py --root /path/to/installed/service \
  --artifacts /private/qkv-prefill --tokens 256 \
  --model /private/qkv-prefill/layer0_qkv_t256.hbm
```

`--inputs /private/validation-activations` 可改测未参与校准的真实激活。CPU 与 BPU 分阶段计时，避免 BLAS 活跃等待线程污染 BPU 耗时；误差使用 float64 累加以免余弦相似度因精度问题超过 1。基准脚本本身不停止或启动相机，操作者必须保证实验结束恢复原先正在运行的应用，保留手动关闭不重开策略。

## 下一阶段的验收要求

1. 扩展到更占计算量的 FFN，并确认真实激活量化范围、误差和复制开销。
2. 在隔离的 llama.cpp 中衔接预填充计算，处理长度分桶、剩余 token、RMSNorm、RoPE、attention 和 KV cache，保留单 token CPU 路径供对照。
3. 对齐 logits、下一 token 和完整原图报道，再测拍摄到 PDF 的总时间。单块数值接近不代表语言输出准确率通过；整体速度和质量通过前不得替换生产后端。
