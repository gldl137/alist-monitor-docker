<!-- 文件名：README.md -->
<!-- 这是项目的“说明书”，别人访问你的仓库时第一眼看到的就是它 -->

# Alist 监控系统

一个用于监控 Alist 存储状态并通过企业微信或 Telegram 发送通知的 Web 应用。本项目已完全容器化，便于快速部署。【兼容Openlist】

## ✨ 主要功能

- **Web UI**: 提供简洁的网页界面，用于配置 Alist 地址、通知方式等。
- **后台监控**: 定时检查 Alist 的所有存储，发现异常状态时自动告警。
- **多种通知渠道**: 支持企业微信机器人和 Telegram Bot 推送通知。
- **状态持久化**: 即使容器重启，配置和监控任务也能自动恢复。
- **容器化部署**: 提供 Dockerfile，一键构建和部署。

## 🚀 快速开始 (使用 Docker)

1.  **克隆仓库**
    ```bash
    git clone [https://github.com/yuai66/alist-monitor-docker.git](https://github.com/yuai66/alist-monitor-docker.git)
    cd alist-monitor-docker
    ```

2.  **创建数据目录**
    在项目根目录创建一个 `data` 文件夹，所有配置和数据库文件都会保存在这里。
    ```bash
    mkdir data
    ```

3.  **构建 Docker 镜像**
    ```bash
    docker build -t alist-monitor .
    ```

4.  **运行容器**
    使用下面的命令启动容器，它会将您本地的 `data` 目录挂载到容器中，实现数据持久化。
    ```bash
    docker run -d \
      -p 5000:5000 \
      --name my-alist-monitor \
      -v "$(pwd)/data:/data" \
      alist-monitor
    ```

5.  **访问和配置**
    在浏览器中打开 `http://<你的服务器IP>:5000` 即可访问 Web 界面。
    - 默认用户名: `admin`
    - 默认密码: `admin`
    
    **请在首次登录后立即修改密码！**

## 🔧 技术栈

- 后端: Flask, APScheduler
- 前端: Tailwind CSS
- 部署: Docker, Gunicorn
```
```
<!-- 文件名：.gitignore -->
<!-- 这个文件告诉 Git 哪些文件不需要上传到仓库，非常重要！-->

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/

# 数据库和数据文件
# 确保不会将本地的配置和数据上传到公开仓库
data/
*.sqlite
*.sqlite3

# IDE/编辑器 配置文件
.idea/
.vscode/
*.swp
