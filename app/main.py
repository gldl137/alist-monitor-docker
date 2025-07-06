# app/main.py
import os
import atexit
import logging
from flask import Flask, render_template, send_from_directory, request, redirect, session, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app import create_app
from app.monitor import monitor_task
from app.config import load_monitor_status, initialize_default_password

# --- 基本配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 创建 Flask app 实例 ---
app = create_app()

# --- 初始化和启动调度器 ---
DATA_DIR = '/data'
DB_PATH = os.path.join(DATA_DIR, 'alist_monitor.sqlite')

# 确保 /data 目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 配置调度器
jobstores = {'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_PATH}')}
scheduler = BackgroundScheduler(jobstores=jobstores, timezone="Asia/Shanghai")

# 将 scheduler 附加到 app 对象，以便在 API 蓝图中访问
app.scheduler = scheduler

# 启动调度器
scheduler.start()
logger.info("调度器已启动。")

# 恢复持久化的监控任务
status = load_monitor_status()
if status.get('is_monitoring') and status.get('interval'):
    logger.info(f"检测到持久化的监控任务，尝试恢复... 间隔: {status['interval']}秒")
    scheduler.add_job(
        func=monitor_task,
        trigger='interval',
        seconds=int(status['interval']),
        id='alist_monitor_job',
        replace_existing=True
    )
    logger.info("后台监控任务已成功恢复。")

# 注册一个退出钩子，在应用关闭时安全地关闭调度器
atexit.register(lambda: scheduler.shutdown())

# --- 初始化默认密码 ---
# 这个操作现在是幂等的，可以安全地在每次启动时调用
initialize_default_password()

# --- 注册蓝图 ---
from app.api import api
app.register_blueprint(api, url_prefix='/api')


# --- Flask 路由 ---
@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/change_password')
def change_password_page():
    if 'logged_in' not in session:
        return redirect('/login')
    return render_template('change_password.html')

@app.route('/')
@app.route('/index.html')
def index():
    if 'logged_in' not in session:
        return redirect('/login')
    return render_template('index.html')

# 本地调试时，Flask 会自动处理 static 文件夹
# 在 Gunicorn 部署中，通常由反向代理（如 Nginx）处理静态文件
# 此处保留是为了本地调试的便利性
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)
