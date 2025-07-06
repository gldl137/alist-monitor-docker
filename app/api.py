# app/api.py
from flask import Blueprint, request, jsonify, session, current_app
from app.monitor import (
    get_storage_status, get_storage_list, send_notification
)
from app.config import (
    load_config, save_config, load_monitor_status, save_monitor_status,
    get_password, save_password, verify_password,
    load_notifications, save_notifications, add_notification_record
)
from .monitor import monitor_task 
import logging
from functools import wraps
from datetime import datetime, timezone

api = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session: return jsonify({"success": False, "message": "请先登录"}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- 常规接口 (无改动) ---
@api.route('/login', methods=['POST'])
def login():
    if not request.is_json: return jsonify({"success": False, "message": "请求必须是JSON格式"}), 415
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    if not username or not password: return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400
    stored_password = get_password()
    if not stored_password: return jsonify({"success": False, "message": "系统错误，请联系管理员"}), 500
    if username == 'admin' and verify_password(password, stored_password):
        session['logged_in'] = True
        return jsonify({"success": True, "message": "登录成功", "redirect": "/"})
    else: return jsonify({"success": False, "message": "用户名或密码错误"}), 401

@api.route('/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return jsonify({"success": True, "message": "已成功退出"})

@api.route('/change_password', methods=['POST'])
@login_required
def change_password():
    if not request.is_json: return jsonify({"success": False, "message": "请求必须是JSON格式"}), 415
    data = request.get_json()
    old_password, new_password = data.get('old_password'), data.get('new_password')
    if not old_password or not new_password: return jsonify({"success": False, "message": "新旧密码均不能为空"}), 400
    if not verify_password(old_password, get_password()): return jsonify({"success": False, "message": "旧密码错误"}), 400
    if len(new_password) < 8: return jsonify({"success": False, "message": "新密码长度至少需要8个字符"}), 400
    if save_password(new_password):
        session.pop('logged_in', None)
        return jsonify({"success": True, "message": "密码修改成功，请重新登录", "redirect": "/login"})
    else: return jsonify({"success": False, "message": "密码修改失败，请稍后重试"}), 500

@api.route('/config', methods=['GET', 'POST'])
@login_required
def config_management():
    if request.method == 'GET':
        config_data = load_config()
        config_data.pop('password', None)
        return jsonify(config_data)
    if not request.is_json: return jsonify({"success": False, "message": "请求必须是JSON格式"}), 415
    new_data = request.get_json()
    if new_data.get('password'):
        new_password = new_data.pop('password')
        current_config = load_config()
        current_config.update(new_data)
        save_config(current_config)
        if save_password(new_password):
            session.pop('logged_in', None)
            return jsonify({"success": True, "message": "配置和密码均已更新...", "redirect": "/login"})
        else: return jsonify({"success": False, "message": "配置已保存，但密码更新失败"}), 500
    else:
        current_config = load_config()
        original_password_hash = current_config.get('password')
        current_config.update(new_data)
        if original_password_hash: current_config['password'] = original_password_hash
        if save_config(current_config): return jsonify({"success": True, "message": "配置保存成功"})
        else: return jsonify({"success": False, "message": "配置保存失败"}), 500

@api.route('/monitor_status', methods=['GET', 'POST'])
@login_required
def monitor_status_endpoint():
    scheduler = current_app.scheduler
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        is_monitoring = data.get('is_monitoring')
        if is_monitoring is True:
            interval, start_time_str = data.get('interval'), data.get('start_time')
            if not interval or not start_time_str: return jsonify({"success": False, "message": "启动监控缺少参数"}), 400
            try:
                scheduler.add_job(func=monitor_task, trigger='interval', seconds=int(interval), id='alist_monitor_job', replace_existing=True)
                status_to_save = {'is_monitoring': True, 'start_time': start_time_str, 'check_count': 0, 'interval': int(interval)}
                save_monitor_status(status_to_save)
                return jsonify({"success": True, "message": "监控已在后台启动", "status": status_to_save})
            except Exception as e: return jsonify({"success": False, "message": f"启动监控失败: {e}"}), 500
        elif is_monitoring is False:
            try: scheduler.remove_job('alist_monitor_job')
            except Exception: pass
            status_to_save = {'is_monitoring': False, 'start_time': None, 'check_count': 0, 'interval': None}
            save_monitor_status(status_to_save)
            return jsonify({"success": True, "message": "监控已在后台停止", "status": status_to_save})
        else: return jsonify({"success": False, "message": "请求无效"}), 400
    else: return jsonify(load_monitor_status())

@api.route('/storage_status', methods=['GET'])
@login_required
def storage_status(): return jsonify(get_storage_status())

@api.route('/storage_list', methods=['GET'])
@login_required
def storage_list(): return jsonify(get_storage_list())
    
@api.route('/check_storage', methods=['POST'])
@login_required
def check_storage():
    status = load_monitor_status()
    if status.get('is_monitoring'):
        status['check_count'] = status.get('check_count', 0) + 1
        save_monitor_status(status)
    config = load_config()
    data = request.get_json()
    config_changed = False
    if data.get('storage_path') and data['storage_path'] != config.get('ALIST_URL'):
        config['ALIST_URL'], config_changed = data['storage_path'], True
    if data.get('api_key') and data['api_key'] != config.get('ALIST_TOKEN'):
        config['ALIST_TOKEN'], config_changed = data['api_key'], True
    if config_changed: save_config(config)
    result = get_storage_status()
    add_notification_record({
        "message": f"手动检查完成: {result.get('status', '未知')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "success" if result.get('status') == '正常' else "warning"
    })
    return jsonify({"success": result.get('success', False), "message": "检查完成", "data": result})

# --- 新的通知接口 ---
@api.route('/notify/test', methods=['POST'])
@login_required
def notify_test():
    result, message = send_notification('test')
    return jsonify({"success": result, "message": message})

@api.route('/notify/start', methods=['POST'])
@login_required
def notify_start():
    data = request.get_json()
    start_time_iso = data.get('start_time')
    interval = data.get('interval')
    
    start_time_local = datetime.fromisoformat(start_time_iso.replace('Z', '+00:00'))\
        .astimezone(timezone(datetime.now().astimezone().utcoffset()))\
        .strftime('%Y-%m-%d %H:%M:%S')

    send_notification('start', data={'start_time': start_time_local, 'interval': interval})
    return jsonify({"success": True})

@api.route('/notify/stop', methods=['POST'])
@login_required
def notify_stop():
    data = request.get_json()
    duration = data.get('duration')
    stop_time_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    send_notification('stop', data={'stop_time': stop_time_local, 'duration': duration})
    return jsonify({"success": True})

# --- 通知记录接口 (无改动) ---
@api.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    return jsonify(load_notifications())

@api.route('/notifications', methods=['DELETE'])
@login_required
def clear_notifications_endpoint():
    save_notifications([])
    return jsonify({"success": True, "message": "通知记录已清除"})