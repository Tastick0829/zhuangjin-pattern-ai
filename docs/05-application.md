# 应用层：Flask 后端与前端交互

> 代码位置：[`../app/`](../app/)　｜　入口：[`../app/server.py`](../app/server.py)

---

## 一、应用在系统中的位置

应用层是整条链路的**出口**——把"模型能力"包装成"用户能用的东西"：

```text
用户上传纹样图
      ↓
┌─────────────────────────────────────┐
│ /upload     本地入库 + 转图床拿公网URL │
│      ↓                              │
│ /generate   HMAC-SHA1 签名 → 提交任务 │
│      ↓                              │
│ /check_status  轮询 → 返回生成图      │
└─────────────────────────────────────┘
      ↓
前端 Canvas 合成文创产品预览 → 下载
```

**为什么需要图床中转**：Liblib 的 API 只接受**公网可访问的图片 URL**，而用户上传的图在本地。所以必须先传图床拿到 URL 再提交任务。

---

## 二、后端接口

基址 `http://127.0.0.1:5000`（端口可用 `PORT` 环境变量覆盖）。

### 2.1 `GET /` — 页面

返回 `app/templates/index.html`（纹样上传与生成界面）。

---

### 2.2 `POST /upload` — 上传并公网化

**请求**：`multipart/form-data`，字段名 `file`

**处理流程**：

```text
接收文件
  ↓
PIL 打开验证是否为合法图片
  ↓
生成唯一文件名：{时间戳}_{16位随机hex}_{内容md5}_converted.png
  ↓
保存到 uploads/（基于 BASE_DIR 的绝对路径）
  ↓
转发到 FreeImageHost
  ↓
返回公网 URL
```

**响应**：

```json
{ "message": "文件上传成功", "original_url": "https://...", "filename": "..." }
```

**唯一文件名为什么这么复杂**：`时间戳 + urandom(8).hex() + md5` 三重组合，避免并发上传时重名覆盖。

**限制**：`MAX_CONTENT_LENGTH = 16MB`（Flask 配置）

---

### 2.3 `POST /generate` — 提交生成任务

**请求**：

```json
{ "image_url": "https://图床地址/xxx.png" }
```

**处理流程**：

```text
1. 生成签名三元组
   timestamp = 毫秒时间戳
   nonce     = uuid4()
   signature = HMAC-SHA1(secret_key, "uri&timestamp&nonce") → urlsafe_base64 去尾=

2. 构造请求体（按节点 ID 覆盖工作流参数）
   templateUuid: 4df2efa0f18d46dc9758803e478eb51c
   generateParams:
     "3"  : KSampler      { denoise: 1, steps: 25 }
     "6"  : CLIPTextEncode{ text: <正向> }
     "7"  : CLIPTextEncode{ text: <负向> }
     "11" : LoadImage     { image: <用户图URL> }
     workflowUuid: a80c31be2aba4901b0073cbc33be4741

3. POST https://openapi.liblibai.cloud/api/generate/comfyui/app
   Header: Content-Type: application/json
   Params: AccessKey / Signature / Timestamp / SignatureNonce

4. 返回 platform 的 generateUuid
```

**响应**：

```json
{ "status": "生成任务已提交", "task_id": "..." }
```

**签名机制**（Liblib 的鉴权方式）：

```python
def generate_signature(uri, timestamp, nonce, secret_key):
    content = "&".join((uri, timestamp, nonce))
    digest = hmac.new(secret_key.encode(), content.encode(), sha1).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
```

签名的三个要素 `uri`（API 路径）、`timestamp`、`nonce` 用 `&` 连接后做 HMAC-SHA1，再 url-safe base64 编码并去掉尾部 `=`。**同一组参数只能有效一次**（nonce 随机 + 时间戳），这是防重放设计。

---

### 2.4 `GET /check_status?task_id=xxx` — 轮询结果

**处理流程**：

```text
生成签名（uri 用 /api/generate/comfy/status）
  ↓
POST 到 status 接口，body 为 { generateUuid: task_id }
  ↓
解析 generateStatus：
   5 → 完成，筛选 auditStatus == 3 的图片（平台审核通过）
   6 → 失败，返回 generateMsg
   其他 → 处理中
  ↓
完成时返回最后一张审核通过的图
```

**响应**：

```json
{ "status": "completed", "image_url": "https://..." }
{ "status": "processing" }
{ "status": "failed", "error": "..." }
```

> **`auditStatus == 3`** 表示平台的**内容合规审核已通过**。生产环境必须只使用通过审核的图，不能绕过。

---

## 三、前端交互

页面：`app/templates/index.html`（`壮锦新生-非遗纹样创意生成`）

### 3.1 界面结构

```text
┌──────────────────────────────────────────┐
│  壮锦新生-非遗纹样创意生成                  │
├──────────────────────────────────────────┤
│  [📤 上传纹样图片]  [✨ 创意生成]            │
├───────────────────┬──────────────────────┤
│   原始纹样         │     生成纹样          │
│   (canvas)        │     (canvas)          │
├───────────────────┴──────────────────────┤
│  [选择文创产品 ▼]  [生成文创产品]           │
│      马克杯 / 帆布包 / 笔                  │
├──────────────────────────────────────────┤
│            文创产品预览 (canvas)           │
│              [下载产品图]                  │
└──────────────────────────────────────────┘
```

### 3.2 交互链路

```text
① 选图 → FileReader 读为 DataURL → 绘制到 originalCanvas
② 点「创意生成」
     → POST /upload（FormData）
     → 拿 original_url
     → POST /generate
     → 轮询 GET /check_status?task_id=
     → 拿到 image_url → 绘制到 resultCanvas
③ 选文创载体 → 点「生成文创产品」
     → Canvas 模板合成（本地绘制）
④ 点「下载产品图」→ toDataURL('image/png') → 触发下载
```

### 3.3 产品合成逻辑（Canvas 实现）

产品合成是**纯前端 Canvas 绘制**，不调后端：

| 产品 | 模板处理 |
| --- | --- |
| `mug` 马克杯 | 白底 400×400，纹样绘制在 `(50,100,300,200)` 区域 |
| `bag` 帆布包 | 灰白底 `#F5F5F5`，纹样绘制在 `(50,80,300,240)` |
| `pen` 笔 | 金色底 `#D4AF37`，纹样绘制在 `(180,150,80,200)` 的细长区域 |

合成后加阴影（`shadowBlur=10`, `shadowOffsetY=5`）模拟产品立体感。

> **这是原型级实现**：用矩形区域模拟载体表面，没有做透视变形或材质融合。真正的产品效果图需要 3D 渲染或专门的合成模型（如 SD 的 inpainting/ControlNet）。保留此实现是为了说明**"纹样→产品预览"这个环节被跑通了**，而非宣称产出可印刷的成品图。

---

## 四、配置与安全

### 4.1 环境变量（必填）

```bash
FREEIMGHOST_API_KEY=   # 图床
LIBLIB_ACCESS_KEY=     # Liblib
LIBLIB_SECRET_KEY=     # Liblib
```

复制 `.env.example` 为 `.env` 填写。**服务启动时会自检，缺失即报错停止**——避免带着空密钥运行到调用时才失败。

> **历史提醒**：本仓库早期版本曾把这三组密钥**硬编码在源码里**。那份代码从未发布，公开版本已改为全部走环境变量。**若你曾经在别处复制过旧版 `server.py`，请立即去对应平台吊销密钥。**
>
> 判断代码里是否残留密钥：
> ```bash
> grep -rnE "chv_|ACCESS_KEY\s*=\s*['\"]|SECRET_KEY\s*=\s*['\"]" app/
> ```
> 正常结果应只在 `os.environ.get(...)` 的行上匹配到变量名，不应出现真实值。

### 4.2 可选运行参数

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `PORT` | `5000` | 监听端口 |
| `FLASK_DEBUG` | `0` | **生产务必保持 0**。Flask debug 模式会暴露交互式调试器（可执行任意代码） |

### 4.3 已知安全问题与改进方向

| 问题 | 风险 | 建议 |
| --- | --- | --- |
| 无鉴权 | 任何人可调用 `/generate` 消耗你的 API 额度 | 加 API Key 或登录态校验 |
| 无频率限制 | 可被刷接口 | 加 rate limit（如 Flask-Limiter） |
| `uploads/` 无限增长 | 磁盘占满 | 定时清理 + 上传失败即删 |
| 依赖第三方图床 | 服务不可用则上传失败 | 自建图床或本地暴露（内网穿透） |
| 端口默认 5000 + debug 曾为 True | 若误暴露公网有 RCE 风险 | 已改为默认 `debug=0`，仍需避免直接公网暴露 |
| 无内容审核前置 | 违规图可能被提交 | 上传前做基础校验 |

> 这套应用是**竞赛原型**定位，不是生产系统。若要对外服务，上述几项必须先补齐。

---

## 五、接口速查

| 方法 | 路径 | 入参 | 出参 |
| --- | --- | --- | --- |
| GET | `/` | — | HTML 页面 |
| POST | `/upload` | form-data `file` | `original_url` |
| POST | `/generate` | JSON `image_url` | `task_id` |
| GET | `/check_status` | query `task_id` | `status` + `image_url` |

**典型调用顺序**：

```bash
# 1. 上传
curl -X POST -F "file=@pattern.png" http://127.0.0.1:5000/upload
# → {"original_url":"https://...","filename":"..."}

# 2. 提交生成
curl -X POST -H "Content-Type: application/json" \
     -d '{"image_url":"https://..."}' http://127.0.0.1:5000/generate
# → {"status":"生成任务已提交","task_id":"..."}

# 3. 轮询（重复调用直到 status != processing）
curl "http://127.0.0.1:5000/check_status?task_id=..."
# → {"status":"completed","image_url":"https://..."}
```

---

## 六、代码演进痕迹

`app/` 与 `source-html/` 同时保留了多个版本，这是有意的：

| 文件 | 说明 |
| --- | --- |
| `app/server.py` | **权威版本**（257 行），已脱敏 |
| `app/app_minimal.py` | 最简版（57 行），早期原型 |
| `app/templates/index.html` | 接入后端的完整前端（16.27 KB） |
| `app/templates/index_minimal.html` | 早期简单模板 |
| `source-html/prototype-full.html` | 纯前端原型（65 KB），无 API 调用 |
| `source-html/prototype-canvas.html` | Canvas 特效原型（11 KB），用描边模拟"纹样生成" |

> 保留演进痕迹的价值：能看出**从"假生成"（Canvas 加个边框）到"真生成"（调 AI API）**的路径转换。这条路径本身就是技术方案选型的一部分。

---

## 相关文档

- 工作流如何被调用 → [`04-workflow.md`](./04-workflow.md)
- 系统整体设计 → [`01-design.md`](./01-design.md)
- 环境变量模板 → [`../.env.example`](../.env.example)
