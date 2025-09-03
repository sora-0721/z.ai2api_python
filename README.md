# Z.AI OpenAI & Anthropic API 代理服务

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python: 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)
![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688.svg)

为 Z.AI 提供 OpenAI 和 Anthropic API 兼容接口的轻量级代理服务，支持 GLM-4.5 系列模型的完整功能。

## ✨ 核心特性

- 🔌 **完全兼容 OpenAI API** - 无缝集成现有应用
- 🎭 **兼容 Anthropic API** - 支持 Claude CLI 客户端直接接入
- 🚀 **高性能流式响应** - Server-Sent Events (SSE) 支持
- 🛠️ **Function Call 支持** - 完整的工具调用功能
- 🧠 **思考模式支持** - 智能处理模型推理过程
- 🔍 **搜索模型集成** - GLM-4.5-Search 网络搜索能力
- 🐳 **Docker 部署** - 一键容器化部署
- 🛡️ **会话隔离** - 匿名模式保护隐私
- 🔧 **高度可配置** - 环境变量灵活配置

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
pip install -r requirement.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
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

#### Anthropic API 客户端

```python
import anthropic

# 初始化客户端
client = anthropic.Anthropic(
    base_url="http://localhost:8080/v1",
    api_key="your-anthropic-token"  # 替换为你的 ANTHROPIC_API_KEY
)

# 普通对话
message = client.messages.create(
    model="GLM-4.5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "你好，介绍一下 Python"}
    ]
)

print(message.content[0].text)
```

### Docker 部署

```bash
cd deploy
docker-compose up -d
```

## 📖 详细指南

### 支持的模型

| 模型 | 描述 | 特性 |
|------|------|------|
| `GLM-4.5` | 标准模型 | 通用对话，平衡性能 |
| `GLM-4.5-Thinking` | 思考模型 | 显示推理过程，透明度高 |
| `GLM-4.5-Search` | 搜索模型 | 实时网络搜索，信息更新 |

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

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AUTH_TOKEN` | `sk-your-api-key` | 客户端认证密钥（OpenAI 和 Anthropic 共用） |
| `API_ENDPOINT` | `https://chat.z.ai/api/chat/completions` | 上游 API 地址 |
| `LISTEN_PORT` | `8080` | 服务监听端口 |
| `DEBUG_LOGGING` | `true` | 调试日志开关 |
| `THINKING_PROCESSING` | `think` | 思考内容处理策略 |
| `ANONYMOUS_MODE` | `true` | 匿名模式开关 |
| `TOOL_SUPPORT` | `true` | Function Call 功能开关 |

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

### 2. 多模型对比测试

```python
models = ["GLM-4.5", "GLM-4.5-Thinking", "GLM-4.5-Search"]

for model in models:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "什么是机器学习？"}]
    )
    print(f"\n=== {model} ===")
    print(response.choices[0].message.content)
```

### 3. 工具调用集成

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
A: `AUTH_TOKEN` 为自己自定义的api key，在环境变量中配置，需要保证客户端与服务端一致。

**Q: ANTHROPIC_API_KEY 如何配置？**
A: 默认使用 `AUTH_TOKEN` 的值，两个 API 使用相同的认证密钥。如需分开配置，可单独设置 `ANTHROPIC_API_KEY` 环境变量。

**Q: 匿名模式是什么？**
A: 匿名模式使用临时 token，避免对话历史共享，保护隐私。

**Q: Function Call 如何工作？**
A: 通过智能提示注入实现，将工具定义转换为系统提示。

**Q: 支持哪些 OpenAI 功能？**
A: 支持聊天完成、模型列表、流式响应、工具调用等核心功能。

**Q: 支持 Anthropic API 的哪些功能？**
A: 支持 messages 创建、流式响应、系统提示等核心功能。

**Q: 如何自定义配置？**
A: 通过环境变量配置，推荐使用 `.env` 文件。

## 🏗️ 技术架构

```
┌──────────────┐     ┌─────────────┐     ┌─────────────┐
│   OpenAI     │     │             │     │             │
│  Client      │────▶│   Proxy     │────▶│    Z.AI     │
└──────────────┘     │   Server    │     │    API      │
┌──────────────┐     │             │     │             │
│  Anthropic    │────▶│             │     │             │
│  Client      │     │             │     │             │
└──────────────┘     └─────────────┘     └─────────────┘
```

- **FastAPI** - 高性能 Web 框架
- **Pydantic** - 数据验证和序列化
- **Uvicorn** - ASGI 服务器
- **Requests** - HTTP 客户端

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