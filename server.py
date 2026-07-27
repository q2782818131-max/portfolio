"""
丘天财作品集 — 后台服务器
Flask + JSON 数据存储，支持作品增删改 + 图片上传
"""
import json
import os
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import (
    Flask, request, jsonify, session, send_from_directory,
    render_template_string, redirect, url_for
)
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'qiutiancai-portfolio-2026-secret-key-change-me')

# ── 持久化存储 ──
# Render 上文件系统是临时的 → 用 Disk 挂载路径；本地保持原位
IS_RENDER = os.environ.get('RENDER') is not None
DATA_ROOT = Path(os.environ.get('DATA_DIR', '/var/data' if IS_RENDER else '.'))
if not DATA_ROOT.exists():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)

# ── 配置 ──
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'qiu2026')
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
DATA_FILE = DATA_ROOT / 'works.json'
UPLOAD_DIR = DATA_ROOT / 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'webm'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

UPLOAD_DIR.mkdir(exist_ok=True)

# ── 默认作品数据 ──
DEFAULT_WORKS = [
    {
        "id": "blender",
        "title": "三维科幻短片",
        "category": "01 / 3D 动画",
        "description": "独立完成科幻飞船与空间场景建模、材质、灯光设计，设计镜头运动与动画节奏——全流程 Blender 作品。",
        "tags": ["Blender", "建模", "灯光渲染"],
        "image": "",
        "video": "",
        "color": "#ff9955",
        "order": 1
    },
    {
        "id": "ue5",
        "title": "UE5 场景设计",
        "category": "02 / 实时引擎",
        "description": "使用 Lumen / Nanite 搭建雪地、沙漠、海洋实时场景，完成场景构图、灯光设计与镜头展示。",
        "tags": ["UE5", "Lumen", "Nanite"],
        "image": "",
        "video": "",
        "color": "#ffffff",
        "order": 2
    },
    {
        "id": "aigc",
        "title": "AI 场景生成",
        "category": "03 / AIGC",
        "description": "SD + ControlNet 线稿→成品，Depth/Lineart 控制结构稳定，ComfyUI 搭建完整工作流——科幻/卡牌/二次元。",
        "tags": ["Stable Diffusion", "ComfyUI", "ControlNet"],
        "image": "",
        "video": "",
        "color": "#a855f7",
        "order": 3
    },
    {
        "id": "ae",
        "title": "游戏抽卡动画",
        "category": "04 / 动态设计",
        "description": "AE 完成卡牌抽卡动画全流程：出卡、特效、节奏设计，独立整合角色/卡框/背景素材，符合商业化需求。",
        "tags": ["After Effects", "Motion Design", "节奏设计"],
        "image": "",
        "video": "",
        "color": "#9999ff",
        "order": 4
    },
    {
        "id": "ua",
        "title": "UA 视频制作",
        "category": "05 / 游戏买量",
        "description": "日产 6 条信息流前贴，面向 30-40 岁男性受众，6 大钩子类型体系，口播+红包+实机——完整 UA 管线。",
        "tags": ["UA 买量", "口播文案", "数据分析"],
        "image": "",
        "video": "",
        "color": "#ff3333",
        "order": 5
    },
    {
        "id": "social",
        "title": "信息流剪辑",
        "category": "06 / 短视频",
        "description": "抖音/小红书账号视觉内容制作，PR/AE 剪辑包装，数据驱动优化——单条最高 15W+ 播放。",
        "tags": ["Premiere Pro", "AE", "抖音运营"],
        "image": "",
        "video": "",
        "color": "#00cccc",
        "order": 6
    }
]


def load_works():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_WORKS


def save_works(works):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(works, f, ensure_ascii=False, indent=2)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated


# ── 媒体文件管理 ──
MEDIA_DIR = DATA_ROOT / 'media'
MEDIA_DIR.mkdir(exist_ok=True)

ALLOWED_MEDIA = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'webm'}


@app.route('/api/works/<work_id>/media', methods=['GET'])
def api_get_media(work_id):
    """获取某作品的所有媒体文件"""
    media_list = []
    work_dir = MEDIA_DIR / work_id
    if work_dir.exists():
        for f in sorted(work_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix.lower().lstrip('.') in ALLOWED_MEDIA:
                media_list.append({
                    'id': f.stem,
                    'type': 'video' if f.suffix.lower() in {'.mp4', '.mov', '.webm'} else 'image',
                    'url': f'/media/{work_id}/{f.name}',
                    'name': f.name
                })
    return jsonify(media_list)


@app.route('/api/works/<work_id>/media', methods=['POST'])
@login_required
def api_upload_media(work_id):
    """上传媒体到某作品"""
    work_dir = MEDIA_DIR / work_id
    work_dir.mkdir(exist_ok=True)

    uploaded = []
    for key in request.files:
        for file in request.files.getlist(key):
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                fid = uuid.uuid4().hex[:8]
                filename = f"{fid}.{ext}"
                file.save(work_dir / filename)
                uploaded.append({
                    'id': fid,
                    'type': 'video' if ext in {'mp4', 'mov', 'webm'} else 'image',
                    'url': f'/media/{work_id}/{filename}',
                    'name': file.filename
                })
    return jsonify({'ok': True, 'media': uploaded})


@app.route('/api/works/<work_id>/media/<media_id>', methods=['DELETE'])
@login_required
def api_delete_media(work_id, media_id):
    """删除某作品的某个媒体文件"""
    work_dir = MEDIA_DIR / work_id
    for f in work_dir.iterdir():
        if f.stem == media_id:
            f.unlink()
            return jsonify({'ok': True})
    return jsonify({'error': '文件不存在'}), 404


# ── 工具数据 ──
TOOLS_FILE = DATA_ROOT / 'tools.json'

def load_tools():
    if TOOLS_FILE.exists():
        try:
            with open(TOOLS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_tools(tools):
    with open(TOOLS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated


# ── 页面路由 ──

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(str(UPLOAD_DIR), filename)


# ── API: 获取所有作品 ──

@app.route('/api/works', methods=['GET'])
def api_get_works():
    works = load_works()
    works.sort(key=lambda w: w.get('order', 999))
    return jsonify(works)


# ── API: 登录 ──

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    password = data.get('password', '')
    if hashlib.sha256(password.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
        session['admin'] = True
        return jsonify({'ok': True})
    return jsonify({'error': '密码错误'}), 403


# ── API: 登出 ──

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('admin', None)
    return jsonify({'ok': True})


# ── API: 检查登录状态 ──

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({'admin': session.get('admin', False)})


# ── API: 添加作品 ──

@app.route('/api/works', methods=['POST'])
@login_required
def api_add_work():
    data = request.form.to_dict()
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': '作品标题不能为空'}), 400

    works = load_works()
    work_id = uuid.uuid4().hex[:8]

    # 处理图片上传
    image_path = ''
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{work_id}.{ext}"
            file.save(UPLOAD_DIR / filename)
            image_path = f"/uploads/{filename}"

    # 处理视频上传
    video_path = data.get('video', '').strip()
    if 'video_file' in request.files:
        vfile = request.files['video_file']
        if vfile and vfile.filename and allowed_file(vfile.filename):
            vext = vfile.filename.rsplit('.', 1)[1].lower()
            vfilename = f"{work_id}_v.{vext}"
            vfile.save(UPLOAD_DIR / vfilename)
            video_path = f"/uploads/{vfilename}"

    work = {
        "id": work_id,
        "title": title,
        "category": data.get('category', '').strip(),
        "description": data.get('description', '').strip(),
        "tags": [t.strip() for t in data.get('tags', '').split(',') if t.strip()],
        "image": image_path,
        "video": video_path,
        "color": data.get('color', '#8ab4f8').strip(),
        "order": len(works) + 1
    }
    works.append(work)
    save_works(works)
    return jsonify({'ok': True, 'work': work})


# ── API: 更新作品 ──

@app.route('/api/works/<work_id>', methods=['PUT'])
@login_required
def api_update_work(work_id):
    works = load_works()
    target = next((w for w in works if w['id'] == work_id), None)
    if not target:
        return jsonify({'error': '作品不存在'}), 404

    data = request.form.to_dict()
    for field in ['title', 'category', 'description', 'tags', 'color']:
        if field in data:
            val = data[field].strip()
            if field == 'tags':
                target[field] = [t.strip() for t in val.split(',') if t.strip()]
            else:
                target[field] = val

    # 图片更新
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            # 删除旧图片
            if target.get('image'):
                old_path = UPLOAD_DIR / Path(target['image']).name
                if old_path.exists():
                    old_path.unlink()
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{work_id}.{ext}"
            file.save(UPLOAD_DIR / filename)
            target['image'] = f"/uploads/{filename}"

    if 'video_file' in request.files:
        vfile = request.files['video_file']
        if vfile and vfile.filename and allowed_file(vfile.filename):
            if target.get('video'):
                old_v = UPLOAD_DIR / Path(target['video']).name
                if old_v.exists():
                    old_v.unlink()
            vext = vfile.filename.rsplit('.', 1)[1].lower()
            vfilename = f"{work_id}_v.{vext}"
            vfile.save(UPLOAD_DIR / vfilename)
            target['video'] = f"/uploads/{vfilename}"

    save_works(works)
    return jsonify({'ok': True, 'work': target})


# ── API: 删除作品 ──

@app.route('/api/works/<work_id>', methods=['DELETE'])
@login_required
def api_delete_work(work_id):
    works = load_works()
    target = next((w for w in works if w['id'] == work_id), None)
    if not target:
        return jsonify({'error': '作品不存在'}), 404

    # 删除关联文件
    for field in ['image', 'video']:
        if target.get(field):
            filepath = UPLOAD_DIR / Path(target[field]).name
            if filepath.exists():
                filepath.unlink()

    works = [w for w in works if w['id'] != work_id]
    save_works(works)
    return jsonify({'ok': True})


# ── API: 调整排序 ──

@app.route('/api/works/reorder', methods=['POST'])
@login_required
def api_reorder():
    data = request.get_json()
    order = data.get('order', [])
    works = load_works()
    for i, wid in enumerate(order):
        for w in works:
            if w['id'] == wid:
                w['order'] = i
                break
    save_works(works)
    return jsonify({'ok': True})


# ── API: 工具列表 ──

@app.route('/api/tools', methods=['GET'])
def api_get_tools():
    return jsonify(load_tools())


@app.route('/api/tools', methods=['POST'])
@login_required
def api_save_tools():
    tools = request.get_json()
    save_tools(tools)
    return jsonify({'ok': True})


if __name__ == '__main__':
    if not DATA_FILE.exists():
        save_works(DEFAULT_WORKS)
    print(f'\n>>> 丘天财作品集服务器已启动')
    print(f'    数据目录: {DATA_ROOT}')
    print(f'    访问: http://localhost:5000')
    print(f'    管理: 页面右上角 登录 (密码: qiu2026)\n')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('RENDER') is None
    app.run(host='0.0.0.0', port=port, debug=debug)
