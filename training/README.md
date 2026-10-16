# 训练参数文件清单

> 本目录保留了 **6 组**训练参数（按时间戳命名），完整记录了调参的收敛过程。
>
> 参数逐项解读与踩坑分析见 [`../docs/03-training.md`](../docs/03-training.md)。

---

## 参数对照表

| 文件 | 类型 | 底模 | 分辨率 | dim/alpha | epochs | batch | 输出名 | 阶段 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1747133205560.toml` | `flux-lora` | `./sd-models/model.safetensors`（占位） | 768×768 | 2 / 16 | 20 | 1 | Tastick | 起步 |
| `1747304252988.toml` | `sd-lora` | `flux1-dev-fp8_unet` | 512×512 | 32 / 32 | 10 | 1 | Tastick | 弯路 |
| `1747306010497.toml` | `sd-lora` | `flux1-dev-fp8_unet` | 512×512 | 32 / 32 | 10 | 1 | Tastick | 弯路 |
| `1747309340434.toml` | — | `flux1-dev-fp8_unet` | 512×512 | 32 / 32 | 10 | 1 | aki | 弯路 |
| `1747453743012.toml` | `flux-lora` | `flux1-dev_unet` | 768×768 | 2 / 16 | 20 | 1 | aki | 回归 |
| **`1747465671967.toml`** | **`flux-lora`** | **`flux1-dev_unet`** | **512×512** | **2 / 16** | **20** | **15** | **Tastick** | ⭐ **最终版** |

---

## 参数演进的三条主线

### 主线 1：训练类型回归正轨

```text
flux-lora  ──>  sd-lora  ──>  flux-lora
   #1            #2~#4          #5~#6
```

中间三轮尝试用 SD 的 LoRA 实现（`networks.lora`）训练 Flux 底模，属于**架构不匹配**——Flux 是 DiT 双流架构，必须用 `networks.lora_flux`。训练能跑但不报错的坑就在这。

### 主线 2：LoRA 容量从激进回归克制

```text
dim=2, alpha=16  ──>  dim=32, alpha=32  ──>  dim=2, alpha=16
      #1                    #2~#4                    #5~#6
```

小数据集下 `dim=32` 过拟合风险高。最终回到 `dim=2` 是**刻意的克制**：目标是注入风格倾向，不是让模型背下纹样。

### 主线 3：批大小提升带来训练效率跃升

```text
batch=1  ──>  batch=1  ──>  batch=15
  #1           #2~#5          #6 ⭐
```

最终版把 `train_batch_size` 从 1 提到 15——在 512×512 分辨率下显存足以容纳，训练效率提升 15 倍。这是 #6 相对 #5 的关键改动。

---

## 各文件用途

| 想做什么 | 用哪个 |
| --- | --- |
| **复现最终训练** | `1747465671967.toml`（改路径后直接用） |
| 研究调参过程 | 全部 6 个，按时间戳顺序读 |
| 对比高低分辨率差异 | `1747453743012.toml`（768）vs `1747465671967.toml`（512） |
| 看容量对风格的影响 | `1747304252988.toml`（dim=32）vs `1747465671967.toml`（dim=2） |

---

## 使用前必须修改的项

参数文件里的路径是**训练时的云端环境路径**，直接使用会失败：

```toml
pretrained_model_name_or_path = "/root/autodl-tmp/lora-scripts/sd-models/unet/flux1-dev_unet.safetensors"
ae     = "/root/autodl-tmp/lora-scripts/sd-models/vae/ae.safetensors"
clip_l = "/root/autodl-tmp/lora-scripts/sd-models/clip/clip_l.safetensors"
t5xxl  = "/root/autodl-tmp/lora-scripts/sd-models/clip/t5xxl_fp16.safetensors"
train_data_dir = "./train/aki"
output_dir = "./output"
logging_dir = "./logs"
```

| 项 | 要改成 |
| --- | --- |
| 四个模型路径 | 你本地/云端实际的权重位置 |
| `train_data_dir` | 你的数据集目录（结构见 `../docs/02-dataset.md`） |
| `output_dir` / `logging_dir` | 你的输出目录 |

---

## 启动训练

```bash
# 以 sd-scripts 为例
accelerate launch --num_cpu_threads_per_process 8 \
  sdxl_train_network.py --config_file /path/to/1747465671967.toml
```

> 启动脚本名与参数因 sd-scripts 版本而异，以你所用版本的文档为准。关键是 `--config_file` 指向本目录的 toml。

---

## 参数合法性自检

用以下命令快速检查三处架构一致性（**最容易出错的地方**）：

```bash
grep -E "model_train_type|network_module|pretrained_model_name_or_path" *.toml
```

三者必须同时指向 Flux：

- `model_train_type = "flux-lora"`
- `network_module = "networks.lora_flux"`
- `pretrained_model_name_or_path` 指向 `flux1-dev*`

若出现 `sd-lora` 或 `networks.lora`（无 `_flux` 后缀），即为架构不匹配。

---

## 相关文档

- **参数逐项解读** → [`../docs/03-training.md`](../docs/03-training.md)
- 数据集准备 → [`../docs/02-dataset.md`](../docs/02-dataset.md)
- 推理工作流 → [`../docs/04-workflow.md`](../docs/04-workflow.md)
