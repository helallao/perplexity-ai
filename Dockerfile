# Perplexity MCP Server Docker Image
# 使用多阶段构建优化镜像大小

FROM python:3.12-slim

WORKDIR /app

# 安装构建依赖 (curl_cffi 需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*


# 复制项目文件
COPY . .

# 使用 uv 创建虚拟环境并安装项目
RUN pip install -e .


# 暴露端口
EXPOSE 8000


COPY perplexity/ ./perplexity/

# 启动命令
CMD ["python", "-m", "perplexity.mcp_server", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
