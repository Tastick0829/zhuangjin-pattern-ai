# LoRA 训练参数详解与迭代记录

> 本文件记录 6 组训练参数的**演进过程**与**每一项取舍的理由**。参数文件全部保留在 [`../training/`](../training/)，按时间戳命名。
>
> 保留全部失败实验而不只留最终版，是刻意的——**调参过程本身是技术贡献的一部分**。

---

## 一、参数迭代轨迹（按时间戳排序）

6 组参数不是并列选项，而是**一条收敛路径**：

| # | 文件 | 类型 | 底模 | 分辨率 | dim/alpha | epochs | batch | 名称 | 阶段判断 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `1747133205560.toml` | `flux-lora` | `./sd-models/model.safetensors` | 768×768 | 2 / 16 | 20 | 1 | Tastick | 起步实验 |
| 2 | `1747304252988.toml` | `sd-lora` | `flux1-dev-fp8_unet.safetensors` | 512×512 | **32 / 32** | 10 | 1 | Tastick | 走弯路 |
| 3 | `1747306010497.toml` | `sd-lora` | 同上 | 512×512 | 32 / 32 | 10 | 1 | Tastick | 重复试验 |
| 4 | `1747309340434.toml` | (未标注) | 同上 | 512×512 | 32 / 32 | 10 | 1 | **aki** | 改名重跑 |
| 5 | `1747453743012.toml` | `flux-lora` | `flux1-dev_unet.safetensors` | **768×768** | 2 / 16 | 20 | 1 | aki | 回归正轨 |
| 6 | **`1747465671967.toml`** | `flux-lora` | `flux1-dev_unet.safetensors` | 512×512 | 2 / 16 | 20 | **15** | Tastick | ⭐ **最终版** |

### 演进解读

**阶段 A（#1）**：直接用 Flux 官方训练类型起步，但底模路径是占位符 `./sd-models/model.safetensors`，且 768×768 对显存压力大、batch=1 训练慢。

**阶段 B（#2–#4）→ 关键弯路**：
- 把 `model_train_type` 从 `flux-lora` 改成 `sd-lora`
- 换上 `flux1-dev-fp8_unet.safetensors`（fp8 量化版）
- `network_module` 从 `networks.lora_flux` 退回 `networks.lora`
- `dim/alpha` 从 2/16 猛增到 **32/32**
- `network_train_unet_only` 由 `true` 改为 `false`
- 关闭了 `gradient_checkpointing`

这组改动方向是**错的**：用 SD 的 LoRA 实现去训练 Flux 底模，等于**架构不匹配**。`networks.lora` 是为 SD 的 UNet/CLIP 结构写的注入逻辑，而 Flux 是双流（DoubleStreamBlock）+ 单流（SingleStreamBlock）的 DiT 架构，必须用 `networks.lora_flux`。

后果：训练能跑（不报错），但风格注入效果差或不稳定。这也是为什么 #2–#4 连做了三次却仍是"重复试验"——**在小参数上微调，没换本质思路**。

**阶段 C（#5–#6）→ 回归并收敛**：
- `model_train_type` 改回 `flux-lora`
- `network_module` 改回 `networks.lora_flux`
- 底模换成**非量化的** `flux1-dev_unet.safetensors`（避免 fp8 在训练中的精度损失）
- `dim/alpha` 回到 2/16
- `network_train_unet_only = true`（只训练 UNet，不碰文本编码器）
- `gradient_checkpointing = true`（省显存）
- 最终把 `train_batch_size` 从 1 提到 **15**（512×512 分辨率下显存可容纳）

> **这段弯路的教训值得记下来**：`model_train_type`、`network_module`、底模三者必须**架构一致**。见"三、最常见的三个坑"。

---

## 二、最终版参数逐项解读

以 `1747465671967.toml` 为准：

### 2.1 模型与路径

```toml
model_train_type = "flux-lora"
pretrained_model_name_or_path = "/root/autodl-tmp/lora-scripts/sd-models/unet/flux1-dev_unet.safetensors"
ae     = "/root/autodl-tmp/lora-scripts/sd-models/vae/ae.safetensors"
clip_l = "/root/autodl-tmp/lora-scripts/sd-models/clip/clip_l.safetensors"
t5xxl  = "/root/autodl-tmp/lora-scripts/sd-models/clip/t5xxl_fp16.safetensors"
```

| 项 | 说明 |
| --- | --- |
| `flux-lora` | 必须与 `networks.lora_flux` 配套 |
| `flux1-dev_unet.safetensors` | Flux 的 UNet（DiT）主干，**非量化版** |
| `ae.safetensors` | Flux 专用 VAE（自动编码器） |
| `clip_l` + `t5xxl_fp16` | Flux 用**双文本编码器**：T5 负责长文本语义，CLIP-L 负责短标签 |

### 2.2 网络结构（LoRA 核心）

```toml
network_module = "networks.lora_flux"
network_dim   = 2
network_alpha = 16
network_train_unet_only = true
```

| 参数 | 值 | 为什么 |
| --- | --- | --- |
| `network_dim` | **2** | 刻意压到极小。目标不是让模型"背下"纹样，而是注入轻量风格倾向，避免过拟合 |
| `network_alpha` | **16** | alpha/dim = 8，缩放系数较大，让低秩矩阵的输出幅度足够 |
| `network_train_unet_only` | `true` | 只训练 UNet，不训练文本编码器。**LoRA 微调图像的常规做法**——改"画法"而非"理解力" |

> `dim=2` 的取舍：好处是体积小（数十 KB 级）、过拟合风险低；代价是风格表达能力有限。若生成风格不够鲜明，可提到 8/16 并重新评估。

### 2.3 训练规模

```toml
resolution = "512,512"
max_train_epochs = 20
train_batch_size = 15
gradient_accumulation_steps = 1
save_every_n_epochs = 2
```

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `resolution` | 512×512 | 与数据集预处理（BIRME 缩放）一致。**训练分辨率必须匹配数据准备的分辨率** |
| `max_train_epochs` | 20 | 配合 batch=15，实际步数仍属"验证可行性"量级 |
| `train_batch_size` | 15 | 从 batch=1 提上来的——这是最终版相对 #5 的关键改动，训练效率提升 15 倍 |
| `save_every_n_epochs` | 2 | 每 2 epoch 存一次，便于挑最优 checkpoint |

### 2.4 优化器与学习率

```toml
optimizer_type = "AdamW8bit"
learning_rate = 0.0001      # 1e-4
unet_lr = 0.0001
text_encoder_lr = 0.00001   # 1e-5
lr_scheduler = "cosine_with_restarts"
lr_warmup_steps = 0
lr_scheduler_num_cycles = 1
```

| 参数 | 值 | 为什么 |
| --- | --- | --- |
| `AdamW8bit` | 8bit 量化 AdamW | **显存友好**，训练 Flux 这种大模型的关键技巧，精度损失可接受 |
| `unet_lr` 1e-4 | UNet 学习率 | LoRA 训练的常用档位 |
| `text_encoder_lr` 1e-5 | 文本编码器 | 比 UNet **低一个数量级**——文本编码器已经很强，动太多会破坏语义理解（本项目中它其实没被训练） |
| `cosine_with_restarts` | 余弦退火 + 重启 | 前期快速下降，后期精细收敛；重启有助于跳出局部最优 |
| `num_cycles = 1` | 1 个周期 | 训练步数少，多周期没意义 |

### 2.5 Flux 专属参数

```toml
timestep_sampling = "sigmoid"
sigmoid_scale = 1
model_prediction_type = "raw"
discrete_flow_shift = 1
guidance_scale = 1
loss_type = "l2"
train_t5xxl = false
```

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `timestep_sampling` | `sigmoid` | Flux 训练推荐采样方式，让不同噪声水平被更均匀地训练 |
| `model_prediction_type` | `raw` | Flux 预测的是 flow（速度场）而非噪声，需用 raw |
| `guidance_scale` | 1 | 训练时关闭 CFG（推理时才用 FluxGuidance） |
| `train_t5xxl` | `false` | **T5 太大（数 GB），不训练**，只作为冻结的文本编码器 |
| `loss_type` | `l2` | 标准 MSE |

### 2.6 性能优化

```toml
mixed_precision = "bf16"
save_precision = "fp16"
fp8_base = true
sdpa = true
gradient_checkpointing = true
cache_latents = true
cache_latents_to_disk = true
cache_text_encoder_outputs = true
cache_text_encoder_outputs_to_disk = true
persistent_data_loader_workers = true
```

| 参数 | 效果 |
| --- | --- |
| `mixed_precision = bf16` | 训练用 bfloat16，比 fp16 数值范围更宽、更稳 |
| `save_precision = fp16` | 保存时用 fp16 省体积 |
| `fp8_base = true` | 底模以 fp8 加载，**大幅省显存** |
| `sdpa` | 使用 PyTorch 的 Scaled Dot-Product Attention，比默认实现快 |
| `gradient_checkpointing` | 用计算换显存，大模型训练必备 |
| **全部 `cache_*`** | 把 VAE 编码结果与文本编码结果**预先算好缓存到磁盘**，避免每步重复计算——**训练加速的关键** |
| `persistent_data_loader_workers` | 复用 dataloader worker，减少启动开销 |

### 2.7 其他

```toml
caption_extension = ".txt"
shuffle_caption = false
keep_tokens = 0
seed = 1337
clip_skip = 2
prior_loss_weight = 1
output_name = "Tastick"
save_model_as = "safetensors"
```

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `caption_extension` | `.txt` | 与 `prompts/captions/*.txt` 对应 |
| `shuffle_caption` | `false` | **不洗牌**。打标是固定模板（`prompts/captions/` 里 12 份内容完全一致），洗牌无意义 |
| `keep_tokens` | 0 | 不保留固定前缀（若想让某些 tag 始终靠前可设为 tag 数） |
| `clip_skip` | 2 | 取 CLIP 倒数第二层输出，风格化任务常用 |
| `output_name` | Tastick | 输出权重命名 |

---

## 三、最常见的三个坑（本项目都踩过或险些踩）

### 坑 1：三者架构必须一致

```toml
model_train_type = "flux-lora"        # ← 训练类型
network_module = "networks.lora_flux" # ← 网络注入实现
pretrained_model_name_or_path = ".../flux1-dev_unet.safetensors"  # ← 底模
```

**这三处必须同时指向 Flux**。任意一处用了 SD 的（`sd-lora` / `networks.lora` / SD 底模），就是架构不匹配——训练能跑，效果打折或不稳定。本项目 #2–#4 就是这么绕了三轮。

### 坑 2：训练分辨率必须与数据准备一致

数据集用 BIRME 缩到 512×512（见 `docs/02-dataset.md`），训练就应设 `resolution = "512,512"`。#1 与 #5 用了 768×768，与数据不匹配会被迫缩放，损失细节还浪费算力。

### 坑 3：`model_train_type` 与底模量化版本的关系

`flux1-dev-fp8_unet.safetensors`（fp8 量化）适合**推理**，训练时用非量化的 `flux1-dev_unet.safetensors` 精度更稳。最终版选了非量化版 + `fp8_base = true`（训练时再把底模以 fp8 加载省显存）——这是兼顾精度与显存的正确组合。

---

## 四、复现步骤

```bash
# 1. 环境（AutoDL 或本地 GPU）
git clone https://github.com/kohya-ss/sd-scripts
cd sd-scripts
pip install -r requirements.txt

# 2. 准备底模（放到脚本期望的路径）
#    flux1-dev_unet.safetensors / ae.safetensors / clip_l.safetensors / t5xxl_fp16.safetensors

# 3. 准备数据集
#    train/aki/xxx.png  +  train/aki/xxx.txt（内容取自 prompts/captions/）

# 4. 复制参数并修改路径
cp training/1747465671967.toml my_train.toml
# 编辑 my_train.toml：改 pretrained_model_name_or_path / train_data_dir 为你自己的路径

# 5. 启动训练
accelerate launch --num_cpu_threads_per_process 8 \
  sdxl_train_network.py --config_file my_train.toml
```

> 具体启动脚本因 sd-scripts 版本而异，以你所用版本的文档为准。核心是 `--config_file` 指向本仓库的 toml。

---

## 五、评估与改进方向

**当前缺口**：没有量化评估。仅凭主观判断"看起来像壮锦"不足以支撑结论。

### 建议补充的评估

| 维度 | 方法 |
| --- | --- |
| 分布相似度 | FID（生成图 vs 真实纹样） |
| 语义一致性 | CLIP Score（图与提示词的匹配度） |
| 风格保真度 | 人工评分量表（壮锦特征保留程度 1–5 分） |
| 多样性 | LPIPS 或生成结果的聚类分布 |
| **消融实验** | 对比 `dim=2` vs `dim=8` vs `dim=16`、LoRA 开关、不同 `guidance` |

### 值得尝试的参数方向

1. **提高 `network_dim`** 到 8/16，看风格强度是否提升（配合过拟合监控）
2. **增大数据集规模**，当前规模下 batch=15 使总步数偏少
3. **引入对照组**：用非壮锦数据训练同等规模 LoRA，验证风格注入的特异性
4. **加 `keep_tokens`**：若希望"壮锦"类关键词始终被优先学习，可固定前缀 tag

---

## 相关文档

- 数据集构建 → [`02-dataset.md`](./02-dataset.md)
- 工作流与推理 → [`04-workflow.md`](./04-workflow.md)
- 参数文件清单 → [`../training/README.md`](../training/README.md)
