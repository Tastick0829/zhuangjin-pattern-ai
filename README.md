<div align="center">

# 🧵 壮锦新生 · AI 纹样创意生成系统

**一个把非遗壮锦纹样「风格化再造 + 文创落地」串成完整链路的 AI 应用**

从数据集构建 → LoRA 风格微调 → 工作流编排 → Web 应用封装的端到端实践

![Model](https://img.shields.io/badge/base%20model-Flux.1--dev-8b4513)
![Method](https://img.shields.io/badge/method-LoRA-6a5acd)
![Workflow](https://img.shields.io/badge/orchestration-ComfyUI%20%2F%20Liblib-1a73e8)
![App](https://img.shields.io/badge/app-Flask%20%2B%20Canvas-2e8b57)
![License](https://img.shields.io/badge/License-AGPL--3.0-blue)

</div>

---

## 目录

| 章节 | 说明 |
| --- | --- |
| [这是什么](#这是什么) | 项目定位与解决的真实问题 |
| [我做了什么](#我做了什么) | 四层技术链路与独立贡献边界 |
| [系统架构](#系统架构) | 数据 → 训练 → 推理 → 应用 |
| [技术选型与理由](#技术选型与理由) | 为什么是 Flux、为什么是 LoRA、为什么是工作流 |
| [仓库结构](#仓库结构) | 每个目录放什么 |
| [快速开始](#快速开始) | 复现这条链路的步骤 |
| [已知局限](#已知局限) | 这个方案的真实边界（必读） |
| [AI 辅助声明](#ai-辅助声明) | 生成内容的标注义务 |
| [许可与声明](#许可与声明) | 文化素材与法律边界 |

---

## 这是什么

**壮锦新生**是一套**面向非遗纹样数字化再生的 AI 创意生成系统**。用户上传一张壮锦纹样图，系统输出：

1. **风格化创意纹样** —— 保留壮锦的几何骨架与民族配色，做新构图
2. **文创产品合成图** —— 把纹样落到马克杯 / 帆布包 / 笔等载体上

项目的完整链路：

```
纹样数据集构建  →  数据清洗与打标  →  Flux LoRA 微调  →  ComfyUI 工作流编排  →  Flask Web 应用
 (172 files)      (BIRME 512×512)    (20 epochs)        (5 套工作流)          (上传→生成→合成)
```

### 它解决的真实问题

非遗纹样的当代应用有两个现实卡点：

| 卡点 | 传统做法 | 本方案 |
| --- | --- | --- |
| **设计门槛高** | 纹样再造需要懂壮锦工艺与构成规则的设计师 | 上传参考图即可生成同风格新构图 |
| **产出慢** | 手工绘制一张纹样稿以天计 | 单次生成秒级，批量出方案 |
| **落地断层** | 纹样图与产品效果图是两件事 | 生成后直接合成文创载体预览图 |

> **定位澄清**：这不是"用 AI 替代设计师"，而是把**纹样→草图→产品预览**的探索环节压缩到几分钟，让设计师把时间花在筛选与深化上。AI 出的是**候选方案**，不是终稿。

---

## 我做了什么

按技术层次说明**独立完成的部分**与**使用他人成果的部分**：

| 层次 | 内容 | 贡献 |
| --- | --- | --- |
| **① 数据层** | 约 150 张壮锦纹样（几何纹 62% / 动物纹 23% / 植物纹 15%）收集与整理、BIRME 统一为 512×512、撰写英文 caption 打标规范 | 独立完成 |
| **② 训练层** | LoRA 训练参数设计与调优（Flux.1-dev，6 组参数迭代）、AutoDL 云端训练执行 | 独立完成 |
| **③ 编排层** | ComfyUI 工作流搭建（5 套：图生图 / 文生图 / 产品合成）、提示词工程、Liblib 平台配置 | 独立完成 |
| **④ 应用层** | Flask 后端（上传 / 生成 / 轮询三个接口 + HMAC-SHA1 签名）、前端 Canvas 交互与产品合成 | 独立完成 |
| **⑤ 论文撰写** | 研究框架、技术路线、实验与结论 | 独立完成（部分文字表述有他人参与） |

**使用但不属于自研的部分**：

- 底模 **Flux.1-dev**（Black Forest Labs，开源权重）
- 社区模型 **星芒 Anything_万物皆可FLUX_V1**（Liblib 平台，用于提升生成风格稳定性）
- 训练框架 **kohya-ss/sd-scripts**（LoRA 训练实现）
- 数据集预处理工具 **BIRME**（批量缩放）
- 推理平台 **LiblibAI**（ComfyUI 在线运行 + API）
- 图床 **FreeImageHost**（图片公网化中转）

---

## 系统架构

<div align="center">

```text
┌──────────────────────────────────────────────────────────────────────┐
│ ① 数据层                                                             │
│   壮锦纹样采集 ──> BIRME 批量缩放(512×512) ──> 英文 caption 打标     │
│   产出: dataset/ 图片 + prompts/captions/*.txt                       │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│ ② 训练层（AutoDL GPU 云）                                            │
│   kohya-ss/sd-scripts ──> flux-lora 训练                             │
│   底模: flux1-dev_unet.safetensors + ae + clip_l + t5xxl             │
│   产出: Tastick.safetensors（LoRA 权重）                             │
│   参数: r=2 / alpha=16 / lr=1e-4 / 20 epochs / 512×512               │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│ ③ 编排层（Liblib 平台 · ComfyUI）                                    │
│   ┌ 文生图：CLIPTextEncode(壮锦提示词) → KSampler → VAEDecode        │
│   ├ 图生图：LoadImage → ImageScaleBy → VAEEncode → KSampler(denoise) │
│   ├ LoRA：LoraLoader 注入风格权重                                    │
│   ├ 底模：UNETLoader(星芒Anything) + DualCLIPLoader + VAELoader      │
│   └ 参数：FluxGuidance 3.5 / steps 25 / 512×512                      │
│   产出: workflow/comfyui/*.json（可导入 ComfyUI 的节点图）           │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│ ④ 应用层（Flask + Canvas）                                           │
│   /upload      图片入库 + 转图床拿公网 URL                            │
│   /generate    HMAC-SHA1 签名 → 提交 Liblib ComfyUI 任务              │
│   /check_status 轮询任务状态 → 返回审核通过的生成图                    │
│   前端         纹样上传 → 创意生成 → 选文创载体(mug/bag/pen) → 合成   │
└──────────────────────────────────────────────────────────────────────┘
```

</div>

---

## 技术选型与理由

选型不是随手挑的，每一项都有明确取舍：

### 为什么是 Flux.1-dev 而不是 SD1.5 / SDXL

| 维度 | SD1.5 / SDXL | Flux.1-dev（本方案） |
| --- | --- | --- |
| 文本理解 | 弱，复杂提示词容易丢要素 | 强，能理解"菱形嵌套 + 云雷纹 + 蝶花点缀"这类结构化描述 |
| 几何规律性 | 图案易崩、对称难保持 | 对几何对称与重复纹样更稳 |
| 显存需求 | 低 | 高（fp8 量化后仍需较大显存） |

**取舍结论**：壮锦纹样高度依赖**几何规律性**（菱形嵌套、四方连续、对称构图），这是 SD 系列的弱项。宁可付出算力成本上 Flux。

### 为什么是 LoRA 而不是全量微调

| 维度 | 全量微调 | LoRA（本方案） |
| --- | --- | --- |
| 训练成本 | 需要大量显存与时间 | 单卡可跑，20 epoch 即可 |
| 产出体积 | 数十 GB | 数十 MB（本次 `network_dim=2` 极小） |
| 复用性 | 绑定单一底模 | 可插拔，可叠加其他 LoRA |

`network_dim = 2` / `network_alpha = 16` 是**刻意压到极小的配置**——目标不是让模型"背下"纹样，而是**注入轻量的风格倾向**，避免过拟合到训练集的某几张图上。

### 为什么用工作流（ComfyUI）而不是手写推理脚本

| 维度 | 手写脚本 | 工作流（本方案） |
| --- | --- | --- |
| 调参 | 改代码 → 重启 | 拖节点 → 即时出图 |
| 复用 | 每换一个流程重写 | 换节点图即可 |
| 协作 | 代码+环境依赖 | 导出一个 JSON 就能给别人 |
| API 化 | 需要自己封装 | 平台直接暴露 API |

**这也是本项目的核心技术架构所在**——把"纹样生成"从一次性的推理调用，变成**可视化、可复用、可 API 化的编排资产**。

### 提示词工程要点

训练与推理用的是两套不同的提示词，这个区分很关键：

| 场景 | 提示词 | 位置 |
| --- | --- | --- |
| **训练打标** | `no humans, intangible cultural heritage, Zhuang brocade, geometric patterns, traditional patterns, ethnic style, colorful decoration, fabric patterns, Pattern, Colorful, Zhuang ethnic traditional pattern style` | `prompts/captions/*.txt` |
| **推理正向** | `Traditional Zhuang brocade, 512x512, symmetrical geometric patterns, dark blue background, vibrant red yellow pink colors, diamond/square/triangle nesting, cloud fret patterns, central geometric motif with butterfly flower accents, layered composition, ethnic decorative art style, high contrast, bold colors` | `workflow/comfyui/*.json` |
| **推理负向** | `text, watermark, embedding:bad-picture-chill-75v` | 同上 |

**差异逻辑**：训练打标追求**覆盖共性**（让模型学会"什么算壮锦"）；推理提示词追求**约束个性**（指定构图、配色、母题）。打标过细会导致模型只会复现训练图，所以训练用泛化标签、推理用具体描述。

---

## 仓库结构

```text
zhuangjin-pattern-ai/
├── README.md                    # 本文件
├── LICENSE                      # AGPL-3.0
├── .env.example                 # 环境变量模板（复制为 .env 使用）
├── .gitignore                   # 已排除密钥、数据集、模型权重
├── requirements.txt
├── docs/
│   ├── 01-design.md             # 系统设计方案（技术路线与决策）
│   ├── 02-dataset.md            # 数据集说明与获取方式
│   ├── 03-training.md           # LoRA 训练参数详解
│   ├── 04-workflow.md           # ComfyUI 工作流拆解
│   ├── 05-application.md        # Flask 应用与接口文档
│   └── literature-notes.txt     # 壮锦纹样特征与文献梳理
├── training/
│   ├── README.md                # 参数对照表
│   └── *.toml                   # 6 组训练参数（迭代记录）
├── prompts/
│   └── captions/                # 12 份训练打标文件
├── workflow/
│   └── comfyui/                 # 5 套 ComfyUI 工作流 JSON
├── app/
│   ├── server.py                # Flask 后端（已脱敏，密钥走环境变量）
│   ├── app_minimal.py           # 最简版后端（早期原型）
│   ├── templates/               # 前端页面
│   └── static/css/
├── source-html/                 # 早期纯前端原型（保留演进痕迹）
└── dataset/                     # 数据集占位目录（数据不入库，见 docs/02-dataset.md）
```

---

## 快速开始

### 前置条件

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| Python | 3.10+ | 运行 Web 应用 |
| Flux.1-dev 权重 | — | 训练底模（自行下载） |
| LiblibAI 账号 | — | 推理平台（工作流运行环境） |
| FreeImageHost 账号 | — | 图床（图片公网化中转） |

### ① 启动 Web 应用

```bash
git clone https://github.com/Tastick0829/zhuangjin-pattern-ai.git
cd zhuangjin-pattern-ai

pip install -r requirements.txt

# 配置密钥（必须）
cp .env.example .env
# 编辑 .env，填入你自己的 FREEIMGHOST_API_KEY / LIBLIB_ACCESS_KEY / LIBLIB_SECRET_KEY

python app/server.py
# 打开 http://127.0.0.1:5000
```

> 应用启动时会**自检环境变量**，缺失会直接报错停止，不会带着空密钥继续跑。

### ② 复现训练（可选，需要 GPU）

```bash
# 1. 准备数据集：把纹样图放入 train/aki/，同名的 .txt 放 caption
#    （缩放建议 512×512，可用 BIRME 批量处理）
# 2. 获取训练脚本
git clone https://github.com/kohya-ss/sd-scripts
# 3. 使用 training/1747465671967.toml（参数最完整的一组），按需修改路径与 train_data_dir
# 4. 启动训练后产出 Tastick.safetensors
```

### ③ 导入工作流（可选）

在 ComfyUI 或 Liblib 的「工作流」界面导入 `workflow/comfyui/*.json`。

> 工作流中的模型名（如 `星芒Anything_万物皆可FLUX_V1`、`AnythingV5V3_v5v3`）是**平台内的模型标识**，你的环境里需要替换成已下载的同名或同类模型。

---

## 已知局限

**这一节必须读。** 诚实标注方案的边界，比夸大效果更有价值。

### 1. 数据集本身是壮锦纹样 → 风格"来源"存在混杂

训练集与测试集**高度同源**：用户上传的参考图本身就是壮锦纹样，工作流又以图生图（`VAEEncode` + `KSampler denoise<1`）为主。这意味着生成图在相当程度上**保留了输入图的结构**，模型学到的是"壮锦→壮锦的映射"。

**影响**：生成结果**更接近"风格化再造"而非"从零创造新纹样"**。

**改进方向**：
- 若目标是**创新生成**，应补充"非壮锦"的对照集，做真正的风格迁移评估
- 或引入结构化条件（线稿 / 分割图 ControlNet）以解耦结构与风格
- 需要构建**独立测试集**（训练时未见过的纹样）才能给出可信的评估结论

### 2. `network_dim = 2` 容量极小

好处是过拟合风险低、权重体积小；代价是**风格注入能力有限**。若发现生成结果风格特征不够强，可尝试提升到 8 / 16 并重新评估。

### 3. 评估仍以主观量表为主

论文中做了**控制变量实验**（以训练步数为变量）并设计了**人工评分量表**：

| 指标 | 方式 |
| --- | --- |
| 文化保留度 | 美术专业教师评分（1–5 分） |
| 现代审美契合度 | 不同年龄段用户评分（1–5 分） |
| 综合满意度 | 两者加权平均 |

这构成了初步的量化框架，但仍有明显缺口：**样本量与评分者来源有限**，且缺少 FID、CLIP Score 等可复现的客观指标。**要让结论更稳固，需要构建独立测试集并补充自动化评估。**

### 4. 依赖第三方平台

推理链路绑定 LiblibAI（模型与 API）、FreeImageHost（图床）。任一服务变更都会影响可用性。**自建 ComfyUI + 本地图床**是更可控的方案。

### 5. 训练步数偏少

`20 epochs × (约 150 张 / batch_size=15)` 的实际步数较少，属于**验证可行性**的量级，不足以逼近该风格的上限。

---

## AI 辅助声明

本项目生成的图像为 **AI 生成内容**（AI-Generated Content）：

- 所有由本系统输出的纹样与产品预览图**均为 AI 生成**，不是人工绘制
- 用于文创产品设计前，建议**人工复核并深化**，不应直接作为成品稿
- 公开发布生成图时，建议标注"AI 生成"，符合《生成式人工智能服务管理暂行办法》等规范精神
- AI 生成内容可能存在**对既有作品的意外相似**，商用前须做权属与相似度审查

---

## 许可与声明

本项目采用 **AGPL-3.0**（详见 [LICENSE](./LICENSE)）。

### 版权与使用边界

| 内容 | 说明 |
| --- | --- |
| 本仓库代码（`app/`） | AGPL-3.0，可自由使用、修改、分发；提供网络服务时须向用户开放源码 |
| 训练参数、提示词、工作流 | 同上 |
| **壮锦纹样图片** | **未随仓库分发**。壮锦为国家级非物质文化遗产，具体素材的著作权与使用授权需单独确认 |
| **第三方参考文献** | **未随仓库分发**。原始 PDF 为他人已发表成果，引用请遵循学术规范 |
| **论文全文** | **未随仓库分发**。论文含合作者参与的文字，权属需另行协商 |

### 使用数据集前请注意

非遗纹样的采集与商用涉及文化尊重与法律边界：

1. **来源合规**：确认每张素材的获取途径与授权状态
2. **文化尊重**：壮锦纹样承载壮族文化语义，改造与商用需尊重原文化语境
3. **商用审查**：涉及文创量产前，建议咨询知识产权与文化主管部门

### 免责声明

本项目用于**技术研究与非遗数字化探索**。使用者须自行确保所用素材与产出内容合法合规。作者不对任何侵权或不当使用承担责任。

---

<div align="center">

**壮锦新生 · 让非遗纹样在新的载体上继续生长 🌿**

</div>
