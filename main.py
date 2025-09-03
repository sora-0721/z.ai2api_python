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

class ServerConfig:
    """Centralized server configuration"""
    
    # API Configuration
    API_ENDPOINT: str = "https://chat.z.ai/api/chat/completions"
    AUTH_TOKEN: str = "sk-your-api-key"
    BACKUP_TOKEN: str = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjMxNmJjYjQ4LWZmMmYtNGExNS04NTNkLWYyYTI5YjY3ZmYwZiIsImVtYWlsIjoiR3Vlc3QtMTc1NTg0ODU4ODc4OEBndWVzdC5jb20ifQ.PktllDySS3trlyuFpTeIZf-7hl8Qu1qYF3BxjgIul0BrNux2nX9hVzIjthLXKMWAf9V0qM8Vm_iyDqkjPGsaiQ"
    
    # Model Configuration
    PRIMARY_MODEL: str = "GLM-4.5"
    THINKING_MODEL: str = "GLM-4.5-Thinking"
    SEARCH_MODEL: str = "GLM-4.5-Search"
    
    # Server Configuration
    LISTEN_PORT: int = 8080
    DEBUG_LOGGING: bool = True
    
    # Feature Configuration
    THINKING_PROCESSING: str = "think"  # strip: 去除<details>标签；think: 转为</think>标签；raw: 保留原样
    ANONYMOUS_MODE: bool = True
    TOOL_SUPPORT: bool = True
    SCAN_LIMIT: int = 200000
    
    # Browser Headers
    CLIENT_HEADERS: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
        "Accept-Language": "zh-CN",
        "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "X-FE-Version": "prod-fe-1.0.70",
        "Origin": "https://chat.z.ai",
    }


# =============================================================================
# Data Models
# =============================================================================

class Message(BaseModel):
    """Chat message model"""
    role: str
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class OpenAIRequest(BaseModel):
    """OpenAI-compatible request model"""
    model: str
    messages: List[Message]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None


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
    tool_calls: Optional[List[Dict[str, Any]]] = None


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
            if args:
                print(f"[SSE_PARSER] {format_str % args}")
            else:
                print(f"[SSE_PARSER] {format_str}")
    
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
# Function Call Utilities
# =============================================================================

def generate_tool_prompt(tools: List[Dict[str, Any]]) -> str:
    """Generate tool injection prompt with enhanced formatting"""
    if not tools:
        return ""
    
    tool_definitions = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
            
        function_spec = tool.get("function", {}) or {}
        function_name = function_spec.get("name", "unknown")
        function_description = function_spec.get("description", "")
        parameters = function_spec.get("parameters", {}) or {}
        
        # Create structured tool definition
        tool_info = [f"## {function_name}", f"**Purpose**: {function_description}"]
        
        # Add parameter details
        parameter_properties = parameters.get("properties", {}) or {}
        required_parameters = set(parameters.get("required", []) or [])
        
        if parameter_properties:
            tool_info.append("**Parameters**:")
            for param_name, param_details in parameter_properties.items():
                param_type = (param_details or {}).get("type", "any")
                param_desc = (param_details or {}).get("description", "")
                requirement_flag = "**Required**" if param_name in required_parameters else "*Optional*"
                tool_info.append(f"- `{param_name}` ({param_type}) - {requirement_flag}: {param_desc}")
        
        tool_definitions.append("\n".join(tool_info))
    
    if not tool_definitions:
        return ""
    
    # Build comprehensive tool prompt
    prompt_template = (
        "\n\n# AVAILABLE FUNCTIONS\n" +
        "\n\n---\n".join(tool_definitions) +
        "\n\n# USAGE INSTRUCTIONS\n"
        "When you need to execute a function, respond ONLY with a JSON object containing tool_calls:\n"
        "```json\n"
        "{\n"
        '  "tool_calls": [\n'
        "    {\n"
        '      "id": "call_" + unique_id,\n'
        '      "type": "function",\n'
        '      "function": {\n'
        '        "name": "function_name",\n'
        '        "arguments": {\n'
        '          "param1": "value1"\n'
        '        }\n'
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "```\n"
        "Important: No explanatory text before or after the JSON.\n"
    )
    
    return prompt_template


def process_messages_with_tools(
    messages: List[Dict[str, Any]], 
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Process messages and inject tool prompts"""
    processed: List[Dict[str, Any]] = []
    
    if tools and ServerConfig.TOOL_SUPPORT and (tool_choice != "none"):
        tools_prompt = generate_tool_prompt(tools)
        has_system = any(m.get("role") == "system" for m in messages)
        
        if has_system:
            for m in messages:
                if m.get("role") == "system":
                    mm = dict(m)
                    content = mm.get("content", "")
                    if content is None:
                        content = ""
                    mm["content"] = content + tools_prompt
                    processed.append(mm)
                else:
                    processed.append(m)
        else:
            processed = [{"role": "system", "content": "你是一个有用的助手。" + tools_prompt}] + messages
        
        # Add tool choice hints
        if tool_choice in ("required", "auto"):
            if processed and processed[-1].get("role") == "user":
                last = dict(processed[-1])
                content = last.get("content", "")
                if content is None:
                    content = ""
                last["content"] = content + "\n\n请根据需要使用提供的工具函数。"
                processed[-1] = last
        elif isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
            fname = (tool_choice.get("function") or {}).get("name")
            if fname and processed and processed[-1].get("role") == "user":
                last = dict(processed[-1])
                content = last.get("content", "")
                if content is None:
                    content = ""
                last["content"] = content + f"\n\n请使用 {fname} 函数来处理这个请求。"
                processed[-1] = last
    else:
        processed = list(messages)
    
    # Handle tool/function messages
    final_msgs: List[Dict[str, Any]] = []
    for m in processed:
        role = m.get("role")
        if role in ("tool", "function"):
            tool_name = m.get("name", "unknown")
            tool_content = m.get("content", "")
            if isinstance(tool_content, dict):
                tool_content = json.dumps(tool_content, ensure_ascii=False)
            elif tool_content is None:
                tool_content = ""
            
            # 确保内容不为空且不包含 None
            content = f"工具 {tool_name} 返回结果:\n```json\n{tool_content}\n```"
            if not content.strip():
                content = f"工具 {tool_name} 执行完成"
                
            final_msgs.append({
                "role": "assistant",
                "content": content,
            })
        else:
            final_msgs.append(m)
    
    return final_msgs


# Tool Extraction Patterns
TOOL_CALL_FENCE_PATTERN = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
TOOL_CALL_INLINE_PATTERN = re.compile(r"(\{[^{}]{0,10000}\"tool_calls\".*?\})", re.DOTALL)
FUNCTION_CALL_PATTERN = re.compile(r"调用函数\s*[：:]\s*([\w\-\.]+)\s*(?:参数|arguments)[：:]\s*(\{.*?\})", re.DOTALL)


def extract_tool_invocations(text: str) -> Optional[List[Dict[str, Any]]]:
    """Extract tool invocations from response text"""
    if not text:
        return None
    
    # Limit scan size for performance
    scannable_text = text[:ServerConfig.SCAN_LIMIT]
    
    # Attempt 1: Extract from JSON code blocks
    json_blocks = TOOL_CALL_FENCE_PATTERN.findall(scannable_text)
    for json_block in json_blocks:
        try:
            parsed_data = json.loads(json_block)
            tool_calls = parsed_data.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                return tool_calls
        except (json.JSONDecodeError, AttributeError):
            continue
    
    # Attempt 2: Extract inline JSON objects
    inline_match = TOOL_CALL_INLINE_PATTERN.search(scannable_text)
    if inline_match:
        try:
            inline_json = inline_match.group(1)
            parsed_data = json.loads(inline_json)
            tool_calls = parsed_data.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                return tool_calls
        except (json.JSONDecodeError, AttributeError):
            pass
    
    # Attempt 3: Parse natural language function calls
    natural_lang_match = FUNCTION_CALL_PATTERN.search(scannable_text)
    if natural_lang_match:
        function_name = natural_lang_match.group(1).strip()
        arguments_str = natural_lang_match.group(2).strip()
        try:
            # Validate JSON format
            json.loads(arguments_str)
            return [{
                "id": f"invoke_{int(time.time() * 1000000)}",
                "type": "function",
                "function": {
                    "name": function_name,
                    "arguments": arguments_str
                }
            }]
        except json.JSONDecodeError:
            return None
    
    return None


def remove_tool_json_content(text: str) -> str:
    """Remove tool JSON content from response text"""
    def remove_tool_call_block(match: re.Match) -> str:
        json_content = match.group(1)
        try:
            parsed_data = json.loads(json_content)
            if "tool_calls" in parsed_data:
                return ""
        except (json.JSONDecodeError, AttributeError):
            pass
        return match.group(0)
    
    # Remove fenced tool JSON blocks
    cleaned_text = TOOL_CALL_FENCE_PATTERN.sub(remove_tool_call_block, text)
    # Remove inline tool JSON
    cleaned_text = TOOL_CALL_INLINE_PATTERN.sub("", cleaned_text)
    return cleaned_text.strip()


# =============================================================================
# Utility Functions
# =============================================================================

def debug_log(message: str, *args) -> None:
    """Log debug message if debug mode is enabled"""
    if ServerConfig.DEBUG_LOGGING:
        if args:
            print(f"[DEBUG] {message % args}")
        else:
            print(f"[DEBUG] {message}")


def generate_request_ids() -> Tuple[str, str]:
    """Generate unique IDs for chat and message"""
    timestamp = int(time.time())
    chat_id = f"{timestamp * 1000}-{timestamp}"
    msg_id = str(timestamp * 1000000)
    return chat_id, msg_id


def get_browser_headers(referer_chat_id: str = "") -> Dict[str, str]:
    """Get browser headers for API requests"""
    headers = ServerConfig.CLIENT_HEADERS.copy()
    
    if referer_chat_id:
        headers["Referer"] = f"{ServerConfig.CLIENT_HEADERS['Origin']}/c/{referer_chat_id}"
    
    return headers


def get_anonymous_token() -> str:
    """Get anonymous token for authentication"""
    headers = get_browser_headers()
    headers.update({
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": f"{ServerConfig.CLIENT_HEADERS['Origin']}/",
    })
    
    try:
        response = requests.get(
            f"{ServerConfig.CLIENT_HEADERS['Origin']}/api/v1/auths/",
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
    if ServerConfig.ANONYMOUS_MODE:
        try:
            token = get_anonymous_token()
            debug_log(f"匿名token获取成功: {token[:10]}...")
            return token
        except Exception as e:
            debug_log(f"匿名token获取失败，回退固定token: {e}")
    
    return ServerConfig.BACKUP_TOKEN


def transform_thinking_content(content: str) -> str:
    """Transform thinking content according to configuration"""
    # Remove summary tags
    content = re.sub(r'(?s)<summary>.*?</summary>', '', content)
    # Clean up remaining tags
    content = content.replace("</thinking>", "").replace("<Full>", "").replace("</Full>", "")
    content = content.strip()
    
    if ServerConfig.THINKING_PROCESSING == "think":
        content = re.sub(r'<details[^>]*>', '<think>', content)
        content = content.replace("</details>", "</think>")
    elif ServerConfig.THINKING_PROCESSING == "strip":
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
        model=ServerConfig.PRIMARY_MODEL,
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
    
    debug_log(f"调用上游API: {ServerConfig.API_ENDPOINT}")
    debug_log(f"上游请求体: {upstream_req.model_dump_json()}")
    
    response = requests.post(
        ServerConfig.API_ENDPOINT,
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
        if ServerConfig.DEBUG_LOGGING:
            debug_log(f"上游错误响应: {response.text}")


class StreamResponseHandler(ResponseHandler):
    """Handler for streaming responses"""
    
    def __init__(self, upstream_req: UpstreamRequest, chat_id: str, auth_token: str, has_tools: bool = False):
        super().__init__(upstream_req, chat_id, auth_token)
        self.has_tools = has_tools
        self.buffered_content = ""
        self.tool_calls = None
    
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
            model=ServerConfig.PRIMARY_MODEL,
            delta=Delta(role="assistant")
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"
        
        # Process stream
        debug_log("开始读取上游SSE流")
        sent_initial_answer = False
        
        with SSEParser(response, debug_mode=ServerConfig.DEBUG_LOGGING) as parser:
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
        content = upstream_data.data.delta_content or upstream_data.data.edit_content
        
        if not content:
            return
        
        # Transform thinking content
        if upstream_data.data.phase == "thinking":
            content = transform_thinking_content(content)
        
        # Buffer content if tools are enabled
        if self.has_tools:
            self.buffered_content += content
        else:
            # Handle initial answer content
            if (not sent_initial_answer and 
                upstream_data.data.edit_content and 
                upstream_data.data.phase == "answer"):
                
                content = self._extract_edit_content(upstream_data.data.edit_content)
                if content:
                    debug_log(f"发送普通内容: {content}")
                    chunk = create_openai_response_chunk(
                        model=ServerConfig.PRIMARY_MODEL,
                        delta=Delta(content=content)
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    sent_initial_answer = True
            
            # Handle delta content
            if upstream_data.data.delta_content:
                if content:
                    if upstream_data.data.phase == "thinking":
                        debug_log(f"发送思考内容: {content}")
                        chunk = create_openai_response_chunk(
                            model=ServerConfig.PRIMARY_MODEL,
                            delta=Delta(reasoning_content=content)
                        )
                    else:
                        debug_log(f"发送普通内容: {content}")
                        chunk = create_openai_response_chunk(
                            model=ServerConfig.PRIMARY_MODEL,
                            delta=Delta(content=content)
                        )
                    yield f"data: {chunk.model_dump_json()}\n\n"
    
    def _extract_edit_content(self, edit_content: str) -> str:
        """Extract content from edit_content field"""
        parts = edit_content.split("</details>")
        return parts[1] if len(parts) > 1 else ""
    
    def _send_end_chunk(self) -> Generator[str, None, None]:
        """Send end chunk and DONE signal"""
        if self.has_tools:
            # Try to extract tool calls from buffered content
            self.tool_calls = extract_tool_invocations(self.buffered_content)
            
            if self.tool_calls:
                # Send tool calls
                tool_calls_list = []
                for i, tc in enumerate(self.tool_calls):
                    tool_calls_list.append({
                        "index": i,
                        "id": tc.get("id"),
                        "type": tc.get("type", "function"),
                        "function": tc.get("function", {}),
                    })
                
                out_chunk = create_openai_response_chunk(
                    model=ServerConfig.PRIMARY_MODEL,
                    delta=Delta(tool_calls=tool_calls_list)
                )
                yield f"data: {out_chunk.model_dump_json()}\n\n"
                finish_reason = "tool_calls"
            else:
                # Send regular content
                trimmed_content = remove_tool_json_content(self.buffered_content)
                if trimmed_content:
                    content_chunk = create_openai_response_chunk(
                        model=ServerConfig.PRIMARY_MODEL,
                        delta=Delta(content=trimmed_content)
                    )
                    yield f"data: {content_chunk.model_dump_json()}\n\n"
                finish_reason = "stop"
        else:
            finish_reason = "stop"
        
        # Send final chunk
        end_chunk = create_openai_response_chunk(
            model=ServerConfig.PRIMARY_MODEL,
            finish_reason=finish_reason
        )
        yield f"data: {end_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
        debug_log("流式响应完成")


class NonStreamResponseHandler(ResponseHandler):
    """Handler for non-streaming responses"""
    
    def __init__(self, upstream_req: UpstreamRequest, chat_id: str, auth_token: str, has_tools: bool = False):
        super().__init__(upstream_req, chat_id, auth_token)
        self.has_tools = has_tools
    
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
        
        with SSEParser(response, debug_mode=ServerConfig.DEBUG_LOGGING) as parser:
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
        
        # Handle tool calls for non-streaming
        tool_calls = None
        finish_reason = "stop"
        message_content = final_content
        
        if self.has_tools:
            tool_calls = extract_tool_invocations(final_content)
            if tool_calls:
                # Content must be null when tool_calls are present (OpenAI spec)
                message_content = None
                finish_reason = "tool_calls"
            else:
                # Remove tool JSON from content
                message_content = remove_tool_json_content(final_content)
        
        # Build response
        response_data = OpenAIResponse(
            id=f"chatcmpl-{int(time.time())}",
            object="chat.completion",
            created=int(time.time()),
            model=ServerConfig.PRIMARY_MODEL,
            choices=[Choice(
                index=0,
                message=Message(
                    role="assistant",
                    content=message_content,
                    tool_calls=tool_calls
                ),
                finish_reason=finish_reason
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
                id=ServerConfig.PRIMARY_MODEL,
                created=current_time,
                owned_by="z.ai"
            ),
            Model(
                id=ServerConfig.THINKING_MODEL,
                created=current_time,
                owned_by="z.ai"
            ),
            Model(
                id=ServerConfig.SEARCH_MODEL,
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
    
    try:
        # Validate API key
        if not authorization.startswith("Bearer "):
            debug_log("缺少或无效的Authorization头")
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        api_key = authorization[7:]
        if api_key != ServerConfig.AUTH_TOKEN:
            debug_log(f"无效的API key: {api_key}")
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        debug_log("API key验证通过")
        debug_log(f"请求解析成功 - 模型: {request.model}, 流式: {request.stream}, 消息数: {len(request.messages)}")
        
        # Generate IDs
        chat_id, msg_id = generate_request_ids()
        
        # Process messages with tools
        processed_messages = process_messages_with_tools(
            [m.model_dump() for m in request.messages],
            request.tools,
            request.tool_choice
        )
        
        # Convert back to Message objects
        upstream_messages = []
        for msg in processed_messages:
            content = msg.get("content")
            # Ensure content is not None for Message model
            if content is None:
                content = ""
            
            upstream_messages.append(Message(
                role=msg["role"],
                content=content,
                reasoning_content=msg.get("reasoning_content")
            ))
        
        # Determine model features
        is_thinking = request.model == ServerConfig.THINKING_MODEL
        is_search = request.model == ServerConfig.SEARCH_MODEL
        search_mcp = "deep-web-search" if is_search else ""
        
        # Build upstream request
        upstream_req = UpstreamRequest(
            stream=True,  # Always use streaming from upstream
            chat_id=chat_id,
            id=msg_id,
            model="0727-360B-API",  # Actual upstream model ID
            messages=upstream_messages,
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
        
        # Check if tools are enabled and present
        has_tools = (ServerConfig.TOOL_SUPPORT and 
                    request.tools and 
                    len(request.tools) > 0 and 
                    request.tool_choice != "none")
        
        # Handle response based on stream flag
        if request.stream:
            handler = StreamResponseHandler(upstream_req, chat_id, auth_token, has_tools)
            return StreamingResponse(
                handler.handle(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            handler = NonStreamResponseHandler(upstream_req, chat_id, auth_token, has_tools)
            return handler.handle()
            
    except HTTPException:
        raise
    except Exception as e:
        debug_log(f"处理请求时发生错误: {str(e)}")
        import traceback
        debug_log(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=ServerConfig.LISTEN_PORT, reload=True)