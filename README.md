# Z.AI OpenAI API 代理服务

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python: 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)
![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688.svg)
![Version: 1.2.0](https://img.shields.io/badge/version-1.2.0-brightgreen.svg)

轻量级 OpenAI API 兼容代理服务，通过 Claude Code Router 接入 Z.AI，支持 GLM-4.5 系列模型的完整功能。

## ✨ 核心特性

- 🔌 **完全兼容 OpenAI API** - 无缝集成现有应用
- 🤖 **Claude Code 支持** - 通过 Claude Code Router 接入 Claude Code (**CCR 工具请升级到 v1.0.47 以上**)
- 🚀 **高性能流式响应** - Server-Sent Events (SSE) 支持
- 🛠️ **增强工具调用** - 改进的 Function Call 实现
- 🧠 **思考模式支持** - 智能处理模型推理过程
- 🔍 **搜索模型集成** - GLM-4.5-Search 网络搜索能力
- 🐳 **Docker 部署** - 一键容器化部署
- 🛡️ **会话隔离** - 匿名模式保护隐私
- 🔧 **灵活配置** - 环境变量灵活配置
- 📊 **多模型映射** - 智能上游模型路由

## 🚀 快速开始

### 环境要求

- Python 3.8+
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

服务启动后访问：http://localhost:8080/docs

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
| `API_ENDPOINT`        | `https://chat.z.ai/api/chat/completions`  | 上游 API 地址          |
| `LISTEN_PORT`         | `8080`                                    | 服务监听端口           |
| `DEBUG_LOGGING`       | `true`                                    | 调试日志开关           |
| `THINKING_PROCESSING` | `think`                                   | 思考内容处理策略       |
| `ANONYMOUS_MODE`      | `true`                                    | 匿名模式开关           |
| `TOOL_SUPPORT`        | `true`                                    | Function Call 功能开关 |
| `SKIP_AUTH_TOKEN`     | `false`                                   | 跳过认证令牌验证       |
| `SCAN_LIMIT`          | `200000`                                  | 扫描限制               |
| `BACKUP_TOKEN`        | `eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...` | Z.ai 固定访问令牌      |

### 思考内容处理策略

- `think` - 转换为 `<thinking>` 标签（OpenAI 兼容）
- `strip` - 移除思考内容
- `raw` - 保留原始格式

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

### 方式 1: 通过 Z.ai 网站

1. 访问 [Z.ai 官网](https://chat.z.ai)
2. 注册账户并登录，进入 [Z.ai API Keys](https://z.ai/manage-apikey/apikey-list) 设置页面，在该页面设置 _**个人 API Token**_
3. 将 Token 放置在 `BACKUP_TOKEN` 环境变量中

### 方式 2: 浏览器开发者工具（临时方案）

1. 打开 [Z.ai 聊天界面](https://chat.z.ai)
2. 按 F12 打开开发者工具
3. 切换到 "Application" 或 "存储" 标签
4. 查看 Local Storage 中的认证 token
5. 复制 token 值设置为环境变量

> ⚠️ **注意**: 方式 2 获取的 token 可能有时效性，建议使用方式 1 获取长期有效的 API Token。  
> ❗ **重要提示**: 多模态模型需要**官方 Z.ai API 非匿名 Token**，匿名 token 不支持多媒体处理。

## 🛠️ 技术栈

| 组件            | 技术                                                                              | 版本    | 说明                                       |
| --------------- | --------------------------------------------------------------------------------- | ------- | ------------------------------------------ |
| **Web 框架**    | [FastAPI](https://fastapi.tiangolo.com/)                                          | 0.104.1 | 高性能异步 Web 框架，支持自动 API 文档生成 |
| **ASGI 服务器** | [Granian](https://github.com/emmett-framework/granian)                            | 2.5.2   | 基于 Rust 的高性能 ASGI 服务器，支持热重载 |
| **HTTP 客户端** | [Requests](https://requests.readthedocs.io/)                                      | 2.32.5  | 简洁易用的 HTTP 库，用于上游 API 调用      |
| **数据验证**    | [Pydantic](https://pydantic.dev/)                                                 | 2.11.7  | 类型安全的数据验证与序列化                 |
| **配置管理**    | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | 2.10.1  | 基于 Pydantic 的配置管理                   |

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
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # 配置管理
│   │   ├── openai.py          # OpenAI API 实现
│   │   └── response_handlers.py  # 响应处理器
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Pydantic 模型定义
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── helpers.py         # 辅助函数
│   │   ├── tools.py           # 增强工具调用处理
│   │   └── sse_parser.py      # SSE 流式解析器
│   └── __init__.py
├── tests/                     # 单元测试
├── deploy/                    # Docker 部署配置
├── main.py                    # FastAPI 应用入口
├── requirements.txt           # Python 依赖
├── .env.example              # 环境变量示例
└── README.md                  # 项目文档
```

## ⭐ Star History

If you like this project, please give it a star ⭐  
[![Star History Chart](https://www.star-history.com/#ZyphrZero/z.ai2api_python&Date)](https://www.star-history.com/#ZyphrZero/z.ai2api_python&Date)


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
