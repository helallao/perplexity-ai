# Docker 部署指南

## 快速开始

### 1. 配置环境变量

```bash
# 复制环境变量模板
cp docker/env.example .env

# 编辑 .env 文件，填入你的配置
```

### 2. 构建并启动

```bash
# 使用 docker-compose 启动
docker-compose up -d

# 或者单独构建和运行
docker build -t perplexity-mcp .
docker run -d -p 8000:8000 \
  -e MCP_TOKEN=sk-123456 \
  -e PPLX_NEXT_AUTH_CSRF_TOKEN=your_csrf_token \
  -e PPLX_SESSION_TOKEN=your_session_token \
  --name perplexity-mcp \
  perplexity-mcp
```

### 3. 验证服务

```bash
# 检查容器状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

## MCP 客户端配置

在 Claude Code 的 `.mcp.json` 中配置：

```json
{
  "mcpServers": {
    "perplexity-http": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_TOKEN}"
      }
    }
  }
}
```

确保系统环境变量 `MCP_TOKEN` 与 Docker 容器中的一致。

## 环境变量说明

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `MCP_PORT` | 否 | `8000` | MCP 服务端口 |
| `MCP_TOKEN` | 是 | `sk-123456` | API 认证密钥 |
| `PPLX_NEXT_AUTH_CSRF_TOKEN` | 否 | - | Perplexity CSRF Token (高级功能需要) |
| `PPLX_SESSION_TOKEN` | 否 | - | Perplexity Session Token (高级功能需要) |

## 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 重新构建镜像
docker-compose build --no-cache

# 进入容器调试
docker exec -it perplexity-mcp /bin/bash
```

## 生产环境建议

1. **使用强密码**: 将 `MCP_TOKEN` 设置为复杂的随机字符串
2. **HTTPS**: 在生产环境中，建议使用 Nginx/Traefik 反向代理并配置 SSL
3. **监控**: 配合 Prometheus/Grafana 进行服务监控
4. **日志**: 配置日志持久化和轮转

### Nginx 反向代理示例

```nginx
server {
    listen 443 ssl;
    server_name mcp.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

