# -*- coding: utf-8 -*-

import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Generator
from urllib.parse import urljoin

import requests
from fastapi import FastAPI, Request, Response, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field


# 配置常量
UPSTREAM_URL = "https://chat.z.ai/api/chat/completions"
DEFAULT_KEY = "sk-tbkFoKzk9a531YyUNNF5"
UPSTREAM_TOKEN = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjMxNmJjYjQ4LWZmMmYtNGExNS04NTNkLWYyYTI5YjY3ZmYwZiIsImVtYWlsIjoiR3Vlc3QtMTc1NTg0ODU4ODc4OEBndWVzdC5jb20ifQ.PktllDySS3trlyuFpTeIZf-7hl8Qu1qYF3BxjgIul0BrNux2nX9hVzIjthLXKMWAf9V0qM8Vm_iyDqkjPGsaiQ"
DEFAULT_MODEL_NAME = "GLM-4.5"
THINKING_MODEL_NAME = "GLM-4.5-Thinking"
SEARCH_MODEL_NAME = "GLM-4.5-Search"
PORT = 8080
DEBUG_MODE = True

# 思考内容处理策略
THINK_TAGS_MODE = "think"  # strip: 去除<details>标签；think: 转为<think>标签；raw: 保留原样

# 伪装前端头部
X_FE_VERSION = "prod-fe-1.0.70"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
SEC_CH_UA = '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"'
SEC_CH_UA_MOB = "?0"
SEC_CH_UA_PLAT = '"Windows"'
ORIGIN_BASE = "https://chat.z.ai"

# 匿名token开关
ANON_TOKEN_ENABLED = True


# SSE 解析生成器
class SSEParser:
    """统一的 SSE (Server-Sent Events) 解析生成器"""
    
    def __init__(self, response, debug_mode=False):
        """初始化 SSE 解析器
        
        Args:
            response: requests.Response 对象，需要设置 stream=True
            debug_mode: 是否启用调试模式
        """
        self.response = response
        self.debug_mode = debug_mode
        self.buffer = ""
        self.line_count = 0
    
    def debug_log(self, format_str: str, *args):
        """调试日志"""
        if self.debug_mode:
            print(f"[SSE_PARSER] {format_str % args}")
    
    def iter_events(self):
        """生成器，逐个产生 SSE 事件
        
        Yields:
            dict: 解析后的 SSE 事件数据
        """
        self.debug_log("开始解析 SSE 流")
        
        for line in self.response.iter_lines():
            self.line_count += 1
            
            # 处理空行
            if not line:
                continue
            
            # 解码字节串
            if isinstance(line, bytes):
                try:
                    line = line.decode('utf-8')
                except UnicodeDecodeError:
                    self.debug_log(f"第{self.line_count}行解码失败，跳过")
                    continue
            
            # 处理注释行
            if line.startswith(':'):
                continue
            
            # 解析字段
            if ':' in line:
                field, value = line.split(':', 1)
                field = field.strip()
                value = value.lstrip()  # 去掉冒号后的空格
                
                if field == 'data':
                    # 处理数据字段
                    self.debug_log(f"收到数据 (第{self.line_count}行): {value}")
                    
                    # 尝试解析 JSON
                    try:
                        data = json.loads(value)
                        yield {
                            'type': 'data',
                            'data': data,
                            'raw': value
                        }
                    except json.JSONDecodeError:
                        # 不是 JSON，作为原始数据返回
                        yield {
                            'type': 'data',
                            'data': value,
                            'raw': value,
                            'is_json': False
                        }
                
                elif field == 'event':
                    # 处理事件类型
                    yield {
                        'type': 'event',
                        'event': value
                    }
                
                elif field == 'id':
                    # 处理事件 ID
                    yield {
                        'type': 'id',
                        'id': value
                    }
                
                elif field == 'retry':
                    # 处理重试时间
                    try:
                        retry = int(value)
                        yield {
                            'type': 'retry',
                            'retry': retry
                        }
                    except ValueError:
                        self.debug_log(f"无效的 retry 值: {value}")
    
    def iter_data_only(self):
        """生成器，只产生数据事件
        
        Yields:
            dict: 仅包含数据的 SSE 事件
        """
        for event in self.iter_events():
            if event['type'] == 'data':
                yield event
    
    def iter_json_data(self, model_class=None):
        """生成器，只产生 JSON 数据事件
        
        Args:
            model_class: 可选的 Pydantic 模型类，用于验证数据
            
        Yields:
            dict: 包含解析后的 JSON 数据的事件
        """
        for event in self.iter_events():
            if event['type'] == 'data' and event.get('is_json', True):
                try:
                    if model_class:
                        # 使用 Pydantic 模型验证
                        data = model_class.model_validate_json(event['raw'])
                        yield {
                            'type': 'data',
                            'data': data,
                            'raw': event['raw']
                        }
                    else:
                        yield event
                except Exception as e:
                    self.debug_log(f"数据验证失败: {e}")
                    continue
    
    def close(self):
        """关闭响应连接"""
        if hasattr(self.response, 'close'):
            self.response.close()
    
    def __enter__(self):
        """支持上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动关闭连接"""
        self.close()


# 数据结构定义
class Message(BaseModel):
    role: str
    content: str
    reasoning_content: Optional[str] = None


class OpenAIRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ModelItem(BaseModel):
    id: str
    name: str
    owned_by: str


class UpstreamRequest(BaseModel):
    stream: bool
    model: str
    messages: List[Message]
    params: Dict[str, Any] = {}
    features: Dict[str, Any] = {}
    background_tasks: Optional[Dict[str, bool]] = None
    chat_id: Optional[str] = None
    id: Optional[str] = None
    mcp_servers: Optional[List[str]] = None
    model_item: Optional[ModelItem] = None
    tool_servers: Optional[List[str]] = None
    variables: Optional[Dict[str, str]] = None
    model_config = {'protected_namespaces': ()}


class Delta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    reasoning_content: Optional[str] = None


class Choice(BaseModel):
    index: int
    message: Optional[Message] = None
    delta: Optional[Delta] = None
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[Usage] = None


class UpstreamError(BaseModel):
    detail: str
    code: int


class UpstreamDataInner(BaseModel):
    error: Optional[UpstreamError] = None


class UpstreamDataData(BaseModel):
    delta_content: str = ""
    edit_content: str = ""
    phase: str = ""
    done: bool = False
    usage: Optional[Usage] = None
    error: Optional[UpstreamError] = None
    inner: Optional[UpstreamDataInner] = None


class UpstreamData(BaseModel):
    type: str
    data: UpstreamDataData
    error: Optional[UpstreamError] = None


class Model(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[Model]


# FastAPI应用
app = FastAPI()


# 调试日志函数
def debug_log(format_str: str, *args):
    if DEBUG_MODE:
        print(f"[DEBUG] {format_str % args}")


# 获取匿名token
def get_anonymous_token() -> str:
    """获取匿名token（每次对话使用不同token，避免共享记忆）"""
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "X-FE-Version": X_FE_VERSION,
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": SEC_CH_UA_MOB,
        "sec-ch-ua-platform": SEC_CH_UA_PLAT,
        "Origin": ORIGIN_BASE,
        "Referer": f"{ORIGIN_BASE}/",
    }
    
    response = requests.get(f"{ORIGIN_BASE}/api/v1/auths/", headers=headers, timeout=10.0)
    
    if response.status_code != 200:
        raise Exception(f"anon token status={response.status_code}")
    
    data = response.json()
    token = data.get("token")
    if not token:
        raise Exception("anon token empty")
    
    return token


# CORS中间件
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


# OPTIONS处理器
@app.options("/")
async def handle_options():
    return Response(status_code=200)


# 模型列表接口
@app.get("/v1/models")
async def handle_models():
    response = ModelsResponse(
        data=[
            Model(
                id=DEFAULT_MODEL_NAME,
                created=int(time.time()),
                owned_by="z.ai"
            ),
            Model(
                id=THINKING_MODEL_NAME,
                created=int(time.time()),
                owned_by="z.ai"
            ),
            Model(
                id=SEARCH_MODEL_NAME,
                created=int(time.time()),
                owned_by="z.ai"
            ),
        ]
    )
    return response


# 聊天完成接口
@app.post("/v1/chat/completions")
async def handle_chat_completions(
    request: OpenAIRequest,
    authorization: str = Header(...)
):
    debug_log("收到chat completions请求")
    
    # 验证API Key
    if not authorization.startswith("Bearer "):
        debug_log("缺少或无效的Authorization头")
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    api_key = authorization[7:]  # 去掉"Bearer "
    if api_key != DEFAULT_KEY:
        debug_log(f"无效的API key: {api_key}")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    debug_log("API key验证通过")
    debug_log(f"请求解析成功 - 模型: {request.model}, 流式: {request.stream}, 消息数: {len(request.messages)}")
    
    # 生成会话相关ID
    chat_id = f"{int(time.time() * 1000)}-{int(time.time())}"
    msg_id = str(int(time.time() * 1000000))
    
    # 确定模型特性
    is_thinking = request.model == THINKING_MODEL_NAME
    is_search = request.model == SEARCH_MODEL_NAME
    search_mcp = "deep-web-search" if is_search else ""
    
    # 构造上游请求
    upstream_req = UpstreamRequest(
        stream=True,  # 总是使用流式从上游获取
        chat_id=chat_id,
        id=msg_id,
        model="0727-360B-API",  # 上游实际模型ID
        messages=request.messages,
        params={},
        features={
            "enable_thinking": is_thinking,
            "web_search": is_search,
            "auto_web_search": is_search,
        },
        background_tasks={
            "title_generation": False,
            "tags_generation": False,
        },
        mcp_servers=[search_mcp] if search_mcp else [],
        model_item=ModelItem(
            id="0727-360B-API",
            name="GLM-4.5",
            owned_by="openai"
        ),
        tool_servers=[],
        variables={
            "{{USER_NAME}}": "User",
            "{{USER_LOCATION}}": "Unknown",
            "{{CURRENT_DATETIME}}": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    
    # 选择本次对话使用的token
    auth_token = UPSTREAM_TOKEN
    if ANON_TOKEN_ENABLED:
        try:
            token = get_anonymous_token()
            auth_token = token
            debug_log(f"匿名token获取成功: {token[:10]}...")
        except Exception as e:
            debug_log(f"匿名token获取失败，回退固定token: {e}")
    
    # 调用上游API
    if request.stream:
        return StreamingResponse(
            handle_stream_response(upstream_req, chat_id, auth_token),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    else:
        return handle_non_stream_response(upstream_req, chat_id, auth_token)


def call_upstream_with_headers(upstream_req: UpstreamRequest, referer_chat_id: str, auth_token: str) -> requests.Response:
    """调用上游API"""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": BROWSER_UA,
        "Authorization": f"Bearer {auth_token}",
        "Accept-Language": "zh-CN",
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": SEC_CH_UA_MOB,
        "sec-ch-ua-platform": SEC_CH_UA_PLAT,
        "X-FE-Version": X_FE_VERSION,
        "Origin": ORIGIN_BASE,
        "Referer": f"{ORIGIN_BASE}/c/{referer_chat_id}",
    }
    
    debug_log(f"调用上游API: {UPSTREAM_URL}")
    debug_log(f"上游请求体: {upstream_req.model_dump_json()}")
    
    response = requests.post(
        UPSTREAM_URL,
        json=upstream_req.model_dump(exclude_none=True),
        headers=headers,
        timeout=60.0,
        stream=True
    )
    
    debug_log(f"上游响应状态: {response.status_code}")
    return response


def transform_thinking(s: str) -> str:
    """转换思考内容"""
    # 去 <summary>…</summary>
    s = re.sub(r'(?s)<summary>.*?</summary>', '', s)
    # 清理残留自定义标签
    s = s.replace("</thinking>", "").replace("<Full>", "").replace("</Full>", "")
    s = s.strip()
    
    if THINK_TAGS_MODE == "think":
        s = re.sub(r'<details[^>]*>', '<think>', s)
        s = s.replace("</details>", "</think>")
    elif THINK_TAGS_MODE == "strip":
        s = re.sub(r'<details[^>]*>', '', s)
        s = s.replace("</details>", "")
    
    # 处理每行前缀 "> "
    s = s.lstrip("> ")
    s = s.replace("\n> ", "\n")
    return s.strip()


def handle_stream_response(upstream_req: UpstreamRequest, chat_id: str, auth_token: str):
    """处理流式响应"""
    debug_log(f"开始处理流式响应 (chat_id={chat_id})")
    
    try:
        response = call_upstream_with_headers(upstream_req, chat_id, auth_token)
    except Exception as e:
        debug_log(f"调用上游失败: {e}")
        yield "data: {\"error\": \"Failed to call upstream\"}\n\n"
        return
    
    if response.status_code != 200:
        debug_log(f"上游返回错误状态: {response.status_code}")
        if DEBUG_MODE:
            debug_log(f"上游错误响应: {response.text}")
        yield "data: {\"error\": \"Upstream error\"}\n\n"
        return
    
    # 发送第一个chunk（role）
    first_chunk = OpenAIResponse(
        id=f"chatcmpl-{int(time.time())}",
        object="chat.completion.chunk",
        created=int(time.time()),
        model=DEFAULT_MODEL_NAME,
        choices=[Choice(
            index=0,
            delta=Delta(role="assistant")
        )]
    )
    yield f"data: {first_chunk.model_dump_json()}\n\n"
    
    # 使用 SSE 解析器处理流
    debug_log("开始读取上游SSE流")
    sent_initial_answer = False
    
    with SSEParser(response, debug_mode=DEBUG_MODE) as parser:
        for event in parser.iter_json_data(UpstreamData):
            upstream_data = event['data']
            
            # 错误检测
            if (upstream_data.error or 
                upstream_data.data.error or 
                (upstream_data.data.inner and upstream_data.data.inner.error)):
                
                err_obj = upstream_data.error or upstream_data.data.error
                if not err_obj and upstream_data.data.inner:
                    err_obj = upstream_data.data.inner.error
                
                debug_log(f"上游错误: code={err_obj.code}, detail={err_obj.detail}")
                
                # 结束下游流
                end_chunk = OpenAIResponse(
                    id=f"chatcmpl-{int(time.time())}",
                    object="chat.completion.chunk",
                    created=int(time.time()),
                    model=DEFAULT_MODEL_NAME,
                    choices=[Choice(
                        index=0,
                        delta=Delta(),
                        finish_reason="stop"
                    )]
                )
                yield f"data: {end_chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
                break
            
            debug_log(f"解析成功 - 类型: {upstream_data.type}, 阶段: {upstream_data.data.phase}, "
                     f"内容长度: {len(upstream_data.data.delta_content)}, 完成: {upstream_data.data.done}")
            
            # 处理EditContent在最初的answer信息（只发送一次）
            if (not sent_initial_answer and 
                upstream_data.data.edit_content and 
                upstream_data.data.phase == "answer"):
                
                out = upstream_data.data.edit_content
                if out:
                    parts = out.split("</details>")
                    if len(parts) > 1:
                        content = parts[1]
                        if content:
                            debug_log(f"发送普通内容: {content}")
                            chunk = OpenAIResponse(
                                id=f"chatcmpl-{int(time.time())}",
                                object="chat.completion.chunk",
                                created=int(time.time()),
                                model=DEFAULT_MODEL_NAME,
                                choices=[Choice(
                                    index=0,
                                    delta=Delta(content=content)
                                )]
                            )
                            yield f"data: {chunk.model_dump_json()}\n\n"
                            sent_initial_answer = True
            
            # 处理DeltaContent
            if upstream_data.data.delta_content:
                out = upstream_data.data.delta_content
                
                if upstream_data.data.phase == "thinking":
                    out = transform_thinking(out)
                    # 思考内容使用 reasoning_content 字段
                    if out:
                        debug_log(f"发送思考内容: {out}")
                        chunk = OpenAIResponse(
                            id=f"chatcmpl-{int(time.time())}",
                            object="chat.completion.chunk",
                            created=int(time.time()),
                            model=DEFAULT_MODEL_NAME,
                            choices=[Choice(
                                index=0,
                                delta=Delta(reasoning_content=out)
                            )]
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"
                else:
                    # 普通内容使用 content 字段
                    if out:
                        debug_log(f"发送普通内容: {out}")
                        chunk = OpenAIResponse(
                            id=f"chatcmpl-{int(time.time())}",
                            object="chat.completion.chunk",
                            created=int(time.time()),
                            model=DEFAULT_MODEL_NAME,
                            choices=[Choice(
                                index=0,
                                delta=Delta(content=out)
                            )]
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"
            
            # 检查是否结束
            if upstream_data.data.done or upstream_data.data.phase == "done":
                debug_log("检测到流结束信号")
                
                # 发送结束chunk
                end_chunk = OpenAIResponse(
                    id=f"chatcmpl-{int(time.time())}",
                    object="chat.completion.chunk",
                    created=int(time.time()),
                    model=DEFAULT_MODEL_NAME,
                    choices=[Choice(
                        index=0,
                        delta=Delta(),
                        finish_reason="stop"
                    )]
                )
                yield f"data: {end_chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
                debug_log(f"流式响应完成")
                break


def handle_non_stream_response(upstream_req: UpstreamRequest, chat_id: str, auth_token: str) -> JSONResponse:
    """处理非流式响应"""
    debug_log(f"开始处理非流式响应 (chat_id={chat_id})")
    
    try:
        response = call_upstream_with_headers(upstream_req, chat_id, auth_token)
    except Exception as e:
        debug_log(f"调用上游失败: {e}")
        raise HTTPException(status_code=502, detail="Failed to call upstream")
    
    if response.status_code != 200:
        debug_log(f"上游返回错误状态: {response.status_code}")
        if DEBUG_MODE:
            debug_log(f"上游错误响应: {response.text}")
        raise HTTPException(status_code=502, detail="Upstream error")
    
    # 收集完整响应
    full_content = []
    debug_log("开始收集完整响应内容")
    
    with SSEParser(response, debug_mode=DEBUG_MODE) as parser:
        for event in parser.iter_json_data(UpstreamData):
            upstream_data = event['data']
            
            if upstream_data.data.delta_content:
                out = upstream_data.data.delta_content
                
                if upstream_data.data.phase == "thinking":
                    out = transform_thinking(out)
                
                if out:
                    full_content.append(out)
            
            if upstream_data.data.done or upstream_data.data.phase == "done":
                debug_log("检测到完成信号，停止收集")
                break
    
    final_content = "".join(full_content)
    debug_log(f"内容收集完成，最终长度: {len(final_content)}")
    
    # 构造完整响应
    response_data = OpenAIResponse(
        id=f"chatcmpl-{int(time.time())}",
        object="chat.completion",
        created=int(time.time()),
        model=DEFAULT_MODEL_NAME,
        choices=[Choice(
            index=0,
            message=Message(
                role="assistant",
                content=final_content
            ),
            finish_reason="stop"
        )],
        usage=Usage()
    )
    
    debug_log("非流式响应发送完成")
    return JSONResponse(content=response_data.model_dump(exclude_none=True))


# 根路径处理器
@app.get("/")
async def root():
    return {"message": "OpenAI Compatible API Server"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)