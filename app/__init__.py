# app/__init__.py
import os
from flask import Flask

def create_app():
    app = Flask(__name__)

    # --- 新增部分：为 Session 设置 Secret Key ---
    # 这是让登录功能正常工作的关键。
    # 为了安全，这个密钥应该是一个长且随机的字符串。
    # 我们使用环境变量，并提供一个默认值。
    app.secret_key = os.environ.get('SECRET_KEY', 'a-very-secure-and-random-secret-key-for-alist-monitor')

    return app
