# app/monitor.py
import requests
import json
import logging
import os
from datetime import datetime, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.config import load_config, load_monitor_status, save_monitor_status, add_notification_record

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 1. 消息模板定义 (已更新图片链接) ---
MESSAGE_TEMPLATES = {
    'start': {
        'title': '▶️ 后台监控已启动',
        'picurl': 'https://tc.z.wiki/autoupload/f/VGYUFUfjLTRdneshf7trSU1pPk5D901eM2bYIJnvuwCyl5f0KlZfm6UsKj-HyTuv/20250706/973O/400X320/%E7%B3%BB%E7%BB%9F%E5%90%AF%E5%8A%A81-min.jpg'
    },
    'stop': {
        'title': '⏹️ 后台监控已停止',
        'picurl': 'https://tc.z.wiki/autoupload/f/VGYUFUfjLTRdneshf7trSU1pPk5D901eM2bYIJnvuwCyl5f0KlZfm6UsKj-HyTuv/20250706/iwZf/400X320/%E7%B3%BB%E7%BB%9F%E5%81%9C%E6%AD%A21-min.jpg'
    },
    'anomaly': {
        'title': '⚠️ 后台监控发现异常',
        'picurl': 'https://tc.z.wiki/autoupload/f/VGYUFUfjLTRdneshf7trSU1pPk5D901eM2bYIJnvuwCyl5f0KlZfm6UsKj-HyTuv/20250706/G59r/400X320/%E7%B3%BB%E7%BB%9F%E5%BC%82%E5%B8%B81-min.jpg'
    },
    'test': {
        'title': '✅ 连接测试',
        'picurl': 'https://tc.z.wiki/autoupload/f/VGYUFUfjLTRdneshf7trSU1pPk5D901eM2bYIJnvuwCyl5f0KlZfm6UsKj-HyTuv/20250706/3XAw/400X320/%E7%B3%BB%E7%BB%9F%E6%B5%8B%E8%AF%951-min.jpg'
    }
}

# --- 2. 核心发送函数 (已修正) ---

def _send_tg_notification(token, chat_id, title, details, picurl):
    """
    为Telegram生成并发送带图片的消息 (使用 sendPhoto 方法)
    """
    # 组合标题和详情，并使用 Telegram 支持的 HTML 标签
    details_html = details.replace('\n', '<br>')
    # 将标题加粗，并与详情组合
    caption_html = f"<b>{title}</b><br><br>{details_html}"

    # 使用正确的 sendPhoto 方法
    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    # 构建请求体
    payload = {
        'chat_id': chat_id,
        'photo': picurl,          # 图片 URL
        'caption': caption_html,  # 格式化的标题和描述
        'parse_mode': 'HTML'
    }

    try:
        # 使用 POST 发送请求，并适当增加超时时间
        response = session.post(url, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        if result.get('ok'):
            logger.info("Telegram 图片通知发送成功")
            return True
        else:
            # 记录下 Telegram 返回的具体错误信息
            logger.error(f"Telegram API 返回错误: {result.get('description')}")
            return False
    except Exception as e:
        logger.error(f"发送 Telegram 图片通知失败: {e}")
        return False


def _send_wecom_notification(webhook, title, details, picurl):
    """为企业微信生成并发送图文卡片(news)消息"""
    data = {
        "msgtype": "news",
        "news": {
            "articles": [
                {
                    "title": title,
                    "description": details,
                    "url": "https://wework.qq.com",  # 可以放一个相关的链接
                    "picurl": picurl
                }
            ]
        }
    }
    try:
        response = session.post(webhook, headers={"Content-Type": "application/json"}, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get('errcode') == 0:
            logger.info("企业微信图文通知发送成功")
            return True
        else:
            logger.error(f"企业微信图文通知发送失败: {result.get('errmsg')}")
            return False
    except Exception as e:
        logger.error(f"发送企业微信图文通知失败: {e}")
        return False

# --- 3. 统一的通知入口函数 ---

def send_notification(notification_type, data={}):
    """
    统一的通知发送入口
    """
    config = load_config()
    method = config.get('NOTIFICATION_METHOD', 'wecom')
    template = MESSAGE_TEMPLATES.get(notification_type, {})
    
    if not template:
        return False, "未知的通知类型"

    title = template['title']
    picurl = template['picurl']
    details = ""

    if notification_type == 'start':
        details = f"启动时间: {data.get('start_time')}\n监控间隔: {data.get('interval')}"
    elif notification_type == 'stop':
        details = f"停止时间: {data.get('stop_time')}\n运行时长: {data.get('duration')}"
    elif notification_type == 'anomaly':
        details = data.get('error_details', '未知异常')
    elif notification_type == 'test':
        details = f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n方式: {'Telegram' if method == 'tg' else '企业微信'}"

    # 替换换行符为空格，使日志更易读
    log_message = f"{title} - {details.replace(chr(10), ' ')}"
    notification_record_type = "info" if notification_type in ['start', 'stop', 'test'] else "error"
    
    add_notification_record({
        "message": log_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": notification_record_type
    })
    
    if method == 'tg':
        token = config.get('TG_BOT_TOKEN')
        chat_id = config.get('TG_CHAT_ID')
        if not token or not chat_id:
            return False, "Telegram Bot Token 或 Chat ID 未配置"
        result = _send_tg_notification(token, chat_id, title, details, picurl)
        return result, "Telegram 通知发送成功" if result else "Telegram 通知发送失败"

    else: # 默认企业微信
        webhook = config.get('WECOM_WEBHOOK')
        if not webhook:
            return False, "企业微信 Webhook 未配置"
        result = _send_wecom_notification(webhook, title, details, picurl)
        return result, "企业微信通知发送成功" if result else "企业微信通知发送失败"


# --- 4. 后台监控任务 ---

def monitor_task():
    """后台定时监控任务，发现异常时调用统一通知入口"""
    try:
        status = load_monitor_status()
        status['check_count'] = status.get('check_count', 0) + 1
        save_monitor_status(status)
        logger.info(f"开始执行后台定时监控任务 (第 {status['check_count']} 次)")

        result = get_storage_status()
        
        if result.get('status') == '异常':
            abnormal_storages = [s for s in result.get('storages', []) if s.get('status') not in ['work', 'disabled']]
            error_details = f"发现{len(abnormal_storages)}个异常存储:\n" + \
                            "\n".join([f" - {s.get('name', '未知路径')} 状态: {s.get('status', '未知')}" for s in abnormal_storages])
            send_notification('anomaly', data={'error_details': error_details})

        elif not result.get('success'):
             send_notification('anomaly', data={'error_details': result.get('message', '获取状态失败')})
        else:
            logger.info("监控检查完成，所有存储状态正常。")

    except Exception as e:
        logger.error(f"后台监控任务执行出错: {e}", exc_info=True)
        send_notification('anomaly', data={'error_details': f'监控任务执行出错: {e}'})


# --- 基础函数 ---

def create_retry_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504], allowed_methods=["GET", "POST"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

session = create_retry_session()

def get_storage_status():
    """获取Alist存储状态的核心函数"""
    check_time_iso = datetime.now(timezone.utc).isoformat()
    config = load_config()
    ALIST_URL = config.get('ALIST_URL')
    ALIST_TOKEN = config.get('ALIST_TOKEN')
    
    if not ALIST_URL or not ALIST_TOKEN:
        return {"success": False, "message": "未配置Alist连接信息", "status": "异常", "storages": []}

    url = f"{ALIST_URL.rstrip('/')}/api/admin/storage/list"
    headers = {"Authorization": ALIST_TOKEN}
    try:
        response = session.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        storage_list = response.json().get('data', {}).get('content', [])
        
        is_abnormal = False
        storages_info = []
        for s in storage_list:
            status = s.get('status', 'unknown')
            if status not in ['work', 'disabled']:
                is_abnormal = True
            
            storages_info.append({
                'name': s.get('mount_path', '/'),
                'driver': s.get('driver', '未知'),
                'status': status,
                'last_updated': check_time_iso 
            })
        
        overall_status = "异常" if is_abnormal else "正常"
        
        return {
            "success": True, 
            "message": "获取存储状态成功",
            "status": overall_status,
            "last_checked": check_time_iso,
            "storages": storages_info
        }
    except Exception as e:
        logger.error(f"请求 {url} 失败: {e}")
        return {"success": False, "message": f"无法获取存储状态: {e}", "status": "异常", "storages": []}

def get_storage_list():
    """获取存储列表，供API调用"""
    return get_storage_status()
