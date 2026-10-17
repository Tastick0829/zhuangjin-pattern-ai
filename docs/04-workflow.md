# ComfyUI 工作流拆解

> 仓库内 `workflow/comfyui/` 下共 5 套工作流 JSON（另有 1 套变体在 `variant/`）。本文件说明每套的用途、节点结构，以及三代工作流的演进逻辑。
>
> **工作流是本项目的核心技术资产**——它把"纹样生成"从一次性的脚本调用，变成可视化、可复用、可 API 化的编排资产。

---

## 一、三代工作流演进

| 代 | 文件 | 底模 | 关键节点 | 用途 |
| --- | --- | --- | --- | --- |
| **一代** | `01-txt2img-anythingv5.json` | `AnythingV5V3_v5v3` | `CheckpointLoaderSimple` + `CLIPTextEncode` ×2 + **`LoraLoader`** | 早期文生图，试挂 LoRA |
| **二代** | `02-img2img-v1.json`、`(1)` | `AnythingV5V3_v5v3` | `VAEEncode` + `ImageScaleBy` + `VAEDecode` + `PreviewImage` | **图生图**（风格化再造） |
| **三代** | `03-flux-mug-product.json` | **`星芒Anything_万物皆可FLUX_V1`** | `UNETLoader` + `DualCLIPLoader` + `VAELoader` + **`FluxGuidance`** | 最终版：Flux 架构 + 产品载体 |

### 演进逻辑

```text
一代：能生成就行
  └─> 问题：SD1.5 底模（AnythingV5）对几何对称纹样控制弱

二代：加上图生图
  └─> 思路：既然底模不够懂壮锦，那就给参考图，让它"照着改"
  └─> 问题：denoise 控制不当会导致"改太少像复制、改太多不像壮锦"

三代：换 Flux + 完整架构
  └─> 换 UNETLoader 加载 Flux 专用 UNet
  └─> DualCLIPLoader 同时挂 t5xxl + clip_l（Flux 双编码器）
  └─> FluxGuidance 单独控制引导强度（Flux 特有）
  └─> 新增产品载体节点（马克杯模板合成）
```

> 三代全部保留而非只留最终版——**能看到思路如何一步步修正**，这比只给结论有价值。

---

## 二、三代工作流详解

### 2.1 一代：文生图 + LoRA 挂载

**文件**：`01-txt2img-anythingv5.json`

**节点链**：

```text
CheckpointLoaderSimple (AnythingV5V3_v5v3)
      ├─ MODEL ─> LoraLoader ─> KSampler
      │              (陆李测试的烂模型。。。_v114514, 1, 1)
      └─ CLIP ──> LoraLoader ─> CLIPTextEncode(正) ─> KSampler
                              └─ CLIPTextEncode(负) ─> KSampler
KSampler ─> VAEDecode ─> SaveImage
```

**关键信息**：

| 项 | 值 |
| --- | --- |
| 底模 | `AnythingV5V3_v5v3`（SD1.5 架构的二次元模型） |
| LoRA | `陆李测试的烂模型。。。_v114514`，权重 1, 1 |
| 正向提示词 | `Traditional Zhuang brocade, 512x512, symmetrical geometric patterns, dark blue background, vibrant red yellow pink colors, diamond/square/triangle nesting, cloud fret patterns, central geometric motif with butterfly flower accents, layered composition, ethnic decorative art style, high contrast, bold colors` |
| 负向提示词 | `text, watermark, embedding:bad-picture-chill-75v, ` |

> **注意**：LoRA 名称本身是实验期的随手命名，不代表最终质量。这正是"保留演进痕迹"的意义。

**为什么这套被替换**：SD1.5 底模对**几何规律性**（菱形嵌套、四方连续）的保持能力弱，这是架构层面的限制，加提示词也补不回来。

---

### 2.2 二代：图生图（风格化再造）

**文件**：`02-img2img-v1.json`、`02-img2img-v2.json`

**节点链**：

```text
LoadImage ─> ImageScaleBy ─┬─> PreviewImage（看输入）
                           └─> VAEEncode ─> KSampler(denoise<1) ─> VAEDecode ─> SaveImage
                                                    ▲
CLIPTextEncode(正/负) ──────────────────────────────┘
```

**核心机制**：`VAEEncode` 把输入图编码到潜空间，`KSampler` 从**这个潜变量**出发（而不是从纯噪声），配合 `denoise < 1` 做部分去噪——结果就是**保留输入图的基本结构，替换风格细节**。

| 参数 | 作用 |
| --- | --- |
| `ImageScaleBy` | 调整输入尺寸到生成分辨率 |
| `VAEEncode` | 图像 → 潜空间（图生图的前提） |
| `denoise` | **最关键**：控制"改多少"。低了像复制，高了像无关新图 |

> **这是本项目技术路线上的一个关键选择**：让 AI 做"风格化再造"而非"无中生有"。原因是壮锦纹样有强烈的文化语义与固定母题，从零生成极易产出"看起来像民族风但不是壮锦"的结果。给参考图 = 给文化锚点。

---

### 2.3 三代：Flux 架构 + 产品载体

**文件**：`03-flux-mug-product.json`（对应应用层 `/generate` 调用的工作流）

**节点链**：

```text
UNETLoader ("星芒Anything_万物皆可FLUX_V1", fp8_e4m3fn) ─> MODEL ─┐
DualCLIPLoader (t5xxl_fp8_e4m3fn + clip_l, type=flux) ─> CLIP ──┼─> FluxGuidance(3.5) ─┐
VAELoader ("ae.sft") ──────────────────────────> VAE ──────────┼──────────────────────┼─> KSampler
CLIPTextEncode(正) ────────────────────────────────────────────┤                      │
CLIPTextEncode(负) ────────────────────────────────────────────┘                      │
LoadImage ─> ImageScaleBy ─> VAEEncode ────────────────────────────────────────────────┘
                                                                                        │
                                              KSampler ─> VAEDecode ─> SaveImage / 产品合成
```

**三代的两个架构升级**：

| 升级 | 一代/二代 | 三代 |
| --- | --- | --- |
| **底模加载** | `CheckpointLoaderSimple`（一体化 ckpt） | **`UNETLoader` + `DualCLIPLoader` + `VAELoader`** 三段式 |
| **引导控制** | KSampler 内置 cfg | **独立的 `FluxGuidance` 节点** |

**为什么要三段式加载**：Flux 的权重是**分开发布的**（UNet / 文本编码器 / VAE 各自独立文件），不像 SD1.5 打成一个 `.ckpt`。这带来更大的组合自由度——可以换 VAE、换 CLIP 而不动主干。

**为什么 `FluxGuidance` 独立**：Flux 采用 **distilled guidance** 机制，引导强度作为条件注入模型（而非 KSampler 的 cfg 参数）。本工作流设 **3.5**——值越高越贴合提示词，但过高会让色彩僵硬、失去纹样自然感。

**关键参数汇总**：

| 节点 | 参数 | 值 | 影响 |
| --- | --- | --- | --- |
| `UNETLoader` | weight_dtype | `fp8_e4m3fn` | 显存占用大幅降低，质量损失可接受 |
| `DualCLIPLoader` | type | `flux` | 必须指定，否则双编码器拼接方式错误 |
| `FluxGuidance` | guidance | `3.5` | 提示词贴合度 |
| `KSampler` | steps | `25`（应用层接口设置） | 步数 |
| `KSampler` | denoise | `1`（应用层接口设置） | 接口侧为 1，完整重绘 |
| 分辨率 | — | 512×512 | 与训练一致 |

> **参数一致性的重要性**：训练分辨率（512×512）、数据集预处理分辨率（BIRME 512×512）、推理分辨率三者必须统一，否则会出现"训练时学的尺寸和推理时用的尺寸不一致"的隐性劣化。

---

## 三、工作流与应用的对接

应用层 `/generate` 接口并非直接提交整份 JSON，而是**通过节点 ID 覆盖参数**：

```python
request_body = {
    "templateUuid": "4df2efa0f18d46dc9758803e478eb51c",
    "generateParams": {
        "3":  {"class_type": "KSampler", "inputs": {"denoise": 1, "steps": 25}},
        "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": "<正向提示词>"}},
        "7":  {"class_type": "CLIPTextEncode", "inputs": {"text": "<负向提示词>"}},
        "11": {"class_type": "LoadImage", "inputs": {"image": "<用户图公网URL>"}},
        "workflowUuid": "a80c31be2aba4901b0073cbc33be4741"
    }
}
```

**机制说明**：

| 字段 | 含义 |
| --- | --- |
| `templateUuid` | 平台上保存的**工作流模板** ID |
| `workflowUuid` | 工作流实例 ID |
| `generateParams["3"\|"6"\|"7"\|"11"]` | **按节点 ID 覆盖**：3=KSampler、6=正向 CLIP、7=负向 CLIP、11=LoadImage |

> 这意味着**同一份工作流可以被不同参数复用**——应用只需改 4 个节点的输入，无需重建整图。这是"工作流即服务"的具体形态。

完整的接口文档见 [`05-application.md`](./05-application.md)。

---

## 四、如何导入与修改

### 4.1 导入

**ComfyUI 本地**：把 JSON 拖入浏览器界面即可（ComfyUI 支持拖放 workflow json）。

**Liblib 平台**：工作流管理 → 导入 → 选择 JSON。注意平台可能要求节点类型在白名单内。

### 4.2 必须替换的内容

导入后**不会开箱即用**，需替换：

| 项 | 原因 | 处理 |
| --- | --- | --- |
| 模型名 | `星芒Anything_万物皆可FLUX_V1`、`AnythingV5V3_v5v3` 是平台内模型标识 | 换成你环境里已下载的 Flux / SD 模型 |
| `templateUuid` / `workflowUuid` | 是你 Liblib 账号下的资产 ID | 换成你自己创建的工作流 ID |
| LoRA 名 | `陆李测试的烂模型。。。_v114514` 是实验命名 | 换成你自己训练的 `Tastick.safetensors` |

### 4.3 想改风格强度时调什么

| 目标 | 调整项 | 方向 |
| --- | --- | --- |
| 更像壮锦 | `FluxGuidance` ↑ | 3.5 → 4.5，但过高会僵硬 |
| 保留更多原图结构 | `denoise` ↓ | 1.0 → 0.6~0.8 |
| 细节更丰富 | `steps` ↑ | 25 → 35（收益递减） |
| 风格更浓 | LoRA 权重 ↑ | 1.0 → 1.2（过高会崩） |

---

## 五、设计取舍记录

| 决策 | 选择 | 放弃的方案 | 理由 |
| --- | --- | --- | --- |
| 生成范式 | **图生图为主** | 纯文生图 | 壮锦有强文化语义，从零生成易偏离；给参考图作文化锚点 |
| 底模演进 | SD1.5 → **Flux** | 停在 AnythingV5 | 几何规律性是架构能力，提示词补不回来 |
| 加载方式 | **三段式** | 一体化 ckpt | Flux 权重本就是分开发布的，三段式更灵活 |
| 引导控制 | **FluxGuidance 独立节点** | KSampler cfg | Flux 是 distilled guidance，机制不同 |
| 工作流保留 | **三代全留** | 只留最终版 | 演进过程本身是技术记录 |
| 应用对接 | **按节点 ID 覆盖参数** | 每次提交整份 JSON | 同一工作流可被不同参数复用 |

---

## 相关文档

- 训练出的 LoRA 如何产生 → [`03-training.md`](./03-training.md)
- 工作流如何被应用调用 → [`05-application.md`](./05-application.md)
- 数据集准备 → [`02-dataset.md`](./02-dataset.md)
