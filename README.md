
## 项目简介

这是一个为 Z.ai 提供 OpenAI API 兼容接口的 Python 代理服务，允许开发者通过标准的 OpenAI API 格式访问 Z.ai 的 GLM-4.5 模型。

## 主要特性

- **OpenAI API 兼容**：完整支持 `/v1/chat/completions` 和 `/v1/models` 端点
- **流式响应支持**：完整实现 Server-Sent Events (SSE) 流式传输
- **思考内容处理**：提供多种策略处理模型的思考过程（`<details>` 标签）
- **匿名会话支持**：可选使用匿名 token 避免共享对话历史
- **多种模型支持**：支持 GLM-4.5 基础版、思考版和搜索版
- **调试模式**：详细的请求/响应日志记录，便于开发调试
- **CORS 支持**：内置跨域资源共享支持
- **Function Call 支持**：完整支持 OpenAI 格式的工具调用功能，通过智能提示注入实现，支持流式响应时的工具调用缓冲机制

## 使用场景

- 将 Z.ai 集成到支持 OpenAI API 的应用程序中
- 开发需要同时使用多个 AI 服务的应用
- 测试和评估 GLM-4.5 模型的能力
- 需要流式响应或思考内容的 AI 应用开发

## 快速开始

### 使用 uv (推荐)

1. 安装 uv：
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # Windows (PowerShell)
   powershell -c "irm https://astral.sh/uv/install.sh | iex"
   ```

2. 同步依赖：
   ```bash
   uv sync
   ```

3. 运行服务：
   ```bash
   uv run python main.py
   ```

### 使用 pip

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 配置服务（可选）：
   编辑 `main.py` 中的 `ServerConfig` 类以调整服务行为：
   - `AUTH_TOKEN`: 客户端 API 密钥
   - `API_ENDPOINT`: Z.ai 上游 API 地址
   - `BACKUP_TOKEN`: 固定认证 token（匿名模式失败时使用）
   - `LISTEN_PORT`: 服务监听端口
   - `DEBUG_LOGGING`: 调试模式开关
   - `THINKING_PROCESSING`: 思考内容处理策略
   - `ANONYMOUS_MODE`: 匿名模式开关
   - `TOOL_SUPPORT`: Function Call 功能开关

3. 运行服务：
   ```bash
   python main.py
   ```

   服务启动后，可以访问 http://localhost:8080/docs 查看自动生成的 Swagger API 文档

4. 使用 OpenAI 客户端库调用：
   ```python
   import openai

   # 初始化客户端
   client = openai.OpenAI(
       base_url="http://localhost:8080/v1",
       api_key="sk-tbkFoKzk9a531YyUNNF5"  # 使用配置的 AUTH_TOKEN
   )

   # 流式调用示例
   response = client.chat.completions.create(
       model="GLM-4.5",  # 可选: "GLM-4.5-Thinking", "GLM-4.5-Search"
       messages=[{"role": "user", "content": "你好"}],
       stream=True
   )

   for chunk in response:
       content = chunk.choices[0].delta.content
       reasoning = chunk.choices[0].delta.reasoning_content
       if content:
           print(content, end="")
       if reasoning:
           print(f"\n[思考] {reasoning}\n")
   ```

   注意：请将 `api_key` 替换为您在 `main.py` 中配置的 `AUTH_TOKEN` 值。

### Function Call 使用示例

本项目完整支持 OpenAI 格式的工具调用功能，包括流式和非流式响应。实现原理是将 OpenAI 的工具定义转换为特殊的系统提示，让模型理解并生成符合格式的工具调用。

#### 基本工具调用

```python
import openai

# 初始化客户端
client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="sk-tbkFoKzk9a531YyUNNF5"
)

# 定义天气查询工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位",
                        "default": "celsius"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

# 使用工具调用
response = client.chat.completions.create(
    model="GLM-4.5",
    messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
    tools=tools,
    tool_choice="auto"
)

message = response.choices[0].message
if message.tool_calls:
    print("模型请求调用工具:")
    for tool_call in message.tool_calls:
        print(f"工具名称: {tool_call.function.name}")
        print(f"参数: {tool_call.function.arguments}")
        print(f"调用ID: {tool_call.id}")
else:
    print(f"回复: {message.content}")
```

#### 流式工具调用

```python
# 流式工具调用示例
response = client.chat.completions.create(
    model="GLM-4.5",
    messages=[{"role": "user", "content": "帮我计算 2 的 10 次方"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "执行数学计算",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式"
                    }
                },
                "required": ["expression"]
            }
        }
    }],
    stream=True
)

# 注意：工具调用模式下，流式响应会缓冲所有内容，
# 在最后一次性返回工具调用信息
tool_calls = None
content = ""

for chunk in response:
    delta = chunk.choices[0].delta
    if delta.tool_calls:
        tool_calls = delta.tool_calls
    if delta.content:
        content += delta.content

if tool_calls:
    print("工具调用:")
    for tool_call in tool_calls:
        print(f"函数: {tool_call.function.name}")
        print(f"参数: {tool_call.function.arguments}")
else:
    print("回复:", content)
```

#### 强制使用特定工具

```python
# 强制使用特定工具
response = client.chat.completions.create(
    model="GLM-4.5",
    messages=[{"role": "user", "content": "今天是什么日子"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "获取当前日期和时间",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }],
    tool_choice={"type": "function", "function": {"name": "get_current_date"}}
)

message = response.choices[0].message
print(f"完成原因: {response.choices[0].finish_reason}")  # tool_calls
if message.tool_calls:
    print("工具调用结果:", message.tool_calls[0].function.arguments)
```

#### 多工具协作

```python
# 定义多个工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索网络信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_text",
            "description": "总结文本内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要总结的文本"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "最大长度",
                        "default": 100
                    }
                },
                "required": ["text"]
            }
        }
    }
]

# 使用多工具
response = client.chat.completions.create(
    model="GLM-4.5",
    messages=[{"role": "user", "content": "搜索一下最新的 AI 新闻并总结"}],
    tools=tools,
    tool_choice="auto"
)

message = response.choices[0].message
if message.tool_calls:
    for tool_call in message.tool_calls:
        print(f"调用工具: {tool_call.function.name}")
        # 在实际应用中，这里需要执行相应的函数
        # 并将结果通过工具消息返回给模型
```

### 运行 Function Call 演示

项目包含一个完整的 Function Call 演示脚本：

```bash
python function_call_demo.py
```

该脚本将演示：
1. 基本的工具调用
2. 数学计算工具
3. 强制使用特定工具
4. 流式工具调用响应

### 使用 Docker Compose

1. 启动服务：
   ```bash
   # 在 deploy 目录下运行
   cd deploy
   docker-compose up -d
   ```

![744X487/QQ20250903-145750.png](https://tc.z.wiki/autoupload/f/KTO6-pUlsq3zQ-YJ9ppdgtiO_OyvX7mIgxFBfDMDErs/20250903/DkjD/744X487/QQ20250903-145750.png)

2. 停止服务：
   ```bash
   docker-compose down
   ```

3. 查看日志：
   ```bash
   docker-compose logs -f
   ```

4. 重新构建并启动：
   ```bash
   docker-compose up -d --build
   ```

注意：如需修改配置参数（如 API 密钥、端口等），请直接编辑 `main.py` 文件中的 `ServerConfig` 类。

![1830X875/微信图片_20250903145327_21624_1.png](https://tc-new.z.wiki/autoupload/f/KTO6-pUlsq3zQ-YJ9ppdgtiO_OyvX7mIgxFBfDMDErs/20250903/AF2F/1830X875/%E5%BE%AE%E4%BF%A1%E5%9B%BE%E7%89%87_20250903145327_21624_1.png)


## 配置选项

| 配置项 | 描述 | 默认值 |
|--------|------|--------|
| `API_ENDPOINT` | Z.ai 的上游 API 地址 | `https://chat.z.ai/api/chat/completions` |
| `AUTH_TOKEN` | 下游客户端鉴权 key | `sk-tbkFoKzk9a531YyUNNF5` |
| `BACKUP_TOKEN` | 上游 API 的 token (匿名模式失败时使用) | JWT token |
| `PRIMARY_MODEL` | 默认模型名称 | `GLM-4.5` |
| `THINKING_MODEL` | 思考模型名称 | `GLM-4.5-Thinking` |
| `SEARCH_MODEL` | 搜索模型名称 | `GLM-4.5-Search` |
| `LISTEN_PORT` | 服务监听端口 | `8080` |
| `DEBUG_LOGGING` | 调试模式开关 | `true` |
| `THINKING_PROCESSING` | 思考内容处理策略 | `think` (可选: `strip`, `raw`) |
| `ANONYMOUS_MODE` | 是否使用匿名 token | `true` |
| `TOOL_SUPPORT` | 是否启用 Function Call 功能 | `true` |

### 思考内容处理策略说明

- **think**: 将 `<details>` 标签转换为 `<thinking>` 标签，适合 OpenAI 兼容格式
- **strip**: 完全移除 `<details>` 标签及其内容
- **raw**: 保留原始格式，不做任何处理

## 架构说明

本项目采用以下技术栈：

- **FastAPI**: 现代、快速的 Web 框架，提供自动 API 文档生成
- **Pydantic**: 数据验证和序列化，确保 API 兼容性
- **uvicorn**: ASGI 服务器，提供高性能服务

项目通过异步编程模型实现高效的并发处理，支持流式和非流式两种响应模式。

## 贡献指南

欢迎提交 Issue 和 Pull Request！请确保：
1. 遵循 PEP 8 规范
2. 提交前运行测试（如果有）
3. 更新相关文档

## 许可证

MIT LICENSE

## 免责声明

本项目与 Z.ai 官方无关，使用前请确保遵守 Z.ai 的服务条款。请勿将此服务用于商业用途或违反 Z.ai 使用条款的场景。
