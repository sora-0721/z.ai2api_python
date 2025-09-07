#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import json
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
import httpx

from app.core.config import settings
from app.models.schemas import OpenAIRequest, Message, ModelsResponse, Model
from app.utils.logger import get_logger
from app.core.zai_transformer import ZAITransformer, generate_uuid
from app.utils.sse_tool_handler import SSEToolHandler

logger = get_logger()

router = APIRouter()

# 全局转换器实例
transformer = ZAITransformer()


@router.get("/v1/models")
async def list_models():
    """List available models"""
    current_time = int(time.time())
    response = ModelsResponse(
        data=[
            Model(id=settings.PRIMARY_MODEL, created=current_time, owned_by="z.ai"),
            Model(id=settings.THINKING_MODEL, created=current_time, owned_by="z.ai"),
            Model(id=settings.SEARCH_MODEL, created=current_time, owned_by="z.ai"),
            Model(id=settings.AIR_MODEL, created=current_time, owned_by="z.ai"),
        ]
    )
    return response


@router.post("/v1/chat/completions")
async def chat_completions(request: OpenAIRequest, authorization: str = Header(...)):
    """Handle chat completion requests with ZAI transformer"""
    logger.debug("收到chat completions请求")

    try:
        # Validate API key (skip if SKIP_AUTH_TOKEN is enabled)
        if not settings.SKIP_AUTH_TOKEN:
            if not authorization.startswith("Bearer "):
                logger.debug("缺少或无效的Authorization头")
                raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

            api_key = authorization[7:]
            if api_key != settings.AUTH_TOKEN:
                logger.debug(f"无效的API key: {api_key}")
                raise HTTPException(status_code=401, detail="Invalid API key")

            logger.debug(f"API key验证通过")
        else:
            logger.debug("SKIP_AUTH_TOKEN已启用，跳过API key验证")

        logger.debug(f"请求解析成功 - 模型: {request.model}, 流式: {request.stream}, 消息数: {len(request.messages)}")

        # 使用新的转换器转换请求
        request_dict = request.model_dump()
        transformed = await transformer.transform_request_in(request_dict)

        logger.debug(
            f"请求转换完成 - 上游模型: {transformed['body']['model']}, "
            f"enable_thinking: {transformed['body']['features']['enable_thinking']}, "
            f"mcp_servers: {transformed['body'].get('mcp_servers', [])}"
        )

        # 调用上游API
        async def stream_response():
            """流式响应生成器"""
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    # 发送请求到上游
                    async with client.stream(
                        "POST",
                        transformed["config"]["url"],
                        json=transformed["body"],
                        headers=transformed["config"]["headers"],
                    ) as response:
                        if response.status_code != 200:
                            logger.error(f"上游返回错误: {response.status_code}")
                            error_text = await response.aread()
                            logger.error(f"错误详情: {error_text.decode('utf-8', errors='ignore')}")
                            yield f"data: {json.dumps({'error': 'Upstream error'})}\n\n"
                            return

                        # 初始化工具处理器（如果需要）
                        has_tools = transformed["body"].get("tools") is not None
                        tool_handler = None
                        if has_tools:
                            chat_id = transformed["body"]["chat_id"]
                            model = request.model
                            tool_handler = SSEToolHandler(chat_id, model)
                            logger.debug(f"初始化工具处理器 - chat_id: {chat_id}")

                        # 处理状态
                        has_thinking = False
                        thinking_signature = None

                        # 处理SSE流
                        buffer = ""
                        async for line in response.aiter_lines():
                            if not line:
                                continue

                            # 累积到buffer处理完整的数据行
                            buffer += line + "\n"

                            # 检查是否有完整的data行
                            while "\n" in buffer:
                                current_line, buffer = buffer.split("\n", 1)
                                if not current_line.strip():
                                    continue

                                if current_line.startswith("data:"):
                                    chunk_str = current_line[5:].strip()
                                    if not chunk_str or chunk_str == "[DONE]":
                                        if chunk_str == "[DONE]":
                                            yield "data: [DONE]\n\n"
                                        continue

                                    try:
                                        chunk = json.loads(chunk_str)

                                        if chunk.get("type") == "chat:completion":
                                            data = chunk.get("data", {})
                                            phase = data.get("phase")

                                            # 处理工具调用
                                            if phase == "tool_call" and tool_handler:
                                                for output in tool_handler.process_tool_call_phase(data, True):
                                                    yield output

                                            # 处理其他阶段（工具结束）
                                            elif phase == "other" and tool_handler:
                                                for output in tool_handler.process_other_phase(data, True):
                                                    yield output

                                            # 处理思考内容
                                            elif phase == "thinking":
                                                if not has_thinking:
                                                    has_thinking = True
                                                    # 发送初始角色
                                                    role_chunk = {
                                                        "choices": [
                                                            {
                                                                "delta": {"role": "assistant"},
                                                                "finish_reason": None,
                                                                "index": 0,
                                                                "logprobs": None,
                                                            }
                                                        ],
                                                        "created": int(time.time()),
                                                        "id": transformed["body"]["chat_id"],
                                                        "model": request.model,
                                                        "object": "chat.completion.chunk",
                                                        "system_fingerprint": "fp_zai_001",
                                                    }
                                                    yield f"data: {json.dumps(role_chunk)}\n\n"

                                                delta_content = data.get("delta_content", "")
                                                if delta_content:
                                                    # 处理思考内容格式
                                                    if delta_content.startswith("<details"):
                                                        content = (
                                                            delta_content.split("</summary>\n>")[-1].strip()
                                                            if "</summary>\n>" in delta_content
                                                            else delta_content
                                                        )
                                                    else:
                                                        content = delta_content

                                                    thinking_chunk = {
                                                        "choices": [
                                                            {
                                                                "delta": {
                                                                    "role": "assistant",
                                                                    "thinking": {"content": content},
                                                                },
                                                                "finish_reason": None,
                                                                "index": 0,
                                                                "logprobs": None,
                                                            }
                                                        ],
                                                        "created": int(time.time()),
                                                        "id": transformed["body"]["chat_id"],
                                                        "model": request.model,
                                                        "object": "chat.completion.chunk",
                                                        "system_fingerprint": "fp_zai_001",
                                                    }
                                                    yield f"data: {json.dumps(thinking_chunk)}\n\n"

                                            # 处理答案内容
                                            elif phase == "answer":
                                                edit_content = data.get("edit_content", "")
                                                delta_content = data.get("delta_content", "")

                                                # 处理思考结束和答案开始
                                                if edit_content and "</details>\n" in edit_content:
                                                    if has_thinking:
                                                        # 发送思考签名
                                                        thinking_signature = str(int(time.time() * 1000))
                                                        sig_chunk = {
                                                            "choices": [
                                                                {
                                                                    "delta": {
                                                                        "role": "assistant",
                                                                        "thinking": {
                                                                            "content": "",
                                                                            "signature": thinking_signature,
                                                                        },
                                                                    },
                                                                    "finish_reason": None,
                                                                    "index": 0,
                                                                    "logprobs": None,
                                                                }
                                                            ],
                                                            "created": int(time.time()),
                                                            "id": transformed["body"]["chat_id"],
                                                            "model": request.model,
                                                            "object": "chat.completion.chunk",
                                                            "system_fingerprint": "fp_zai_001",
                                                        }
                                                        yield f"data: {json.dumps(sig_chunk)}\n\n"

                                                    # 提取答案内容
                                                    content_after = edit_content.split("</details>\n")[-1]
                                                    if content_after:
                                                        content_chunk = {
                                                            "choices": [
                                                                {
                                                                    "delta": {
                                                                        "role": "assistant",
                                                                        "content": content_after,
                                                                    },
                                                                    "finish_reason": None,
                                                                    "index": 0,
                                                                    "logprobs": None,
                                                                }
                                                            ],
                                                            "created": int(time.time()),
                                                            "id": transformed["body"]["chat_id"],
                                                            "model": request.model,
                                                            "object": "chat.completion.chunk",
                                                            "system_fingerprint": "fp_zai_001",
                                                        }
                                                        yield f"data: {json.dumps(content_chunk)}\n\n"

                                                # 处理增量内容
                                                elif delta_content:
                                                    # 如果还没有发送角色
                                                    if not has_thinking:
                                                        role_chunk = {
                                                            "choices": [
                                                                {
                                                                    "delta": {"role": "assistant"},
                                                                    "finish_reason": None,
                                                                    "index": 0,
                                                                    "logprobs": None,
                                                                }
                                                            ],
                                                            "created": int(time.time()),
                                                            "id": transformed["body"]["chat_id"],
                                                            "model": request.model,
                                                            "object": "chat.completion.chunk",
                                                            "system_fingerprint": "fp_zai_001",
                                                        }
                                                        yield f"data: {json.dumps(role_chunk)}\n\n"

                                                    content_chunk = {
                                                        "choices": [
                                                            {
                                                                "delta": {
                                                                    "role": "assistant",
                                                                    "content": delta_content,
                                                                },
                                                                "finish_reason": None,
                                                                "index": 0,
                                                                "logprobs": None,
                                                            }
                                                        ],
                                                        "created": int(time.time()),
                                                        "id": transformed["body"]["chat_id"],
                                                        "model": request.model,
                                                        "object": "chat.completion.chunk",
                                                        "system_fingerprint": "fp_zai_001",
                                                    }
                                                    yield f"data: {json.dumps(content_chunk)}\n\n"

                                                # 处理完成
                                                if data.get("usage"):
                                                    finish_chunk = {
                                                        "choices": [
                                                            {
                                                                "delta": {"role": "assistant", "content": ""},
                                                                "finish_reason": "stop",
                                                                "index": 0,
                                                                "logprobs": None,
                                                            }
                                                        ],
                                                        "usage": data["usage"],
                                                        "created": int(time.time()),
                                                        "id": transformed["body"]["chat_id"],
                                                        "model": request.model,
                                                        "object": "chat.completion.chunk",
                                                        "system_fingerprint": "fp_zai_001",
                                                    }
                                                    yield f"data: {json.dumps(finish_chunk)}\n\n"
                                                    yield "data: [DONE]\n\n"

                                    except json.JSONDecodeError as e:
                                        logger.debug(f"JSON解析错误: {e}, 内容: {chunk_str[:100]}")
                                    except Exception as e:
                                        logger.error(f"处理chunk错误: {e}")

                        # 确保发送结束信号
                        if not tool_handler or not tool_handler.state.has_tool_call:
                            yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"流处理错误: {e}")
                import traceback

                logger.error(traceback.format_exc())
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        # 返回流式响应
        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}")
        import traceback

        logger.error(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
