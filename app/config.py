# app/config.py
import os
import json
import bcrypt
import logging
from functools import wraps

logger = logging.getLogger(__name__)

# --- 文件路径定义 (保持不变) ---
DATA_DIR = '/data'
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
MONITOR_STATUS_PATH = os.path.join(DATA_DIR, 'monitor_status.json')
NOTIFICATIONS_PATH = os.path.join(DATA_DIR, 'notifications.json')

# --- 装饰器：确保目录存在 ---
def ensure_data_dir_exists(func):
    """确保 /data 目录存在的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        os.makedirs(DATA_DIR, exist_ok=True)
        return func(*args, **kwargs)
    return wrapper

# --- 内部辅助函数 (已简化，移除文件锁) ---
def _load_json_file(file_path, default_value):
    """通用函数：加载JSON文件"""
    if not os.path.exists(file_path):
        return default_value
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 如果文件为空，也返回默认值
            return json.loads(content) if content else default_value
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"加载JSON文件 {file_path} 失败: {e}")
        return default_value

def _save_json_file(file_path, data, indent=4):
    """通用函数：保存数据到JSON文件 (使用临时文件保证原子性)"""
    try:
        temp_path = file_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        # 使用 os.replace 保证操作的原子性，避免文件损坏
        os.replace(temp_path, file_path)
        return True
    except Exception as e:
        logger.error(f"保存JSON文件 {file_path} 失败: {e}")
        return False

# --- 核心配置函数 ---
@ensure_data_dir_exists
def load_config():
    """从文件加载配置"""
    return _load_json_file(CONFIG_PATH, default_value={})

@ensure_data_dir_exists
def save_config(config):
    """安全地保存配置到文件"""
    return _save_json_file(CONFIG_PATH, config, indent=4)

# --- 监控状态函数 ---
@ensure_data_dir_exists
def load_monitor_status():
    return _load_json_file(MONITOR_STATUS_PATH, default_value={'is_monitoring': False, 'start_time': None, 'check_count': 0, 'interval': None})

@ensure_data_dir_exists
def save_monitor_status(status):
    return _save_json_file(MONITOR_STATUS_PATH, status, indent=2)

# --- 通知记录函数 ---
@ensure_data_dir_exists
def load_notifications():
    """从文件加载通知记录"""
    return _load_json_file(NOTIFICATIONS_PATH, default_value=[])

@ensure_data_dir_exists
def save_notifications(notifications):
    """保存通知记录到文件"""
    return _save_json_file(NOTIFICATIONS_PATH, notifications, indent=2)

def add_notification_record(notification):
    """添加一条新的通知记录，并保持日志大小"""
    MAX_NOTIFICATIONS = 100
    notifications = load_notifications()
    notifications.insert(0, notification)
    trimmed_notifications = notifications[:MAX_NOTIFICATIONS]
    save_notifications(trimmed_notifications)

# --- 密码相关函数 ---
def get_password():
    config = load_config()
    return config.get('password')

def save_password(password):
    if not password:
        return False
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    config = load_config()
    config['password'] = hashed.decode('utf-8')
    return save_config(config)

def verify_password(raw_password, hashed_password):
    if not raw_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(raw_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def initialize_default_password():
    """初始化默认密码（如果未设置）"""
    if get_password():
        return True
    logger.warning("警告：未设置密码，已初始化为默认值 'admin'。请尽快修改密码！")
    return save_password('admin')
