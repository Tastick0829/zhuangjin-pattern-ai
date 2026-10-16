from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image
import io
import requests  # 新增
import time  # 新增
import hmac
from hashlib import sha1
import base64
import uuid
import json
import hashlib

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ---------- 环境变量加载 ----------
# 优先从 .env 读取（python-dotenv 可选依赖，未安装时静默跳过）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------- 配置：全部通过环境变量注入，禁止硬编码密钥 ----------
# 参考 .env.example 填写
FREEIMGHOST_API_KEY = os.environ.get("FREEIMGHOST_API_KEY", "")
LIBLIB_ACCESS_KEY = os.environ.get("LIBLIB_ACCESS_KEY", "")
LIBLIB_SECRET_KEY = os.environ.get("LIBLIB_SECRET_KEY", "")

FREEIMGHOST_API_URL = "https://freeimghost.net/api/1/upload"
LIBLIB_GENERATE_API_URL = "https://openapi.liblibai.cloud/api/generate/comfyui/app"
LIBLIB_STATUS_API_URL = "https://openapi.liblibai.cloud/api/generate/comfy/status"

# 上传目录与模板路径（基于本文件位置，保证从任意工作目录启动都能找到）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
TEMPLATE_NAME = "index.html"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- 启动自检 ----------
_missing = [
    n for n, v in (
        ("FREEIMGHOST_API_KEY", FREEIMGHOST_API_KEY),
        ("LIBLIB_ACCESS_KEY", LIBLIB_ACCESS_KEY),
        ("LIBLIB_SECRET_KEY", LIBLIB_SECRET_KEY),
    ) if not v
]
if _missing:
    raise RuntimeError(
        "缺少必需的环境变量: " + ", ".join(_missing)
        + "\n请复制 .env.example 为 .env 并填入你自己的密钥。"
    )


@app.route("/")
def index():
    return send_from_directory(os.path.join(BASE_DIR, "templates"), TEMPLATE_NAME)


def generate_signature(uri, timestamp, nonce, secret_key):
    """按 LiblibAI 要求生成请求签名"""
    content = "&".join((uri, timestamp, nonce))
    digest = hmac.new(secret_key.encode(), content.encode(), sha1).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

@app.route('/generate', methods=['POST'])
def generate_creative():
    try:
        data = request.json
        if not data or 'image_url' not in data:
            return jsonify({'error': '缺少必要参数'}), 400
            
        # 生成签名参数
        timestamp = str(int(time.time() * 1000))  # 毫秒时间戳
        nonce = str(uuid.uuid4())  # 随机字符串
        signature = generate_signature(
            "/api/generate/comfyui/app",  # API URI
            timestamp,
            nonce,
            LIBLIB_SECRET_KEY
        )
        
        # 构造请求体
        request_body = {
            "templateUuid": "4df2efa0f18d46dc9758803e478eb51c",
            "generateParams": {
                "3": {"class_type": "KSampler", "inputs": {"denoise": 1, "steps": 25}},  # steps改为25
                "6": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": "Zhuang brocade innovative design, traditional craftsmanship..."
                    }
                },
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": "text, watermark, embedding:bad-picture-chill-75v..."
                    }
                },
                "11": {"class_type": "LoadImage", "inputs": {"image": data['image_url']}},
                "workflowUuid": "a80c31be2aba4901b0073cbc33be4741"  # 更新workflowUuid
            }
        }
        
        # 发送生成请求
        response = requests.post(
            LIBLIB_GENERATE_API_URL,
            json=request_body,
            headers={'Content-Type': 'application/json'},
            params={
                'AccessKey': LIBLIB_ACCESS_KEY,
                'Signature': signature,
                'Timestamp': timestamp,
                'SignatureNonce': nonce
            },
            timeout=30
        )
        
        if response.status_code != 200:
            return jsonify({'error': '生成请求失败', 'details': response.text}), 500
            
        result = response.json()
        if result.get('code') != 0:
            return jsonify({'error': '生成失败', 'message': result.get('msg')}), 500
            
        return jsonify({
            'status': '生成任务已提交',
            'task_id': result['data']['generateUuid']
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload', methods=['POST', 'GET'])
def upload_file():
    if request.method == 'GET':
        return "请使用POST方法上传文件", 400
        
    if 'file' not in request.files:
        return jsonify({'error': '没有文件部分'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    try:
        # 生成更复杂的唯一文件名
        img = Image.open(file.stream)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        random_str = os.urandom(8).hex()  # 增加随机字符串长度
        file_hash = hashlib.md5(file.read()).hexdigest()  # 添加文件内容哈希值
        file.seek(0)  # 重置文件指针
        
        filename = f"{timestamp}_{random_str}_{file_hash}_converted.png"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 检查文件是否已存在
        if os.path.exists(filepath):
            return jsonify({
                'error': '文件已存在',
                'suggestion': '请修改文件内容后重新上传'
            }), 400
            
        img.save(filepath, 'PNG')
        
        # 上传到FreeImageHost
        headers = {'X-API-Key': FREEIMGHOST_API_KEY}
        files = {'source': open(filepath, 'rb')}
        
        try:
            response = requests.post(
                FREEIMGHOST_API_URL,
                headers=headers,
                files=files,
                timeout=10
            )
            
            # 检查响应内容是否为JSON
            try:
                result = response.json()
            except ValueError:
                return jsonify({
                    'error': '图片上传服务返回了无效的响应',
                    'details': '服务暂时不可用，请稍后再试'
                }), 500
                
            if response.status_code == 200:
                if result.get('status_code') == 200:
                    image_url = result['image']['url']
                    print("原始图片链接:", image_url)
                    return jsonify({
                        'message': '文件上传成功',
                        'original_url': image_url,
                        'filename': filename
                    }), 200
                else:
                    return jsonify({
                        'error': '图片上传失败',
                        'details': result.get('status_txt', '未知错误')
                    }), 500
            else:
                return jsonify({
                    'error': '图片上传服务返回错误',
                    'status_code': response.status_code,
                    'details': result if isinstance(result, dict) else '服务错误'
                }), 500
                
        except requests.exceptions.RequestException as e:
            return jsonify({
                'error': '图片上传服务连接失败',
                'details': str(e)
            }), 500
            
    except Exception as e:
        return jsonify({'error': f'图片处理失败: {str(e)}'}), 400

@app.route('/check_status')
def check_status():
    task_id = request.args.get('task_id')
    if not task_id:
        return jsonify({'error': '缺少任务ID'}), 400
        
    try:
        # 生成签名参数
        timestamp = str(int(time.time() * 1000))  # 毫秒时间戳
        nonce = str(uuid.uuid4())  # 随机字符串
        signature = generate_signature(
            "/api/generate/comfy/status",  # API URI
            timestamp,
            nonce,
            LIBLIB_SECRET_KEY
        )
        
        response = requests.post(
            LIBLIB_STATUS_API_URL,
            json={'generateUuid': task_id},
            headers={'Content-Type': 'application/json'},
            params={
                'AccessKey': LIBLIB_ACCESS_KEY,
                'Signature': signature,
                'Timestamp': timestamp,
                'SignatureNonce': nonce
            },
            timeout=10
        )
        
        if response.status_code != 200:
            return jsonify({'error': '状态查询失败'}), 500
            
        result = response.json()
        if result.get('code') != 0:
            return jsonify({'error': result.get('msg')}), 500
            
        if result['data']['generateStatus'] == 5:  # 完成
            # 获取所有审核通过的图片
            valid_images = [img for img in result['data']['images'] if img['auditStatus'] == 3]
            if valid_images:
                # 只返回最后一张图片
                last_image = valid_images[-1]
                return jsonify({
                    'status': 'completed',
                    'image_url': last_image['imageUrl']
                })
            return jsonify({'status': 'failed', 'error': '没有可用的生成图片'})
        elif result['data']['generateStatus'] == 6:  # 失败
            return jsonify({'status': 'failed', 'error': result['data'].get('generateMsg')})
        else:
            return jsonify({'status': 'processing'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # debug 默认为关闭：Flask debug 模式会暴露交互式调试器，存在 RCE 风险
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", "5000"))
    print(f"壮锦纹样生成服务启动: http://127.0.0.1:{port}")
    print("接口: GET / | POST /upload | POST /generate | GET /check_status?task_id=")
    app.run(debug=debug, port=port)
