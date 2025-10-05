# 1. 使用官方推荐的 Python 3.11-slim 作为基础镜像
# This provides a lightweight environment with Python pre-installed.
FROM python:3.11-slim

# 设置环境变量，防止生成 .pyc 文件并确保日志直接输出
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. 在容器内创建一个工作目录
WORKDIR /app

# 4. 复制依赖文件到工作目录
# We copy the requirements file first to leverage Docker's layer caching.
# Dependencies will only be reinstalled if this file changes.
COPY requirements.txt .

# 5. 安装项目依赖
# The --no-cache-dir option keeps the image size smaller.
RUN pip install --no-cache-dir -r requirements.txt

# 6. 复制项目的所有文件到工作目录
# This includes the main.py and the app folder.
COPY . .

# 7. 暴露应用程序运行的端口
# The application listens on port 8080 by default.
EXPOSE 8080

# 8. 设置容器启动时执行的命令
# This command starts the FastAPI application.
CMD ["python", "main.py"]
