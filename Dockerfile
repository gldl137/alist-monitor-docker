# --- 阶段 1: 构建阶段 (Builder Stage) ---
# 使用您指定的 DaoCloud 镜像作为基础，以加速镜像拉取
FROM docker.m.daocloud.io/library/python:3.9-slim AS builder

# 设置工作目录
WORKDIR /app

# ---- 更换为清华大学的 apt 镜像源 ----
# 这是针对 Debian 11 (Bullseye) 的有效方法
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# ---- 安装编译依赖 ----
# 在同一层(layer)中执行 update, install 和 clean，可以减小镜像体积
# 这里安装的 gcc 和 python3-dev 是为了编译 bcrypt 等需要C扩展的库
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# 优先复制依赖文件，以充分利用 Docker 的层缓存机制
COPY requirements.txt .

# ---- 使用清华大学的 PyPI 镜像源 ----
# 将 Python 依赖预编译成 "wheels" 文件，这会让下一阶段的安装非常快
# 并且因为是预编译，下一阶段就不再需要 gcc 等编译工具了
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple


# --- 阶段 2: 最终生产阶段 (Final Stage) ---
# 再次使用轻量的 slim 镜像作为最终镜像的基础
FROM docker.m.daocloud.io/library/python:3.9-slim

WORKDIR /app

# 从构建阶段复制预编译好的 wheels 文件
COPY --from=builder /wheels /wheels

# 安装依赖
# 直接从本地的 wheels 文件安装，速度极快
# 同时安装 gunicorn 作为生产服务器
RUN pip install --no-cache-dir gunicorn /wheels/* && \
    rm -rf /wheels

# 复制您项目中的所有源代码到工作目录
COPY . .

# 设置环境变量，确保日志能直接输出，并指定为生产环境
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# 暴露应用运行的端口
EXPOSE 5000

# ---- 启动应用的最终命令 (已增加 --preload 标志) ----
# 使用 Gunicorn 启动应用，它是一个生产级的 WSGI 服务器
# '--preload' 标志确保应用代码在 fork 工作进程前只加载一次，避免重复初始化
# 'app.main:app' 指的是在 app 包内的 main.py 文件中，名为 app 的 Flask 应用实例
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "--preload", "app.main:app"]
