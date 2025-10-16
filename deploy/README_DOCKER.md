# Docker 部署指南

## 快速开始

### 1. 构建并启动服务

```bash
cd deploy
docker compose up -d
```

### 2. 查看日志

```bash
docker compose logs -f
```

### 3. 停止服务

```bash
docker compose down
```

## 数据持久化

### 目录结构

容器启动后会在 `deploy/` 目录下自动创建以下目录:

```
deploy/
├── data/              # 数据库文件存储目录
│   └── tokens.db      # SQLite 数据库文件
├── logs/              # 日志文件存储目录
└── docker-compose.yml
```

### 数据卷映射

- `./data:/app/data` - 数据库持久化存储
- `./logs:/app/logs` - 日志持久化存储

**重要**: 这些目录会自动创建,数据在容器重启或重建后仍然保留。

## 环境变量配置

在 `docker-compose.yml` 中可以配置以下环境变量:

```yaml
environment:
  # 管理后台密码
  - ADMIN_PASSWORD=admin123

  # API 认证密钥
  - AUTH_TOKEN=sk-your-api-key

  # 是否跳过 API Key 验证
  - SKIP_AUTH_TOKEN=false

  # 调试日志
  - DEBUG_LOGGING=true

  # 匿名模式
  - ANONYMOUS_MODE=true

  # Function Call 功能开关
  - TOOL_SUPPORT=true

  # 工具调用扫描限制(字符数)
  - SCAN_LIMIT=200000

  # 数据库路径(已配置持久化)
  - DB_PATH=/app/data/tokens.db
```

## 故障排查

### 问题: 数据库初始化失败 "unable to open database file"

**原因**:
1. 数据目录权限问题
2. 卷映射未正确配置
3. 容器内目录不存在

**解决方案**:
```bash
# 1. 停止容器
docker compose down

# 2. 确保宿主机目录存在并有正确权限
mkdir -p ./data ./logs
chmod 755 ./data ./logs

# 3. 重新构建并启动
docker compose up -d --build

# 4. 查看日志确认启动成功
docker compose logs -f
```

### 问题: 数据在容器重启后丢失

**检查**:
1. 确认 `docker-compose.yml` 中有正确的卷映射
2. 检查 `./data` 目录是否存在且包含 `tokens.db` 文件

```bash
# 查看数据目录
ls -la ./data/

# 应该看到 tokens.db 文件
```

### 问题: 权限被拒绝

如果遇到权限问题,可以检查文件权限:

```bash
# 查看目录权限
ls -ld ./data ./logs

# 修正权限
chmod -R 755 ./data ./logs
```

## 高级配置

### 自定义数据库位置

如果想使用不同的数据库路径,可以修改 `docker-compose.yml`:

```yaml
volumes:
  - /opt/1panel/docker/compose/k2think/data:/app/data  # 自定义路径

environment:
  - DB_PATH=/app/data/tokens.db
```

### 使用已有数据库

如果已经有 `tokens.db` 文件,将其放入 `deploy/data/` 目录即可:

```bash
# 复制已有数据库
cp /path/to/existing/tokens.db ./data/

# 设置权限
chmod 644 ./data/tokens.db

# 启动容器
docker compose up -d
```

## 健康检查

容器配置了健康检查,每30秒检查一次服务状态:

```bash
# 查看健康状态
docker compose ps

# 应该看到 STATUS 列显示 "healthy"
```

## 访问服务

- **API 端点**: http://localhost:8080
- **管理后台**: http://localhost:8080/admin
- **API 文档**: http://localhost:8080/docs
- **模型列表**: http://localhost:8080/v1/models

## 备份和恢复

### 备份数据

```bash
# 备份数据库
cp ./data/tokens.db ./data/tokens.db.backup.$(date +%Y%m%d_%H%M%S)

# 或创建完整备份
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz ./data ./logs
```

### 恢复数据

```bash
# 停止服务
docker compose down

# 恢复数据库
cp ./data/tokens.db.backup.20250116_120000 ./data/tokens.db

# 启动服务
docker compose up -d
```

## 更新应用

```bash
# 停止服务
docker compose down

# 拉取最新代码
git pull

# 重新构建并启动
docker compose up -d --build

# 数据会自动保留
```
