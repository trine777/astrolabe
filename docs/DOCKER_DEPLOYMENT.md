# 星图 Docker 部署指南

> **本文档面向 REST Adapter 部署** (即给 Matrix Go 等跨语言客户端用的形态)。
>
> 单进程内嵌 Astrolabe 请直接 lib import：`from xingtu import XingTuService`。
> 详见 [`POSITIONING.md`](POSITIONING.md) 的 4 路径决策树。

> 将星图部署为 Docker 容器，提供稳定的 REST + MCP 服务 (Adapter 形态)

## 快速开始

### 1. 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间

### 2. 一键部署

```bash
# 克隆或进入项目目录
cd xingtu

# 运行部署脚本
./deploy.sh deploy
```

部署脚本会自动：
1. 检查 Docker 环境
2. 创建 `.env` 配置文件（如果不存在）
3. 创建数据目录
4. 构建 Docker 镜像
5. 启动服务
6. 检查健康状态

### 3. 配置环境变量

首次部署时，脚本会提示编辑 `.env` 文件。主要配置项：

```bash
# 必填：OpenAI API Key（如果使用 OpenAI 嵌入）
OPENAI_API_KEY=sk-your-api-key-here

# 可选：数据存储路径
XINGTU_DATA_PATH=./data

# 可选：嵌入模型提供商
XINGTU_EMBEDDING_PROVIDER=openai  # 或 ollama, sentence-transformers
```

## 部署架构

### 服务组件

```
┌─────────────────────────────────────┐
│     Claude Desktop / AI Client      │
│                                     │
│  通过 MCP 协议连接                   │
└──────────────┬──────────────────────┘
               │ stdio
               ▼
┌─────────────────────────────────────┐
│      xingtu-mcp (Docker 容器)       │
│                                     │
│  ┌─────────────────────────────┐   │
│  │   XingTu MCP Server         │   │
│  │   - 意图处理                 │   │
│  │   - 差分计算                 │   │
│  │   - 行技执行                 │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │   LanceDB 存储              │   │
│  │   - 元数据                   │   │
│  │   - 向量索引                 │   │
│  │   - 事件流                   │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      持久化数据卷 (./data)           │
└─────────────────────────────────────┘
```

### 可选：使用 Ollama 本地模型

如果不想使用 OpenAI，可以使用本地 Ollama 服务：

```bash
# 修改 .env
XINGTU_EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434

# 启动时会自动启动 Ollama 容器
./deploy.sh deploy
```

## 管理命令

### 查看服务状态

```bash
./deploy.sh status
```

### 查看日志

```bash
./deploy.sh logs
```

### 重启服务

```bash
./deploy.sh restart
```

### 停止服务

```bash
./deploy.sh stop
```

### 清理所有数据（危险）

```bash
./deploy.sh clean
```

## 手动部署

如果不使用部署脚本，可以手动执行：

### 1. 创建配置文件

```bash
cp .env.example .env
# 编辑 .env，填入必要配置
```

### 2. 构建镜像

```bash
docker-compose build
```

### 3. 启动服务

```bash
# 仅启动星图
docker-compose up -d

# 同时启动 Ollama
docker-compose --profile ollama up -d
```

### 4. 查看日志

```bash
docker-compose logs -f xingtu-mcp
```

## 在 Claude Desktop 中配置

### 方式 1: Docker Exec 模式

编辑 Claude Desktop 配置文件：

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "xingtu": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "xingtu-mcp",
        "python",
        "-m",
        "xingtu_mcp.server"
      ]
    }
  }
}
```

### 方式 2: Docker Run 模式（推荐）

```json
{
  "mcpServers": {
    "xingtu": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-v",
        "xingtu-data:/data",
        "--env-file",
        "/path/to/xingtu/.env",
        "xingtu-mcp:latest"
      ]
    }
  }
}
```

## 数据持久化

### 数据目录结构

```
./data/
├── lancedb/              # LanceDB 数据库文件
│   ├── collections.lance
│   ├── documents.lance
│   ├── relations.lance
│   ├── events.lance
│   ├── agent_memories.lance
│   ├── universe_goals.lance
│   └── universe_deltas.lance
└── logs/                 # 日志文件（可选）
```

### 备份数据

```bash
# 停止服务
./deploy.sh stop

# 备份数据目录
tar -czf xingtu-backup-$(date +%Y%m%d).tar.gz ./data

# 重启服务
./deploy.sh start
```

### 恢复数据

```bash
# 停止服务
./deploy.sh stop

# 恢复数据
tar -xzf xingtu-backup-20240101.tar.gz

# 重启服务
./deploy.sh start
```

## 性能优化

### 资源限制

在 `docker-compose.yml` 中调整资源限制：

```yaml
deploy:
  resources:
    limits:
      cpus: '4'        # 增加 CPU 限制
      memory: 8G       # 增加内存限制
    reservations:
      cpus: '2'
      memory: 4G
```

#使用本地嵌入模型

使用 `sentence-transformers` 避免 API 调用：

```bash
# .env
XINGTU_EMBEDDING_PROVIDER=sentence-transformers
SENTENCE_TRANSFORMERS_MODEL=all-MiniLM-L6-v2
```

## 故障排查

### 容器无法启动

```bash
# 查看详细日志
docker-compose logs xingtu-mcp

# 检查配置
docker-compose config
```

### 健康检查失败

```bash
# 进入容器检查
docker exec -it xingtu-mcp bash

# 手动测试
python -c "from xingtu import XingTuService; s = XingTuService(); s.initialize()"
```

### 数据库损坏

```bash
# 停止服务
./deploy.sh stop

# 备份当前数据
mv ./data ./data.backup

# 重新初始化
./deploy.sh start
```

### OpenAI API 连接问题

```bash
# 检查 API Key
docker exec xingtu-mcp env | grep OPENAI

# 测试连接
docker exec xingtu-mcp python -c "
import openai
client = openai.OpenAI()
print(client.models.list())
"
```

## 监控和日志

### 查看实时日志

```bash
docker-compose logs -f --tail=100 xingtu-mcp
```

### 导出日志

```bash
docker-compose logs xingtu-mcp > xingtu-$(date +%Y%m%d).log
```

### 监控资源使用

```bash
docker stats xingtu-mcp
```

## 更新部署

### 更新代码

```bash
# 拉取最新代码
git pull

# 重新构建并重启
./deploy.sh build
./deploy.sh restart
```

### 更新依赖

```bash
# 强制重新构建（不使用缓存）
docker-compose build --no-cache

# 重启服务
./deploy.sh restart
```

## 安全建议

1. **保护 API Key**: 不要将 `.env` 文件提交到版本控制
2. **限制网络访问**: 使用 Docker 网络隔离
3. **定期备份**: 设置自动备份任务
4. **更新镜像**: 定期更新基础镜像和依赖
5. **监控日志**: 定期检查异常日志

## 生产环境部署

### 使用 Docker Swarm

```bash
# 初始化 Swarm
docker swarm init

# 部署服务栈
docker stack deploy -c docker-compose.yml xingtu
```

### 使用 Kubernetes

参考 `k8s/` 目录下的 Kubernetes 配置文件（待添加）。

## 常见问题

**Q: 如何更改数据存储路径？**

A: 修改 `.env` 中的 `XINGTU_DATA_PATH`，然后重启服务。

**Q: 可以同时运行多个实例吗？**

A: 可以，但需要使用不同的数据目录和容器名称。

**Q: 如何升级到新版本？**

A: 拉取最新代码，运行 `./deploy.sh build` 重新构建，然后 `./dy.sh restart`。

**Q: 数据会丢失吗？**

A: 不会，数据存储在持久化卷中，容器重启不影响数据。

## 支持

如有问题，请查看：
- 项目文档: `docs/`
- 问题追踪: GitHub Issues
- 日志文件: `./data/logs/`
