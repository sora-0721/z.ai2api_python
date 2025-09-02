# Docker部署指南

## 文件说明

- `Dockerfile.python` - 基础版本的Dockerfile
- `Dockerfile.python.optimized` - 多阶段构建，镜像更小
- `docker-compose.yml` - Docker Compose配置文件
- `.dockerignore` - Docker构建时忽略的文件
- `test-page/` - 简单的Web测试界面

## 快速开始

### 1. 构建并运行（使用docker-compose）

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 2. 仅使用Docker

```bash
# 构建镜像
docker build -f Dockerfile.python.optimized -t openai-proxy-python .

# 运行容器
docker run -d \
  --name openai-proxy \
  -p 8080:8080 \
  openai-proxy-python
```

### 3. 带测试界面的完整部署

```bash
# 启动服务和测试界面
docker-compose --profile test-ui up -d

# 访问测试界面
# 打开浏览器访问 http://localhost:8081
```

## 环境变量配置

可以通过环境变量覆盖默认配置：

```bash
# 在docker-compose.yml中添加
environment:
  - DEBUG_MODE=false
  - PORT=8080
  - DEFAULT_KEY=your-api-key
  - UPSTREAM_TOKEN=your-upstream-token
```

或者使用.env文件：

```bash
# 创建.env文件
echo "DEBUG_MODE=false" > .env
echo "DEFAULT_KEY=sk-your-custom-key" >> .env

# 启动时自动加载
docker-compose up -d
```

## 生产环境建议

1. **使用优化版Dockerfile**
   ```bash
   docker build -f Dockerfile.python.optimized -t openai-proxy:latest .
   ```

2. **配置HTTPS**
   建议在反向代理（如Nginx）中配置SSL证书

3. **使用Docker Secrets管理敏感信息**
   ```yaml
   secrets:
     api_key:
       file: ./secrets/api_key.txt
     upstream_token:
       file: ./secrets/upstream_token.txt
   ```

4. **设置资源限制**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '0.5'
         memory: 512M
   ```

## 常用命令

```bash
# 查看容器状态
docker ps

# 查看日志
docker logs openai-proxy

# 进入容器
docker exec -it openai-proxy bash

# 重新构建
docker-compose build

# 完全清理
docker-compose down -v --rmi all
```

## 故障排除

1. **端口冲突**
   - 修改docker-compose.yml中的端口映射
   - 或者停止占用8080端口的程序

2. **镜像构建失败**
   - 确保Docker版本 >= 19.03
   - 检查网络连接

3. **容器启动失败**
   - 查看日志：`docker logs openai-proxy`
   - 检查配置文件语法

4. **API请求失败**
   - 确认容器正在运行
   - 检查防火墙设置
   - 验证API密钥配置

## 测试API

容器启动后，可以测试API：

```bash
# 测试模型列表
curl -X GET http://localhost:8080/v1/models \
  -H "Authorization: Bearer sk-tbkFoKzk9a531YyUNNF5"

# 测试聊天接口
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-tbkFoKzk9a531YyUNNF5" \
  -d '{"model": "GLM-4.5", "messages": [{"role": "user", "content": "Hello"}]}'
```