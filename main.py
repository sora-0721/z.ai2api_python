

import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, AsyncGenerator
from urllib.parse import urljoin

import httpx
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
async def get_anonymous_token() -> str:
    """获取匿名token（每次对话使用不同token，避免共享记忆）"""
    async with httpx.AsyncClient(timeout=10.0) as client:
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
        
        response = await client.get(f"{ORIGIN_BASE}/api/v1/auths/", headers=headers)
        
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
@app.options("/v1/{path:path}")
async def handle_options(path: str = ""):
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
    return JSONResponse(content=response.model_dump(exclude_none=True))


# 聊天完成接口
@app.post("/v1/chat/completions")
async def handle_chat_completions(
    request: OpenAIRequest,
    authorization: Optional[str] = Header(None)
):
    debug_log("收到chat completions请求")
    
    # 验证API Key
    if not authorization or not authorization.startswith("Bearer "):
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
            token = await get_anonymous_token()
            if token:
                auth_token = token
                debug_log(f"匿名token获取成功: {token[:10] if len(token) > 10 else token}...")
            else:
                debug_log("获取到的匿名token为空，使用固定token")
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
        return await handle_non_stream_response(upstream_req, chat_id, auth_token)


async def call_upstream_with_headers(upstream_req: UpstreamRequest, referer_chat_id: str, auth_token: str) -> httpx.Response:
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
    debug_log(f"上游请求体: {upstream_req.model_dump_json(exclude_none=True)}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            UPSTREAM_URL,
            json=upstream_req.model_dump(exclude_none=True),
            headers=headers
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


async def handle_stream_response(upstream_req: UpstreamRequest, chat_id: str, auth_token: str) -> AsyncGenerator[str, None]:
    """处理流式响应"""
    debug_log(f"开始处理流式响应 (chat_id={chat_id})")
    
    try:
        response = await call_upstream_with_headers(upstream_req, chat_id, auth_token)
    except Exception as e:
        debug_log(f"调用上游失败: {e}")
        yield f"data: {{\"error\": \"Failed to call upstream\", \"type\": \"server_error\"}}\n\n"
        return
    
    if response.status_code != 200:
        debug_log(f"上游返回错误状态: {response.status_code}")
        if DEBUG_MODE:
            debug_log(f"上游错误响应: {response.text}")
        yield f"data: {{\"error\": \"Upstream error\", \"type\": \"upstream_error\"}}\n\n"
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
    
    # 读取上游SSE流
    debug_log("开始读取上游SSE流")
    line_count = 0
    sent_initial_answer = False
    
    try:
        async for line in response.aiter_lines():
            line_count += 1
            
            if not line.startswith("data: "):
                continue
            
            data_str = line[6:]  # 去掉 "data: "
            if not data_str:
                continue
            
            debug_log(f"收到SSE数据 (第{line_count}行): {data_str}")
            
            try:
                upstream_data = UpstreamData.model_validate_json(data_str)
            except Exception as e:
                debug_log(f"SSE数据解析失败: {e}")
                continue
            
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
                    # 使用正则表达式分割，支持多行
                    parts = re.split(r'</details>', out)
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
                debug_log(f"流式响应完成，共处理{line_count}行")
                break
    except Exception as e:
        debug_log(f"读取SSE流时发生错误: {e}")
        yield f"data: {{\"error\": \"Stream reading error\", \"type\": \"stream_error\"}}\n\n"


async def handle_non_stream_response(upstream_req: UpstreamRequest, chat_id: str, auth_token: str) -> JSONResponse:
    """处理非流式响应"""
    debug_log(f"开始处理非流式响应 (chat_id={chat_id})")
    
    try:
        response = await call_upstream_with_headers(upstream_req, chat_id, auth_token)
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
    
    try:
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            
            data_str = line[6:]
            if not data_str:
                continue
            
            try:
                upstream_data = UpstreamData.model_validate_json(data_str)
            except Exception:
                continue
            
            if upstream_data.data.delta_content:
                out = upstream_data.data.delta_content
                
                if upstream_data.data.phase == "thinking":
                    out = transform_thinking(out)
                
                if out:
                    full_content.append(out)
            
            if upstream_data.data.done or upstream_data.data.phase == "done":
                debug_log("检测到完成信号，停止收集")
                break
    except Exception as e:
        debug_log(f"读取响应流时发生错误: {e}")
        raise HTTPException(status_code=502, detail="Failed to read upstream response")
    
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
    # 添加CORS头
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Credentials": "true"
    }
    return JSONResponse(
        content=response_data.model_dump(exclude_none=True),
        headers=headers
    )


# 根路径处理器
@app.get("/")
async def root():
    return {"message": "OpenAI Compatible API Server"}


# 根路径处理器
@app.get("/")
async def root():
    return {"message": "OpenAI Compatible API Server"}


# 健康检查接口
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": int(time.time())}


if __name__ == "__main__":
    import uvicorn
    print(f"OpenAI兼容API服务器启动在端口 {PORT}")
    print(f"模型: {DEFAULT_MODEL_NAME}")
    print(f"上游: {UPSTREAM_URL}")
    print(f"Debug模式: {DEBUG_MODE}")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=DEBUG_MODE)