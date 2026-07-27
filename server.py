"""
丘天财作品集 — 后台服务器
Flask + Supabase，支持作品增删改 + 图片上传，数据永不离失
"""
import hashlib
import os
import uuid
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory, session
from supabase import create_client

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'qiutiancai-portfolio-2026-secret-key-change-me')

# ── Supabase 配置 ──
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')  # service_role key
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── 常规配置 ──
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'qiu2026')
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
ALLOWED_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'webm'}

BUCKET_UPLOADS = 'uploads'
BUCKET_MEDIA = 'media'


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated


def public_url(bucket, path):
    """Supabase Storage 公开 URL"""
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"


def upload_to_storage(bucket, path, file):
    """上传文件到 Supabase Storage，返回公开 URL"""
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    mime = f"video/{ext}" if ext in {'mp4', 'mov', 'webm'} else f"image/{ext}"
    file.seek(0)
    supabase.storage.from_(bucket).upload(
        path, file.read(),
        file_options={'content-type': mime}
    )
    return public_url(bucket, path)


def remove_from_storage(bucket, path):
    """删除存储文件（不存在则忽略）"""
    try:
        supabase.storage.from_(bucket).remove([path])
    except Exception:
        pass


def parse_storage_url(url):
    """从完整 URL 提取 (bucket, path)，失败返回 (None, None)"""
    marker = '/storage/v1/object/public/'
    if not url or marker not in url:
        return None, None
    parts = url.split(marker)[1].split('/', 1)
    return parts[0], parts[1] if len(parts) > 1 else None


def row_to_work(row):
    return {
        'id': row['id'],
        'title': row['title'],
        'category': row.get('category', ''),
        'description': row.get('description', ''),
        'tags': row.get('tags', []),
        'image': row.get('image', ''),
        'video': row.get('video', ''),
        'color': row.get('color', '#8ab4f8'),
        'order': row.get('order', 0),
    }


# ═══════════════════════════════════════════
# 调试端点（排查问题后删除）
# ═══════════════════════════════════════════

@app.route('/api/debug', methods=['GET'])
def api_debug():
    info = {'supabase_url': SUPABASE_URL[:30] + '...' if SUPABASE_URL else 'EMPTY',
            'key_set': bool(SUPABASE_KEY)}
    try:
        res = supabase.table('works').select('id', count='exact').execute()
        info['works_count'] = res.count if hasattr(res, 'count') else len(res.data or [])
        info['db_ok'] = True
    except Exception as e:
        info['db_ok'] = False
        info['db_error'] = str(e)
    try:
        supabase.storage.from_(BUCKET_UPLOADS).list()
        info['storage_ok'] = True
    except Exception as e:
        info['storage_ok'] = False
        info['storage_error'] = str(e)
    return jsonify(info)

# ═══════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


# ═══════════════════════════════════════════
# 认证 API
# ═══════════════════════════════════════════

@app.route('/api/login', methods=['POST'])
def api_login():
    pw = request.get_json().get('password', '')
    if hashlib.sha256(pw.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
        session['admin'] = True
        return jsonify({'ok': True})
    return jsonify({'error': '密码错误'}), 403


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('admin', None)
    return jsonify({'ok': True})


@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({'admin': session.get('admin', False)})


# ═══════════════════════════════════════════
# 作品 CRUD API
# ═══════════════════════════════════════════

@app.route('/api/works', methods=['GET'])
def api_get_works():
    res = supabase.table('works').select('*').order('order').execute()
    return jsonify([row_to_work(r) for r in (res.data or [])])


@app.route('/api/works', methods=['POST'])
@login_required
def api_add_work():
    data = request.form.to_dict()
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': '作品标题不能为空'}), 400

    work_id = uuid.uuid4().hex[:8]
    image_url = ''
    video_url = ''

    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            image_url = upload_to_storage(BUCKET_UPLOADS, f"{work_id}.{ext}", f)

    if 'video_file' in request.files:
        vf = request.files['video_file']
        if vf and vf.filename and allowed_file(vf.filename):
            ext = vf.filename.rsplit('.', 1)[1].lower()
            video_url = upload_to_storage(BUCKET_UPLOADS, f"{work_id}_v.{ext}", vf)

    # 计算排序位置
    res = supabase.table('works').select('order').order('order', desc=True).limit(1).execute()
    next_order = (res.data[0]['order'] + 1) if res.data else 1

    row = {
        'id': work_id, 'title': title,
        'category': data.get('category', '').strip(),
        'description': data.get('description', '').strip(),
        'tags': [t.strip() for t in data.get('tags', '').split(',') if t.strip()],
        'image': image_url, 'video': video_url,
        'color': data.get('color', '#8ab4f8').strip(),
        'order': next_order,
    }
    supabase.table('works').insert(row).execute()
    return jsonify({'ok': True, 'work': row_to_work(row)})


@app.route('/api/works/<work_id>', methods=['PUT'])
@login_required
def api_update_work(work_id):
    res = supabase.table('works').select('*').eq('id', work_id).execute()
    if not res.data:
        return jsonify({'error': '作品不存在'}), 404
    target = res.data[0]

    data = request.form.to_dict()
    updates = {}
    for field in ['title', 'category', 'description', 'color']:
        if field in data:
            updates[field] = data[field].strip()
    if 'tags' in data:
        updates['tags'] = [t.strip() for t in data['tags'].split(',') if t.strip()]

    # 图片替换
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename and allowed_file(f.filename):
            bucket, path = parse_storage_url(target.get('image', ''))
            if bucket and path:
                remove_from_storage(bucket, path)
            ext = f.filename.rsplit('.', 1)[1].lower()
            updates['image'] = upload_to_storage(BUCKET_UPLOADS, f"{work_id}.{ext}", f)

    # 视频替换
    if 'video_file' in request.files:
        vf = request.files['video_file']
        if vf and vf.filename and allowed_file(vf.filename):
            bucket, path = parse_storage_url(target.get('video', ''))
            if bucket and path:
                remove_from_storage(bucket, path)
            ext = vf.filename.rsplit('.', 1)[1].lower()
            updates['video'] = upload_to_storage(BUCKET_UPLOADS, f"{work_id}_v.{ext}", vf)

    if updates:
        supabase.table('works').update(updates).eq('id', work_id).execute()
        target.update(updates)

    return jsonify({'ok': True, 'work': row_to_work(target)})


@app.route('/api/works/<work_id>', methods=['DELETE'])
@login_required
def api_delete_work(work_id):
    res = supabase.table('works').select('*').eq('id', work_id).execute()
    if not res.data:
        return jsonify({'error': '作品不存在'}), 404
    target = res.data[0]

    # 删关联上传文件
    for field in ['image', 'video']:
        bucket, path = parse_storage_url(target.get(field, ''))
        if bucket and path:
            remove_from_storage(bucket, path)

    # 删媒体画廊文件
    try:
        files = supabase.storage.from_(BUCKET_MEDIA).list(work_id)
        for f in files:
            remove_from_storage(BUCKET_MEDIA, f"{work_id}/{f['name']}")
    except Exception:
        pass

    supabase.table('works').delete().eq('id', work_id).execute()
    return jsonify({'ok': True})


@app.route('/api/works/reorder', methods=['POST'])
@login_required
def api_reorder():
    order_list = request.get_json().get('order', [])
    for i, wid in enumerate(order_list):
        supabase.table('works').update({'order': i}).eq('id', wid).execute()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════
# 媒体画廊 API
# ═══════════════════════════════════════════

@app.route('/api/works/<work_id>/media', methods=['GET'])
def api_get_media(work_id):
    items = []
    try:
        files = supabase.storage.from_(BUCKET_MEDIA).list(work_id)
        for f in sorted(files, key=lambda x: x.get('created_at', ''), reverse=True):
            name = f['name']
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            if ext in ALLOWED_EXTS:
                items.append({
                    'id': name.rsplit('.', 1)[0] if '.' in name else name,
                    'type': 'video' if ext in {'mp4', 'mov', 'webm'} else 'image',
                    'url': public_url(BUCKET_MEDIA, f"{work_id}/{name}"),
                    'name': name,
                })
    except Exception:
        pass
    return jsonify(items)


@app.route('/api/works/<work_id>/media', methods=['POST'])
@login_required
def api_upload_media(work_id):
    uploaded = []
    for key in request.files:
        for f in request.files.getlist(key):
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                fid = uuid.uuid4().hex[:8]
                name = f"{fid}.{ext}"
                url = upload_to_storage(BUCKET_MEDIA, f"{work_id}/{name}", f)
                uploaded.append({
                    'id': fid,
                    'type': 'video' if ext in {'mp4', 'mov', 'webm'} else 'image',
                    'url': url,
                    'name': f.filename,
                })
    return jsonify({'ok': True, 'media': uploaded})


@app.route('/api/works/<work_id>/media/<media_id>', methods=['DELETE'])
@login_required
def api_delete_media(work_id, media_id):
    try:
        files = supabase.storage.from_(BUCKET_MEDIA).list(work_id)
        for f in files:
            if f['name'].startswith(media_id):
                remove_from_storage(BUCKET_MEDIA, f"{work_id}/{f['name']}")
                return jsonify({'ok': True})
    except Exception:
        pass
    return jsonify({'error': '文件不存在'}), 404


# ═══════════════════════════════════════════
# 工具 API
# ═══════════════════════════════════════════

@app.route('/api/tools', methods=['GET'])
def api_get_tools():
    res = supabase.table('tools').select('data').eq('id', 1).execute()
    if res.data:
        return jsonify(res.data[0].get('data') or [])
    return jsonify([])


@app.route('/api/tools', methods=['POST'])
@login_required
def api_save_tools():
    supabase.table('tools').upsert({'id': 1, 'data': request.get_json()}).execute()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════

if __name__ == '__main__':
    print(f'\n>>> 丘天财作品集服务器已启动')
    print(f'    Supabase: {SUPABASE_URL}')
    print(f'    访问: http://localhost:5000\n')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('RENDER') is None
    app.run(host='0.0.0.0', port=port, debug=debug)
