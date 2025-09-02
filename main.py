# -*- coding: utf-8 -*-

"""
OpenAI Compatible API Server for Z.AI
=====================================

This module provides an OpenAI-compatible API server that forwards requests
to the Z.AI chat service with proper authentication and response formatting.
"""

import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Generator, Tuple

import requests
from fastapi import FastAPI, Request, Response, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field


# =============================================================================
# Configuration Constants
# =============================================================================

class Config:
    """Centralized configuration constants"""
    
    # API Configuration
    UPSTREAM_URL: str = "https://chat.z.ai/api/chat/completions"
    DEFAULT_KEY: str = "sk-tbkFoKzk9a531YyUNNF5"
    UPSTREAM_TOKEN: str = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjMxNmJjYjQ4LWZmMmYtNGExNS04NTNkLWYyYTI5YjY3ZmYwZiIsImVtYWlsIjoiR3Vlc3QtMTc1NTg0ODU4ODc4OEBndWVzdC5jb20ifQ.PktllDySS3trlyuFpTeIZf-7hl8Qu1qYF3BxjgIul0BrNux2nX9hVzIjthLXKMWAf9V0qM8Vm_iyDqkjPGsaiQ"
    
    # Model Configuration
    DEFAULT_MODEL_NAME: str = "GLM-4.5"
    THINKING_MODEL_NAME: str = "GLM-4.5-Thinking"
    SEARCH_MODEL_NAME: str = "GLM-4.5-Search"
    
    # Server Configuration
    PORT: int = 8080
    DEBUG_MODE: bool = True
    
    # Feature Configuration
    THINK_TAGS_MODE: str = "think"  # strip: 去除<details>标签；think: 转为<think>标签；raw: 保留原样
    ANON_TOKEN_ENABLED: bool = True
    
    # Browser Headers
    X_FE_VERSION: str = "prod-fe-1.0.70"
    BROWSER_UA: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
    SEC_CH_UA: str = '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"'
    SEC_CH_UA_MOB: str = "?0"
    SEC_CH_UA_PLAT: str = '"Windows"'
    ORIGIN_BASE: str = "https://chat.z.ai"


# =============================================================================
# Data Models
# =============================================================================

class Message(BaseModel):
    """Chat message model"""
    role: str
    content: str
    reasoning_content: Optional[str] = None


class OpenAIRequest(BaseModel):
    """OpenAI-compatible request model"""
    model: str
    messages: List[Message]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ModelItem(BaseModel):
    """Model information item"""
    id: str
    name: str
    owned_by: str


class UpstreamRequest(BaseModel):
    """Upstream service request model"""
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
    """Stream delta model"""
    role: Optional[str] = None
    content: Optional[str] = None
    reasoning_content: Optional[str] = None


class Choice(BaseModel):
    """Response choice model"""
    index: int
    message: Optional[Message] = None
    delta: Optional[Delta] = None
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    """Token usage statistics"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIResponse(BaseModel):
    """OpenAI-compatible response model"""
    id: str
    object: str
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[Usage] = None


class UpstreamError(BaseModel):
    """Upstream error model"""
    detail: str
    code: int


class UpstreamDataInner(BaseModel):
    """Inner upstream data model"""
    error: Optional[UpstreamError] = None


class UpstreamDataData(BaseModel):
    """Upstream data content model"""
    delta_content: str = ""
    edit_content: str = ""
    phase: str = ""
    done: bool = False
    usage: Optional[Usage] = None
    error: Optional[UpstreamError] = None
    inner: Optional[UpstreamDataInner] = None


class UpstreamData(BaseModel):
    """Upstream data model"""
    type: str
    data: UpstreamDataData
    error: Optional[UpstreamError] = None


class Model(BaseModel):
    """Model information for listing"""
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelsResponse(BaseModel):
    """Models list response model"""
    object: str = "list"
    data: List[Model]


# =============================================================================
# SSE Parser
# =============================================================================

class SSEParser:
    """Server-Sent Events parser for streaming responses"""
    
    def __init__(self, response: requests.Response, debug_mode: bool = False):
        """Initialize SSE parser
        
        Args:
            response: requests.Response object with stream=True
            debug_mode: Enable debug logging
        """
        self.response = response
        self.debug_mode = debug_mode
        self.buffer = ""
        self.line_count = 0
    
    def debug_log(self, format_str: str, *args) -> None:
        """Log debug message if debug mode is enabled"""
        if self.debug_mode:
            print(f"[SSE_PARSER] {format_str % args}")
    
    def iter_events(self) -> Generator[Dict[str, Any], None, None]:
        """Iterate over SSE events
        
        Yields:
            dict: Parsed SSE event data
        """
        self.debug_log("开始解析 SSE 流")
        
        for line in self.response.iter_lines():
            self.line_count += 1
            
            # Skip empty lines
            if not line:
                continue
            
            # Decode bytes
            if isinstance(line, bytes):
                try:
                    line = line.decode('utf-8')
                except UnicodeDecodeError:
                    self.debug_log(f"第{self.line_count}行解码失败，跳过")
                    continue
            
            # Skip comment lines
            if line.startswith(':'):
                continue
            
            # Parse field-value pairs
            if ':' in line:
                field, value = line.split(':', 1)
                field = field.strip()
                value = value.lstrip()
                
                if field == 'data':
                    self.debug_log(f"收到数据 (第{self.line_count}行): {value}")
                    
                    # Try to parse JSON
                    try:
                        data = json.loads(value)
                        yield {
                            'type': 'data',
                            'data': data,
                            'raw': value
                        }
                    except json.JSONDecodeError:
                        yield {
                            'type': 'data',
                            'data': value,
                            'raw': value,
                            'is_json': False
                        }
                
                elif field == 'event':
                    yield {'type': 'event', 'event': value}
                
                elif field == 'id':
                    yield {'type': 'id', 'id': value}
                
                elif field == 'retry':
                    try:
                        retry = int(value)
                        yield {'type': 'retry', 'retry': retry}
                    except ValueError:
                        self.debug_log(f"无效的 retry 值: {value}")
    
    def iter_data_only(self) -> Generator[Dict[str, Any], None, None]:
        """Iterate only over data events"""
        for event in self.iter_events():
            if event['type'] == 'data':
                yield event
    
    def iter_json_data(self, model_class: Optional[type] = None) -> Generator[Dict[str, Any], None, None]:
        """Iterate only over JSON data events with optional validation
        
        Args:
            model_class: Optional Pydantic model class for validation
            
        Yields:
            dict: JSON data events
        """
        for event in self.iter_events():
            if event['type'] == 'data' and event.get('is_json', True):
                try:
                    if model_class:
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
    
    def close(self) -> None:
        """Close the response connection"""
        if hasattr(self.response, 'close'):
            self.response.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.close()


# =============================================================================
# Utility Functions
# =============================================================================

def debug_log(message: str, *args) -> None:
    """Log debug message if debug mode is enabled"""
    if Config.DEBUG_MODE:
        print(f"[DEBUG] {message % args}")


def generate_request_ids() -> Tuple[str, str]:
    """Generate unique IDs for chat and message"""
    timestamp = int(time.time())
    chat_id = f"{timestamp * 1000}-{timestamp}"
    msg_id = str(timestamp * 1000000)
    return chat_id, msg_id


def get_browser_headers(referer_chat_id: str = "") -> Dict[str, str]:
    """Get browser headers for API requests"""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": Config.BROWSER_UA,
        "Accept-Language": "zh-CN",
        "sec-ch-ua": Config.SEC_CH_UA,
        "sec-ch-ua-mobile": Config.SEC_CH_UA_MOB,
        "sec-ch-ua-platform": Config.SEC_CH_UA_PLAT,
        "X-FE-Version": Config.X_FE_VERSION,
        "Origin": Config.ORIGIN_BASE,
    }
    
    if referer_chat_id:
        headers["Referer"] = f"{Config.ORIGIN_BASE}/c/{referer_chat_id}"
    
    return headers


def get_anonymous_token() -> str:
    """Get anonymous token for authentication"""
    headers = get_browser_headers()
    headers.update({
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": f"{Config.ORIGIN_BASE}/",
    })
    
    try:
        response = requests.get(
            f"{Config.ORIGIN_BASE}/api/v1/auths/",
            headers=headers,
            timeout=10.0
        )
        
        if response.status_code != 200:
            raise Exception(f"anon token status={response.status_code}")
        
        data = response.json()
        token = data.get("token")
        if not token:
            raise Exception("anon token empty")
        
        return token
    except Exception as e:
        debug_log(f"获取匿名token失败: {e}")
        raise


def get_auth_token() -> str:
    """Get authentication token (anonymous or fixed)"""
    if Config.ANON_TOKEN_ENABLED:
        try:
            token = get_anonymous_token()
            debug_log(f"匿名token获取成功: {token[:10]}...")
            return token
        except Exception as e:
            debug_log(f"匿名token获取失败，回退固定token: {e}")
    
    return Config.UPSTREAM_TOKEN


def transform_thinking_content(content: str) -> str:
    """Transform thinking content according to configuration"""
    # Remove summary tags
    content = re.sub(r'(?s)<summary>.*?</summary>', '', content)
    # Clean up remaining tags
    content = content.replace("</thinking>", "").replace("<Full>", "").replace("</Full>", "")
    content = content.strip()
    
    if Config.THINK_TAGS_MODE == "think":
        content = re.sub(r'<details[^>]*>', '<think>', content)
        content = content.replace("</details>", "</think>")
    elif Config.THINK_TAGS_MODE == "strip":
        content = re.sub(r'<details[^>]*>', '', content)
        content = content.replace("</details>", "")
    
    # Remove line prefixes
    content = content.lstrip("> ")
    content = content.replace("\n> ", "\n")
    
    return content.strip()


def create_openai_response_chunk(
    model: str,
    delta: Optional[Delta] = None,
    finish_reason: Optional[str] = None
) -> OpenAIResponse:
    """Create OpenAI response chunk for streaming"""
    return OpenAIResponse(
        id=f"chatcmpl-{int(time.time())}",
        object="chat.completion.chunk",
        created=int(time.time()),
        model=model,
        choices=[Choice(
            index=0,
            delta=delta or Delta(),
            finish_reason=finish_reason
        )]
    )


def handle_upstream_error(error: UpstreamError) -> Generator[str, None, None]:
    """Handle upstream error response"""
    debug_log(f"上游错误: code={error.code}, detail={error.detail}")
    
    # Send end chunk
    end_chunk = create_openai_response_chunk(
        model=Config.DEFAULT_MODEL_NAME,
        finish_reason="stop"
    )
    yield f"data: {end_chunk.model_dump_json()}\n\n"
    yield "data: [DONE]\n\n"


def call_upstream_api(
    upstream_req: UpstreamRequest,
    chat_id: str,
    auth_token: str
) -> requests.Response:
    """Call upstream API with proper headers"""
    headers = get_browser_headers(chat_id)
    headers["Authorization"] = f"Bearer {auth_token}"
    
    debug_log(f"调用上游API: {Config.UPSTREAM_URL}")
    debug_log(f"上游请求体: {upstream_req.model_dump_json()}")
    
    response = requests.post(
        Config.UPSTREAM_URL,
        json=upstream_req.model_dump(exclude_none=True),
        headers=headers,
        timeout=60.0,
        stream=True
    )
    
    debug_log(f"上游响应状态: {response.status_code}")
    return response


# =============================================================================
# Response Handlers
# =============================================================================

class ResponseHandler:
    """Base class for response handling"""
    
    def __init__(self, upstream_req: UpstreamRequest, chat_id: str, auth_token: str):
        self.upstream_req = upstream_req
        self.chat_id = chat_id
        self.auth_token = auth_token
    
    def _call_upstream(self) -> requests.Response:
        """Call upstream API with error handling"""
        try:
            return call_upstream_api(self.upstream_req, self.chat_id, self.auth_token)
        except Exception as e:
            debug_log(f"调用上游失败: {e}")
            raise
    
    def _handle_upstream_error(self, response: requests.Response) -> None:
        """Handle upstream error response"""
        debug_log(f"上游返回错误状态: {response.status_code}")
        if Config.DEBUG_MODE:
            debug_log(f"上游错误响应: {response.text}")


class StreamResponseHandler(ResponseHandler):
    """Handler for streaming responses"""
    
    def handle(self) -> Generator[str, None, None]:
        """Handle streaming response"""
        debug_log(f"开始处理流式响应 (chat_id={self.chat_id})")
        
        try:
            response = self._call_upstream()
        except Exception:
            yield "data: {\"error\": \"Failed to call upstream\"}\n\n"
            return
        
        if response.status_code != 200:
            self._handle_upstream_error(response)
            yield "data: {\"error\": \"Upstream error\"}\n\n"
            return
        
        # Send initial role chunk
        first_chunk = create_openai_response_chunk(
            model=Config.DEFAULT_MODEL_NAME,
            delta=Delta(role="assistant")
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"
        
        # Process stream
        debug_log("开始读取上游SSE流")
        sent_initial_answer = False
        
        with SSEParser(response, debug_mode=Config.DEBUG_MODE) as parser:
            for event in parser.iter_json_data(UpstreamData):
                upstream_data = event['data']
                
                # Check for errors
                if self._has_error(upstream_data):
                    error = self._get_error(upstream_data)
                    yield from handle_upstream_error(error)
                    break
                
                debug_log(f"解析成功 - 类型: {upstream_data.type}, 阶段: {upstream_data.data.phase}, "
                         f"内容长度: {len(upstream_data.data.delta_content)}, 完成: {upstream_data.data.done}")
                
                # Process content
                yield from self._process_content(upstream_data, sent_initial_answer)
                
                # Check if done
                if upstream_data.data.done or upstream_data.data.phase == "done":
                    debug_log("检测到流结束信号")
                    yield from self._send_end_chunk()
                    break
    
    def _has_error(self, upstream_data: UpstreamData) -> bool:
        """Check if upstream data contains error"""
        return bool(
            upstream_data.error or 
            upstream_data.data.error or 
            (upstream_data.data.inner and upstream_data.data.inner.error)
        )
    
    def _get_error(self, upstream_data: UpstreamData) -> UpstreamError:
        """Get error from upstream data"""
        return (
            upstream_data.error or 
            upstream_data.data.error or 
            (upstream_data.data.inner.error if upstream_data.data.inner else None)
        )
    
    def _process_content(
        self, 
        upstream_data: UpstreamData, 
        sent_initial_answer: bool
    ) -> Generator[str, None, None]:
        """Process content from upstream data"""
        # Handle initial answer content
        if (not sent_initial_answer and 
            upstream_data.data.edit_content and 
            upstream_data.data.phase == "answer"):
            
            content = self._extract_edit_content(upstream_data.data.edit_content)
            if content:
                debug_log(f"发送普通内容: {content}")
                chunk = create_openai_response_chunk(
                    model=Config.DEFAULT_MODEL_NAME,
                    delta=Delta(content=content)
                )
                yield f"data: {chunk.model_dump_json()}\n\n"
                sent_initial_answer = True
        
        # Handle delta content
        if upstream_data.data.delta_content:
            content = upstream_data.data.delta_content
            
            if upstream_data.data.phase == "thinking":
                content = transform_thinking_content(content)
                if content:
                    debug_log(f"发送思考内容: {content}")
                    chunk = create_openai_response_chunk(
                        model=Config.DEFAULT_MODEL_NAME,
                        delta=Delta(reasoning_content=content)
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
            else:
                if content:
                    debug_log(f"发送普通内容: {content}")
                    chunk = create_openai_response_chunk(
                        model=Config.DEFAULT_MODEL_NAME,
                        delta=Delta(content=content)
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
    
    def _extract_edit_content(self, edit_content: str) -> str:
        """Extract content from edit_content field"""
        parts = edit_content.split("</details>")
        return parts[1] if len(parts) > 1 else ""
    
    def _send_end_chunk(self) -> Generator[str, None, None]:
        """Send end chunk and DONE signal"""
        end_chunk = create_openai_response_chunk(
            model=Config.DEFAULT_MODEL_NAME,
            finish_reason="stop"
        )
        yield f"data: {end_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
        debug_log("流式响应完成")


class NonStreamResponseHandler(ResponseHandler):
    """Handler for non-streaming responses"""
    
    def handle(self) -> JSONResponse:
        """Handle non-streaming response"""
        debug_log(f"开始处理非流式响应 (chat_id={self.chat_id})")
        
        try:
            response = self._call_upstream()
        except Exception as e:
            debug_log(f"调用上游失败: {e}")
            raise HTTPException(status_code=502, detail="Failed to call upstream")
        
        if response.status_code != 200:
            self._handle_upstream_error(response)
            raise HTTPException(status_code=502, detail="Upstream error")
        
        # Collect full response
        full_content = []
        debug_log("开始收集完整响应内容")
        
        with SSEParser(response, debug_mode=Config.DEBUG_MODE) as parser:
            for event in parser.iter_json_data(UpstreamData):
                upstream_data = event['data']
                
                if upstream_data.data.delta_content:
                    content = upstream_data.data.delta_content
                    
                    if upstream_data.data.phase == "thinking":
                        content = transform_thinking_content(content)
                    
                    if content:
                        full_content.append(content)
                
                if upstream_data.data.done or upstream_data.data.phase == "done":
                    debug_log("检测到完成信号，停止收集")
                    break
        
        final_content = "".join(full_content)
        debug_log(f"内容收集完成，最终长度: {len(final_content)}")
        
        # Build response
        response_data = OpenAIResponse(
            id=f"chatcmpl-{int(time.time())}",
            object="chat.completion",
            created=int(time.time()),
            model=Config.DEFAULT_MODEL_NAME,
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


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="OpenAI Compatible API Server",
    description="An OpenAI-compatible API server for Z.AI chat service",
    version="1.0.0"
)


# CORS middleware
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    """Add CORS headers to responses"""
    response = await call_next(request)
    response.headers.update({
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Credentials": "true"
    })
    return response


# =============================================================================
# API Endpoints
# =============================================================================

@app.options("/")
async def handle_options():
    """Handle OPTIONS requests"""
    return Response(status_code=200)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "OpenAI Compatible API Server"}


@app.get("/v1/models")
async def list_models():
    """List available models"""
    current_time = int(time.time())
    response = ModelsResponse(
        data=[
            Model(
                id=Config.DEFAULT_MODEL_NAME,
                created=current_time,
                owned_by="z.ai"
            ),
            Model(
                id=Config.THINKING_MODEL_NAME,
                created=current_time,
                owned_by="z.ai"
            ),
            Model(
                id=Config.SEARCH_MODEL_NAME,
                created=current_time,
                owned_by="z.ai"
            ),
        ]
    )
    return response


@app.post("/v1/chat/completions")
async def chat_completions(
    request: OpenAIRequest,
    authorization: str = Header(...)
):
    """Handle chat completion requests"""
    debug_log("收到chat completions请求")
    
    # Validate API key
    if not authorization.startswith("Bearer "):
        debug_log("缺少或无效的Authorization头")
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    api_key = authorization[7:]
    if api_key != Config.DEFAULT_KEY:
        debug_log(f"无效的API key: {api_key}")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    debug_log("API key验证通过")
    debug_log(f"请求解析成功 - 模型: {request.model}, 流式: {request.stream}, 消息数: {len(request.messages)}")
    
    # Generate IDs
    chat_id, msg_id = generate_request_ids()
    
    # Determine model features
    is_thinking = request.model == Config.THINKING_MODEL_NAME
    is_search = request.model == Config.SEARCH_MODEL_NAME
    search_mcp = "deep-web-search" if is_search else ""
    
    # Build upstream request
    upstream_req = UpstreamRequest(
        stream=True,  # Always use streaming from upstream
        chat_id=chat_id,
        id=msg_id,
        model="0727-360B-API",  # Actual upstream model ID
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
    
    # Get authentication token
    auth_token = get_auth_token()
    
    # Handle response based on stream flag
    if request.stream:
        handler = StreamResponseHandler(upstream_req, chat_id, auth_token)
        return StreamingResponse(
            handler.handle(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    else:
        handler = NonStreamResponseHandler(upstream_req, chat_id, auth_token)
        return handler.handle()


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=Config.PORT, reload=True)