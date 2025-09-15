# Z.AI OpenAI API 代理服务

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python: 3.9-3.12](https://img.shields.io/badge/python-3.9--3.12-green.svg)
![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688.svg)
![Version: 0.1.0](https://img.shields.io/badge/version-0.1.0-brightgreen.svg)

> 🎯 **项目愿景**：提供完全兼容 OpenAI API 的 Z.AI 代理服务，让用户无需修改现有代码即可接入 GLM-4.5 系列模型。

轻量级、高性能的 OpenAI API 兼容代理服务，通过 Claude Code Router 接入 Z.AI，支持 GLM-4.5 系列模型的完整功能。

## ✨ 核心特性

- 🔌 **完全兼容 OpenAI API** - 无缝集成现有应用
- 🤖 **Claude Code 支持** - 通过 Claude Code Router 接入 Claude Code (**CCR 工具请升级到 v1.0.47 以上**)
- 🚀 **高性能流式响应** - Server-Sent Events (SSE) 支持
- 🛠️ **增强工具调用** - 改进的 Function Call 实现，支持复杂工具链
- 🧠 **思考模式支持** - 智能处理模型推理过程
- 🔍 **搜索模型集成** - GLM-4.5-Search 网络搜索能力
- 🐳 **Docker 部署** - 一键容器化部署
- 🛡️ **会话隔离** - 匿名模式保护隐私
- 🔧 **灵活配置** - 环境变量灵活配置
- 📊 **多模型映射** - 智能上游模型路由
- 🔄 **Token 池管理** - 自动轮询、容错恢复、动态更新
- 🛡️ **错误处理** - 完善的异常捕获和重试机制
- 🔒 **服务唯一性** - 基于进程名称(pname)的服务唯一性验证，防止重复启动

## 🚀 快速开始

### 环境要求

- Python 3.9-3.12
- pip 或 uv (推荐)

### 安装运行

```bash
# 克隆项目
git clone https://github.com/ZyphrZero/z.ai2api_python.git
cd z.ai2api_python

# 使用 uv (推荐)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
uv run python main.py

# 或使用 pip (推荐使用清华源)
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python main.py
```

>  服务启动后访问接口文档：http://localhost:8080/docs  
> 💡 **提示**：默认端口为 8080，可通过环境变量 `LISTEN_PORT` 修改  
> ⚠️ **注意**：请勿将 `AUTH_TOKEN` 泄露给其他人，请使用 `AUTH_TOKENS` 配置多个认证令牌  

### 基础使用

#### OpenAI API 客户端

```python
import openai

# 初始化客户端
client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="your-auth-token"  # 替换为你的 AUTH_TOKEN
)

# 普通对话
response = client.chat.completions.create(
    model="GLM-4.5",
    messages=[{"role": "user", "content": "你好，介绍一下 Python"}],
    stream=False
)

print(response.choices[0].message.content)
```

### Docker 部署

```bash
cd deploy
docker-compose up -d
```

## 📖 详细指南

### 支持的模型

| 模型               | 上游 ID       | 描述        | 特性                   |
| ------------------ | ------------- | ----------- | ---------------------- |
| `GLM-4.5`          | 0727-360B-API | 标准模型    | 通用对话，平衡性能     |
| `GLM-4.5-Thinking` | 0727-360B-API | 思考模型    | 显示推理过程，透明度高 |
| `GLM-4.5-Search`   | 0727-360B-API | 搜索模型    | 实时网络搜索，信息更新 |
| `GLM-4.5-Air`      | 0727-106B-API | 轻量模型    | 快速响应，高效推理     |
| `GLM-4.5V`         | glm-4.5v      | ❌ 暂不支持 |                        |

### Function Call 功能

```python
# 定义工具
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "获取天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"}
            },
            "required": ["city"]
        }
    }
}]

# 使用工具
response = client.chat.completions.create(
    model="GLM-4.5",
    messages=[{"role": "user", "content": "北京天气怎么样？"}],
    tools=tools,
    tool_choice="auto"
)
```

### 流式响应

```python
response = client.chat.completions.create(
    model="GLM-4.5-Thinking",
    messages=[{"role": "user", "content": "解释量子计算"}],
    stream=True
)

for chunk in response:
    content = chunk.choices[0].delta.content
    reasoning = chunk.choices[0].delta.reasoning_content

    if content:
        print(content, end="")
    if reasoning:
        print(f"\n🤔 思考: {reasoning}\n")
```

## ⚙️ 配置说明

### 环境变量配置

| 变量名                | 默认值                                    | 说明                   |
| --------------------- | ----------------------------------------- | ---------------------- |
| `AUTH_TOKEN`          | `sk-your-api-key`                         | 客户端认证密钥         |
| `LISTEN_PORT`         | `8080`                                    | 服务监听端口           |
| `DEBUG_LOGGING`       | `true`                                    | 调试日志开关           |
| `ANONYMOUS_MODE`      | `true`                                    | 匿名用户模式开关           |
| `TOOL_SUPPORT`        | `true`                                    | Function Call 功能开关 |
| `SKIP_AUTH_TOKEN`     | `false`                                   | 跳过认证令牌验证       |
| `SCAN_LIMIT`          | `200000`                                  | 扫描限制               |
| `AUTH_TOKENS_FILE`  | `tokens.txt`                              | 认证token文件路径 |

> 💡 详细配置请查看 `.env.example` 文件  

## 🔄 Token池机制

### 功能特性

- **负载均衡**：轮询使用多个auth token，分散请求负载
- **自动容错**：token失败时自动切换到下一个可用token
- **健康监控**：基于Z.AI API的role字段精确验证token类型
- **自动恢复**：失败token在超时后自动重新尝试
- **动态管理**：支持运行时更新token池
- **智能去重**：自动检测和去除重复token
- **类型验证**：只接受认证用户token (role: "user")，拒绝匿名token (role: "guest")

### Token配置方式

创建 `tokens.txt` 文件，支持多种格式的混合使用：
1. 每行一个token（换行分隔）
2. 逗号分隔的token
3. 混合格式（同时支持换行和逗号分隔）

## 监控API

```bash
# 查看token池状态
curl http://localhost:8080/v1/token-pool/status

# 手动健康检查
curl -X POST http://localhost:8080/v1/token-pool/health-check

# 动态更新token池
curl -X POST http://localhost:8080/v1/token-pool/update \
  -H "Content-Type: application/json" \
  -d '["new_token1", "new_token2"]'
```

详细文档请参考：[Token池功能说明](TOKEN_POOL_README.md)

## 🎯 使用场景

### 1. AI 应用开发

```python
# 集成到现有应用
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="your-token"
)

# 智能客服
def chat_with_ai(message):
    response = client.chat.completions.create(
        model="GLM-4.5",
        messages=[{"role": "user", "content": message}]
    )
    return response.choices[0].message.content
```

### 2. 工具调用集成

```python
# 结合外部 API
def call_external_api(tool_name, arguments):
    # 执行实际工具调用
    return result

# 处理工具调用
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        result = call_external_api(
            tool_call.function.name,
            json.loads(tool_call.function.arguments)
        )
        # 将结果返回给模型继续对话
```

## ❓ 常见问题

**Q: 如何获取 AUTH_TOKEN？**
A: `AUTH_TOKEN` 为自己自定义的 api key，在环境变量中配置，需要保证客户端与服务端一致。

**Q: 遇到 "Illegal header value b'Bearer '" 错误怎么办？**
A: 这通常是因为 Token 获取失败导致的。请检查：
- 匿名模式是否正确配置（`ANONYMOUS_MODE=true`）
- Token 文件是否存在且格式正确（`tokens.txt`）
- 网络连接是否正常，能否访问 Z.AI API

**Q: 启动时提示"服务已在运行"怎么办？**
A: 这是服务唯一性验证功能，防止重复启动。解决方法：
- 检查是否已有服务实例在运行：`ps aux | grep z-ai2api-server`
- 停止现有实例后再启动新的
- 如果确认没有实例运行，删除 PID 文件：`rm z-ai2api-server.pid`
- 可通过环境变量 `SERVICE_NAME` 自定义服务名称避免冲突

**Q: 如何通过 Claude Code 使用本服务？**

A: 创建 [zai.js](https://gist.githubusercontent.com/musistudio/b35402d6f9c95c64269c7666b8405348/raw/f108d66fa050f308387938f149a2b14a295d29e9/gistfile1.txt) 这个 ccr 插件放在`./.claude-code-router/plugins`目录下，配置 `./.claude-code-router/config.json` 指向本服务地址，使用 `AUTH_TOKEN` 进行认证。

示例配置：

```json
{
  "LOG": false,
  "LOG_LEVEL": "debug",
  "CLAUDE_PATH": "",
  "HOST": "127.0.0.1",
  "PORT": 3456,
  "APIKEY": "",
  "API_TIMEOUT_MS": "600000",
  "PROXY_URL": "",
  "transformers": [
    {
      "name": "zai",
      "path": "C:\\Users\\Administrator\\.claude-code-router\\plugins\\zai.js",
      "options": {}
    }
  ],
  "Providers": [
    {
      "name": "GLM",
      "api_base_url": "http://127.0.0.1:8080/v1/chat/completions",
      "api_key": "sk-your-api-key",
      "models": ["GLM-4.5", "GLM-4.5-Air"],
      "transformers": {
        "use": ["zai"]
      }
    }
  ],
  "StatusLine": {
    "enabled": false,
    "currentStyle": "default",
    "default": {
      "modules": []
    },
    "powerline": {
      "modules": []
    }
  },
  "Router": {
    "default": "GLM,GLM-4.5",
    "background": "GLM,GLM-4.5",
    "think": "GLM,GLM-4.5",
    "longContext": "GLM,GLM-4.5",
    "longContextThreshold": 60000,
    "webSearch": "GLM,GLM-4.5",
    "image": "GLM,GLM-4.5"
  },
  "CUSTOM_ROUTER_PATH": ""
}
```

**Q: 匿名模式是什么？**  
A: 匿名模式使用临时 token，避免对话历史共享，保护隐私。

**Q: Function Call 如何工作？**  
A: 通过智能提示注入实现，将工具定义转换为系统提示。

**Q: 支持哪些 OpenAI 功能？**  
A: 支持聊天完成、模型列表、流式响应、工具调用等核心功能。

**Q: Function Call 如何优化？**  
A: 改进了工具调用的请求响应结构，支持更复杂的工具链调用和并行执行。

**Q: 如何选择合适的模型？**  
A:

- **GLM-4.5**: 通用场景，性能和效果平衡
- **GLM-4.5-Thinking**: 需要了解推理过程的场景
- **GLM-4.5-Search**: 需要实时信息的场景
- **GLM-4.5-Air**: 高并发、低延迟要求的场景

**Q: 如何自定义配置？**  
A: 通过环境变量配置，推荐使用 `.env` 文件。

## 🔑 获取 Z.ai API Token

要使用完整的多模态功能，需要获取正式的 Z.ai API Token：

1. 打开 [Z.ai 聊天界面](https://chat.z.ai)
2. 按 F12 打开开发者工具
3. 切换到 "Application" 或 "存储" 标签
4. 查看 Local Storage 中的认证 token
5. 复制 token 值设置为环境变量

> ❗ **重要提示**: 获取的 token 可能有时效性，多模态模型需要**官方 Z.ai API 非匿名 Token**，匿名 token 不支持多媒体处理  

## 🛠️ 技术栈

| 组件            | 技术                                                                              | 版本    | 说明                                       |
| --------------- | --------------------------------------------------------------------------------- | ------- | ------------------------------------------ |
| **Web 框架**    | [FastAPI](https://fastapi.tiangolo.com/)                                          | 0.116.1 | 高性能异步 Web 框架，支持自动 API 文档生成 |
| **ASGI 服务器** | [Granian](https://github.com/emmett-framework/granian)                            | 2.5.2   | 基于 Rust 的高性能 ASGI 服务器，支持热重载 |
| **HTTP 客户端** | [HTTPX](https://www.python-httpx.org/) / [Requests](https://requests.readthedocs.io/) | 0.27.0 / 2.32.5 | 异步/同步 HTTP 库，用于上游 API 调用      |
| **数据验证**    | [Pydantic](https://pydantic.dev/)                                                 | 2.11.7  | 类型安全的数据验证与序列化                 |
| **配置管理**    | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | 2.10.1  | 基于 Pydantic 的配置管理                   |
| **日志系统**    | [Loguru](https://loguru.readthedocs.io/)                                          | 0.7.3   | 高性能结构化日志库                         |
| **用户代理**    | [Fake UserAgent](https://pypi.org/project/fake-useragent/)                        | 2.2.0   | 动态用户代理生成                           |

## 🏗️ 技术架构

```
┌──────────────┐      ┌─────────────────────────┐      ┌─────────────────┐
│   OpenAI     │      │                         │      │                 │
│  Client      │────▶│    FastAPI Server       │────▶│   Z.AI API      │
└──────────────┘      │                         │      │                 │
┌──────────────┐      │ ┌─────────────────────┐ │      │ ┌─────────────┐ │
│ Claude Code  │      │ │ /v1/chat/completions│ │      │ │0727-360B-API│ │
│   Router     │────▶│ └─────────────────────┘ │      │ └─────────────┘ │
└──────────────┘      │ ┌─────────────────────┐ │      │ ┌─────────────┐ │
                      │ │    /v1/models       │ │────▶│ │0727-106B-API│ │
                      │ └─────────────────────┘ │      │ └─────────────┘ │
                      │ ┌─────────────────────┐ │      │                 │
                      │ │  Enhanced Tools     │ │      └─────────────────┘
                      │ └─────────────────────┘ │
                      └─────────────────────────┘
                           OpenAI Compatible API
```

### 项目结构

```
z.ai2api_python/
├── app/                          # 主应用模块
│   ├── core/                     # 核心模块
│   │   ├── config.py            # 配置管理（Pydantic Settings）
│   │   ├── openai.py            # OpenAI API 兼容层
│   │   └── zai_transformer.py   # Z.AI 请求/响应转换器
│   ├── models/                   # 数据模型
│   │   └── schemas.py           # Pydantic 数据模型
│   └── utils/                    # 工具模块
│       ├── logger.py            # Loguru 日志系统
│       ├── reload_config.py     # 热重载配置
│       ├── sse_tool_handler.py  # SSE 工具调用处理器
│       └── token_pool.py        # Token 池管理
├── tests/                        # 测试文件
├── deploy/                       # 部署配置
│   ├── Dockerfile               # Docker 镜像构建
│   └── docker-compose.yml       # 容器编排
├── main.py                       # FastAPI 应用入口
├── requirements.txt              # 依赖清单
├── pyproject.toml               # 项目配置
├── tokens.txt.example           # Token 配置文件
└── .env.example                 # 环境变量示例
```

## ⭐ Star History

If you like this project, please give it a star ⭐  

[![Star History Chart](https://api.star-history.com/svg?repos=ZyphrZero/z.ai2api_python&type=Date)](https://star-history.com/#ZyphrZero/z.ai2api_python&Date)


## 🤝 贡献指南

我们欢迎所有形式的贡献！
请确保代码符合 PEP 8 规范，并更新相关文档。

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## ⚠️ 免责声明

- 本项目与 Z.AI 官方无关
- 使用前请确保遵守 Z.AI 服务条款
- 请勿用于商业用途或违反使用条款的场景
- 项目仅供学习和研究使用

---

<div align="center">
Made with ❤️ by the community
</div>
