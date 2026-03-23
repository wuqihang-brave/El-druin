FROM python:3.11-slim

WORKDIR /app

# 复制requirements.txt
COPY requirements.txt .

# 安装依赖
RUN pip installmain:app --host 0.0.0.0 --port $PORT
