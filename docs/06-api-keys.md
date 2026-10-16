# API 密钥配置指南

> 本项目需要 **3 个密钥**，分别来自两个平台。**都是你自己注册申请的**，仓库里不含任何可用凭证。
>
> 配置耗时约 10 分钟。密钥只存在你本机的 `.env` 文件里（已被 `.gitignore` 排除，不会上传）。

---

## 总览

| 密钥 | 来源平台 | 用途 | 费用 |
| --- | --- | --- | --- |
| `FREEIMGHOST_API_KEY` | [FreeImageHost](https://freeimghost.net/) | 把用户上传的图片转成公网 URL | 免费 |
| `LIBLIB_ACCESS_KEY` | [LiblibAI](https://www.liblib.art/) | 调用 ComfyUI 工作流生成纹样 | 按量计费 |
| `LIBLIB_SECRET_KEY` | 同上 | 生成请求签名（鉴权） | 同上 |

**为什么需要图床**：Liblib 的 API 只接受**公网可访问的图片 URL**，而用户上传的图在你本机。所以要先传到图床拿到 URL，再提交生成任务。

---

## 一、获取 FreeImageHost API Key

1. 打开 https://freeimghost.net/
2. 注册账号（邮箱注册，免费）
3. 登录后进入 **API** 页面（通常在用户菜单或设置里）
4. 复制你的 **API Key**

**格式特征**：以 `chv_` 开头的一长串字符。

```bash
FREEIMGHOST_API_KEY=chv_你的密钥
```

> 这个 key 通过请求头 `X-API-Key` 传递，用于 `/api/1/upload` 接口。

---

## 二、获取 LiblibAI AccessKey 与 SecretKey

LiblibAI 是国内主流的 AI 绘画模型与工作流平台，其**开放平台**允许通过 API 调用 ComfyUI 工作流。

### 步骤

1. 打开 https://www.liblib.art/ 并登录
2. 进入 **个人中心** → 找到 **开放平台**（或"API 开放平台"、"开发者中心"）
3. **创建应用**，填写应用名称与用途说明
4. 审核通过后（通常即时），你会得到：
   - **AccessKey** — 公开标识，用于标识调用者身份
   - **SecretKey** — 私密密钥，用于生成签名，**绝不能泄露**

```bash
LIBLIB_ACCESS_KEY=你的AccessKey
LIBLIB_SECRET_KEY=你的SecretKey
```

### 关键限制：免费额度

LiblibAI 的 API **通常需要账户余额或付费套餐**才能调用。请先在平台上确认：

- 是否有免费试用额度
- 单次生成（ComfyUI 工作流）的计费方式
- 你账户的余额是否足够

> **没有额度会怎样**：图片能上传成功（图床免费），但 `/generate` 提交后会返回平台侧的错误码，提示余额不足。

---

## 三、签名机制说明（为什么需要 SecretKey）

LiblibAI 用 **HMAC-SHA1** 做请求鉴权，这是它跟你账号之间的"暗号"。代码实现在 `app/server.py`：

```python
def generate_signature(uri, timestamp, nonce, secret_key):
    content = "&".join((uri, timestamp, nonce))
    digest = hmac.new(secret_key.encode(), content.encode(), sha1).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
```

**三个输入**：

| 参数 | 来源 | 作用 |
| --- | --- | --- |
| `uri` | 固定为 API 路径，如 `/api/generate/comfyui/app` | 区分不同接口的签名 |
| `timestamp` | 当前**毫秒**时间戳 | 防止旧请求被重放 |
| `nonce` | 随机字符串（代码用 `uuid4()`） | 保证每次签名唯一 |

**输出**：`base64(urlsafe(HMAC-SHA1(secret_key, uri&timestamp&nonce)))`，去掉尾部 `=`。

每次请求都要**重新生成**一套 `timestamp` + `nonce` + `signature`，不能复用。

> 这也是为什么 SecretKey 必须保密——泄露它等于别人可以伪造你的身份调用 API、消耗你的额度。

---

## 四、填写与验证

### ① 创建 `.env`

```bash
cd zhuangjin-pattern-ai
cp .env.example .env      # Windows: copy .env.example .env
```

编辑 `.env`，填入三个密钥：

```bash
FREEIMGHOST_API_KEY=chv_xxxxxxxx
LIBLIB_ACCESS_KEY=xxxxxxxx
LIBLIB_SECRET_KEY=xxxxxxxx
```

### ② 启动服务并看自检输出

```bash
python app/server.py
```

**配置完整时**会看到：

```
[OK] API 密钥已配置，功能可用。
壮锦纹样生成服务启动: http://127.0.0.1:5000
```

**缺失密钥时**会看到提示，但服务仍会启动（方便你先看界面）：

```
==================================================================
[提示] 以下 API 密钥尚未配置: LIBLIB_ACCESS_KEY, LIBLIB_SECRET_KEY
       服务仍可启动，但「上传图片」与「创意生成」会返回 503 并给出指引。
       配置文档: docs/06-api-keys.md
==================================================================
```

### ③ 验证是否真的通了

打开 http://127.0.0.1:5000 ，上传一张图片并点「创意生成」。

| 现象 | 含义 | 排查 |
| --- | --- | --- |
| 正常出图 | 全部配置正确 | — |
| 弹窗提示"密钥未配置" | `.env` 没生效 | 确认文件名为 `.env`（不是 `.env.txt`），且在项目根目录 |
| 提示"图片上传失败" | FreeImageHost key 有问题 | 检查 key 是否完整、账号是否可用 |
| 提示"生成失败"/余额不足 | Liblib 无额度或 key 错误 | 去 Liblib 平台确认余额与 key |
| 提示"生成请求失败" | 平台返回非 200 | 看返回的 `details` 字段中的具体错误 |

**接口级验证**（可选，更直接）：

```bash
# 密钥缺失时应返回 503 + 指引
curl -X POST -H "Content-Type: application/json" \
     -d '{"image_url":"https://example.com/a.png"}' \
     http://127.0.0.1:5000/generate
```

---

## 五、安全须知

### 绝对不要做的事

| 禁止 | 原因 |
| --- | --- |
| 把密钥写进 `.py` / `.js` 源码 | 会被 Git 记录，一旦公开就是永久泄露 |
| 把 `.env` 提交到仓库 | 已加 `.gitignore`，仍需你自己确认 |
| 把密钥贴到聊天/截图/论坛 | SecretKey 泄露 = 别人能刷你的额度 |
| 在公开仓库里用 `print(os.environ)` 调试 | 日志会泄露密钥 |

### 如果不小心泄露了

**立刻去平台重置密钥**，不要只删代码——Git 历史、fork、缓存都可能有留存。

```bash
# 快速自检：确认仓库里没有硬编码密钥
grep -rnE "chv_|ACCESS_KEY\s*=\s*['\"][A-Za-z0-9]|SECRET_KEY\s*=\s*['\"][A-Za-z0-9]" app/ .env.example
```

正常结果：`app/server.py` 只在 `os.environ.get(...)` 的行上匹配到变量名，**不应出现真实值**。

---

## 六、常见问题

<details>
<summary><b>Q1. 只想看界面，不想申请密钥行不行？</b></summary>

可以。服务能正常启动并打开首页，只是「上传」和「创意生成」会返回 503 提示。界面浏览、代码学习不受影响。
</details>

<details>
<summary><b>Q2. 能不能用别的图床替代 FreeImageHost？</b></summary>

可以。只要满足两个条件：① 支持 API 上传并返回公网 URL；② 该 URL 能被 Liblib 的服务器访问到。

替换位置在 `app/server.py` 的 `FREEIMGHOST_API_URL` 与 `upload_file()` 里的调用逻辑。国内可考虑七牛云、阿里云 OSS 等。
</details>

<details>
<summary><b>Q3. 能不能不用 Liblib，自建 ComfyUI？</b></summary>

可以，而且**更可控**（不依赖第三方额度与政策）：

1. 本地或云服务器部署 ComfyUI
2. 导入 `workflow/comfyui/*.json`，加载 Flux 模型 + 你训练的 LoRA
3. 用 ComfyUI 的 API 模式替代 Liblib 的接口

代价是需要自己解决 GPU 资源。详见 [`04-workflow.md`](./04-workflow.md)。
</details>

<details>
<summary><b>Q4. `.env` 放在哪？</b></summary>

项目根目录（与 `app/`、`docs/` 同级）。代码用 `python-dotenv` 的 `load_dotenv()` 自动从当前工作目录向上查找。

若 `python-dotenv` 未安装会自动跳过（不报错），但那样就必须用系统环境变量传入：

```bash
# Windows PowerShell
$env:FREEIMGHOST_API_KEY="chv_xxx"
$env:LIBLIB_ACCESS_KEY="xxx"
$env:LIBLIB_SECRET_KEY="xxx"
python app/server.py
```
</details>

<details>
<summary><b>Q5. 为什么我的密钥看起来和别人不一样？</b></summary>

密钥是**每个账号独立生成**的，格式一致但值不同。文档里从不出现真实密钥——如果你在别处看到"示例 key"，那是占位符。

本项目历史版本曾误将真实密钥硬编码在源码中，**公开版已全部改为环境变量**。若你从其他渠道拿到过旧版 `server.py`，请勿使用其中的密钥，并建议通知原持有者重置。
</details>

---

## 相关文档

- 应用接口与安全 → [`05-application.md`](./05-application.md)
- 环境变量模板 → [`../.env.example`](../.env.example)
- 工作流与模型配置 → [`04-workflow.md`](./04-workflow.md)
