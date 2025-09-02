
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
- **异步处理**：基于 FastAPI 和 httpx 的高性能异步架构

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
   编辑 `main.py` 中的以下常量以调整服务行为：
   - `DEFAULT_KEY`: 客户端 API 密钥
   - `UPSTREAM_URL`: Z.ai 上游 API 地址
   - `UPSTREAM_TOKEN`: 固定认证 token（匿名模式失败时使用）
   - `PORT`: 服务监听端口
   - `DEBUG_MODE`: 调试模式开关
   - `THINK_TAGS_MODE`: 思考内容处理策略
   - `ANON_TOKEN_ENABLED`: 匿名 token 开关

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
       api_key="sk-tbkFoKzk9a531YyUNNF5"  # 使用配置的 DEFAULT_KEY
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

   注意：请将 `api_key` 替换为您在 `main.py` 中配置的 `DEFAULT_KEY` 值。

## 配置选项

| 配置项 | 描述 | 默认值 |
|--------|------|--------|
| `UPSTREAM_URL` | Z.ai 的上游 API 地址 | `https://chat.z.ai/api/chat/completions` |
| `DEFAULT_KEY` | 下游客户端鉴权 key | `sk-tbkFoKzk9a531YyUNNF5` |
| `UPSTREAM_TOKEN` | 上游 API 的 token (匿名模式失败时使用) | JWT token |
| `DEFAULT_MODEL_NAME` | 默认模型名称 | `GLM-4.5` |
| `THINKING_MODEL_NAME` | 思考模型名称 | `GLM-4.5-Thinking` |
| `SEARCH_MODEL_NAME` | 搜索模型名称 | `GLM-4.5-Search` |
| `PORT` | 服务监听端口 | `8080` |
| `DEBUG_MODE` | 调试模式开关 | `true` |
| `THINK_TAGS_MODE` | 思考内容处理策略 | `think` (可选: `strip`, `raw`) |
| `ANON_TOKEN_ENABLED` | 是否使用匿名 token | `true` |

### 思考内容处理策略说明

- **think**: 将 `<details>` 标签转换为 `<thinking>` 标签，适合 OpenAI 兼容格式
- **strip**: 完全移除 `<details>` 标签及其内容
- **raw**: 保留原始格式，不做任何处理

## 架构说明

本项目采用以下技术栈：

- **FastAPI**: 现代、快速的 Web 框架，提供自动 API 文档生成
- **httpx**: 异步 HTTP 客户端，用于上游 API 调用
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