"""
Anthropic API compatibility endpoints
"""

import json
import time
import uuid
from typing import Generator
import requests
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.models.schemas import (
    AnthropicRequest, Message, UpstreamRequest, ModelItem,
    ContentBlock
)
from app.utils.helpers import debug_log, generate_request_ids, get_auth_token, get_browser_headers, transform_thinking_content

router = APIRouter()


def stream_anthropic_generator(upstream_response: requests.Response, request_id: str, requested_model: str) -> Generator[str, None, None]:
    """生成 Anthropic 兼容的流式响应事件"""
    usage = {"input_tokens": 0, "output_tokens": 0}
    
    start_event = {
        "type": "message_start",
        "message": {
            "id": request_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": requested_model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": usage
        }
    }
    yield f"event: {start_event['type']}\ndata: {json.dumps(start_event['message'])}\n\n"
    
    # 发送 content_block_start 事件
    content_start_data = {
        "type": "content_block_start",
        "index": 0,
        "content_block": {
            "type": "text",
            "text": ""
        }
    }
    yield f"event: content_block_start\ndata: {json.dumps(content_start_data)}\n\n"
    
    # 处理上游响应
    for line in upstream_response.iter_lines():
        if not line.startswith(b"data:"): continue
        data_str = line[5:].strip()
        if not data_str: continue
        try:
            data = json.loads(data_str.decode('utf-8'))
            delta_content = data.get("data", {}).get("delta_content", "")
            phase = data.get("data", {}).get("phase", "")
            
            # 处理内容增量
            if delta_content:
                out_content = transform_thinking_content(delta_content) if phase == "thinking" else delta_content
                if out_content:
                    usage["output_tokens"] += len(out_content) // 4  # 简单估算
                    delta_data = {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {
                            "type": "text_delta",
                            "text": out_content
                        }
                    }
                    yield f"event: content_block_delta\ndata: {json.dumps(delta_data)}\n\n"
            
            # 处理结束
            if data.get("data", {}).get("done", False) or phase == "done":
                # 发送 content_block_stop
                content_stop_data = {
                    "type": "content_block_stop",
                    "index": 0
                }
                yield f"event: content_block_stop\ndata: {json.dumps(content_stop_data)}\n\n"
                
                # 发送 message_delta
                message_delta_data = {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": "end_turn",
                        "stop_sequence": None,
                        "usage": {
                            "input_tokens": usage["input_tokens"],
                            "output_tokens": usage["output_tokens"]
                        }
                    }
                }
                yield f"event: message_delta\ndata: {json.dumps(message_delta_data)}\n\n"
                
                # 发送 message_stop
                yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
                break
                
        except json.JSONDecodeError:
            continue


@router.post("/v1/messages")
async def handle_anthropic_message(
    req: AnthropicRequest,
    x_api_key: str = Header(None, alias="x-api-key"),
    authorization: str = Header(None, alias="authorization")
):
    """Handle Anthropic message requests"""
    debug_log("收到 Anthropic message 请求")
    
    # 验证 API key (skip if SKIP_AUTH_TOKEN is enabled)
    if not settings.SKIP_AUTH_TOKEN:
        api_key = None
        if x_api_key:
            api_key = x_api_key
        elif authorization and authorization.startswith("Bearer "):
            api_key = authorization[7:]
        
        if not api_key or api_key != settings.ANTHROPIC_API_KEY:
            debug_log(f"无效的 API key: {api_key}")
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        debug_log(f"API key 验证通过")
    else:
        debug_log("SKIP_AUTH_TOKEN已启用，跳过API key验证")
    debug_log(f"请求解析成功 - 模型: {req.model}, 流式: {req.stream}, 消息数: {len(req.messages)}")
    
    # 确定上游模型和功能
    upstream_model = "GLM-4.5"
    if req.model == settings.THINKING_MODEL:
        upstream_model = "GLM-4.5-Thinking"
    elif req.model == settings.SEARCH_MODEL:
        upstream_model = "GLM-4.5-Search"
    
    debug_log(f"收到请求 (模型: {req.model}) -> 代理到上游 (模型: {upstream_model})")
    
    # 生成 ID
    chat_id, msg_id = generate_request_ids()
    
    # 转换消息格式
    openai_messages = []
    if req.system:
        # 处理两种格式的 system 内容
        if isinstance(req.system, str):
            # 字符串格式
            system_content = req.system
        else:
            # 对象数组格式
            system_content = ""
            for block in req.system:
                if block.type == "text":
                    system_content += block.text
        
        openai_messages.append({"role": "system", "content": system_content})
    
    for msg in req.messages:
        # 处理两种格式的内容
        if isinstance(msg.content, str):
            # 字符串格式
            text_content = msg.content
        else:
            # 对象数组格式
            text_content = ""
            for block in msg.content:
                if block.type == "text":
                    text_content += block.text
        
        openai_messages.append({
            "role": msg.role,
            "content": text_content
        })
    
    # 构建上游请求
    upstream_messages = []
    for msg in openai_messages:
        content = msg.get("content", "")
        if content is None:
            content = ""
        upstream_messages.append(Message(
            role=msg["role"],
            content=content
        ))
    
    upstream_req = UpstreamRequest(
        stream=True,  # 总是使用上游的流式
        chat_id=chat_id,
        id=msg_id,
        model="0727-360B-API",  # 实际的上游模型 ID
        messages=upstream_messages,
        params={},
        features={"enable_thinking": True},
        background_tasks={
            "title_generation": False,
            "tags_generation": False,
        },
        mcp_servers=[],
        model_item=ModelItem(
            id="0727-360B-API",
            name="GLM-4.5",
            owned_by="openai"
        ),
        tool_servers=[],
        variables={
            "{{USER_NAME}}": "User",
            "{{USER_LOCATION}}": "Unknown",
            "{{CURRENT_DATETIME}}": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    
    # 获取认证 token
    auth_token = get_auth_token()
    
    try:
        # 调用上游 API
        headers = get_browser_headers(chat_id)
        headers["Authorization"] = f"Bearer {auth_token}"
        
        response = requests.post(
            settings.API_ENDPOINT,
            json=upstream_req.model_dump(exclude_none=True),
            headers=headers,
            timeout=60.0,
            stream=True
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        debug_log(f"上游 API 返回错误状态: {e.response.status_code}, 响应: {e.response.text}")
        raise HTTPException(status_code=502, detail="Upstream API error")
    except requests.RequestException as e:
        debug_log(f"请求上游 API 失败: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to call upstream API: {e}")
    
    request_id = f"msg_{uuid.uuid4().hex}"
    
    if req.stream:
        # 流式响应
        return StreamingResponse(
            stream_anthropic_generator(response, request_id, req.model),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    else:
        # 非流式响应
        full_content = ""
        for line in response.iter_lines():
            if not line.startswith(b"data:"): continue
            data_str = line[5:].strip()
            if not data_str: continue
            try:
                data = json.loads(data_str.decode('utf-8'))
                delta_content = data.get("data", {}).get("delta_content", "")
                phase = data.get("data", {}).get("phase", "")
                if delta_content:
                    out_content = transform_thinking_content(delta_content) if phase == "thinking" else delta_content
                    if out_content: full_content += out_content
                if data.get("data", {}).get("done", False) or phase == "done":
                    break
            except json.JSONDecodeError:
                continue
        
        return {
            "id": request_id,
            "type": "message",
            "role": "assistant",
            "model": req.model,
            "content": [{"type": "text", "text": full_content}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 0, "output_tokens": len(full_content) // 4}
        }