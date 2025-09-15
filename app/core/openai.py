#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import json
import asyncio
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
from app.utils.token_pool import get_token_pool

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
    role = request.messages[0].role if request.messages else "unknown"
    logger.info(f"😶‍🌫️ 收到 客户端 请求 - 模型: {request.model}, 流式: {request.stream}, 消息数: {len(request.messages)}, 角色: {role}, 工具数: {len(request.tools) if request.tools else 0}")

    try:
        # Validate API key (skip if SKIP_AUTH_TOKEN is enabled)
        if not settings.SKIP_AUTH_TOKEN:
            if not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

            api_key = authorization[7:]
            if api_key != settings.AUTH_TOKEN:
                raise HTTPException(status_code=401, detail="Invalid API key")

        # 使用新的转换器转换请求
        request_dict = request.model_dump()
        logger.info("🔄 开始转换请求格式: OpenAI -> Z.AI")
        
        transformed = await transformer.transform_request_in(request_dict)
        # logger.debug(f"🔄 转换后 Z.AI 请求体: {json.dumps(transformed['body'], ensure_ascii=False, indent=2)}")

        # 调用上游API
        async def stream_response():
            """流式响应生成器（包含重试机制）"""
            retry_count = 0
            last_error = None
            current_token = transformed.get("token", "")  # 获取当前使用的token

            while retry_count <= settings.MAX_RETRIES:
                try:
                    # 如果是重试，重新获取令牌并更新请求
                    if retry_count > 0:
                        delay = settings.RETRY_DELAY
                        logger.warning(f"重试请求 ({retry_count}/{settings.MAX_RETRIES}) - 等待 {delay:.1f}s")
                        await asyncio.sleep(delay)

                        # 标记前一个token失败（如果不是匿名模式）
                        if current_token and not settings.ANONYMOUS_MODE:
                            transformer.mark_token_failure(current_token, Exception(f"Retry {retry_count}: {last_error}"))

                        # 重新获取令牌
                        logger.info("🔑 重新获取令牌用于重试...")
                        new_token = await transformer.get_token()
                        if not new_token:
                            logger.error("❌ 重试时无法获取有效的认证令牌")
                            raise Exception("重试时无法获取有效的认证令牌")
                        transformed["config"]["headers"]["Authorization"] = f"Bearer {new_token}"
                        current_token = new_token

                    async with httpx.AsyncClient(timeout=60.0) as client:
                        # 发送请求到上游
                        logger.info(f"🎯 发送请求到 Z.AI: {transformed['config']['url']}")
                        async with client.stream(
                            "POST",
                            transformed["config"]["url"],
                            json=transformed["body"],
                            headers=transformed["config"]["headers"],
                        ) as response:
                            # 检查响应状态码
                            if response.status_code == 400:
                                # 400 错误，触发重试
                                error_text = await response.aread()
                                error_msg = error_text.decode('utf-8', errors='ignore')
                                logger.warning(f"❌ 上游返回 400 错误 (尝试 {retry_count + 1}/{settings.MAX_RETRIES + 1})")

                                retry_count += 1
                                last_error = f"400 Bad Request: {error_msg}"

                                # 如果还有重试机会，继续循环
                                if retry_count <= settings.MAX_RETRIES:
                                    continue
                                else:
                                    # 达到最大重试次数，抛出错误
                                    logger.error(f"❌ 达到最大重试次数 ({settings.MAX_RETRIES})，请求失败")
                                    error_response = {
                                        "error": {
                                            "message": f"Request failed after {settings.MAX_RETRIES} retries: {last_error}",
                                            "type": "upstream_error",
                                            "code": 400
                                        }
                                    }
                                    yield f"data: {json.dumps(error_response)}\n\n"
                                    yield "data: [DONE]\n\n"
                                    return

                            elif response.status_code != 200:
                                # 其他错误，直接返回
                                logger.error(f"❌ 上游返回错误: {response.status_code}")
                                error_text = await response.aread()
                                error_msg = error_text.decode('utf-8', errors='ignore')
                                logger.error(f"❌ 错误详情: {error_msg}")

                                error_response = {
                                    "error": {
                                        "message": f"Upstream error: {response.status_code}",
                                        "type": "upstream_error",
                                        "code": response.status_code
                                    }
                                }
                                yield f"data: {json.dumps(error_response)}\n\n"
                                yield "data: [DONE]\n\n"
                                return

                            # 200 成功，处理响应
                            logger.info(f"✅ Z.AI 响应成功，开始处理 SSE 流")
                            if retry_count > 0:
                                logger.info(f"✨ 第 {retry_count} 次重试成功")

                            # 标记token使用成功（如果不是匿名模式）
                            if current_token and not settings.ANONYMOUS_MODE:
                                transformer.mark_token_success(current_token)

                            # 初始化工具处理器（如果需要）
                            has_tools = transformed["body"].get("tools") is not None
                            tool_handler = None
                            if has_tools:
                                chat_id = transformed["body"]["chat_id"]
                                model = request.model
                                tool_handler = SSEToolHandler(chat_id, model)
                                logger.info(f"🔧 初始化工具处理器: {len(transformed['body'].get('tools', []))} 个工具")

                            # 处理状态
                            has_thinking = False
                            thinking_signature = None

                            # 处理SSE流
                            buffer = ""
                            line_count = 0
                            logger.debug("📡 开始接收 SSE 流数据...")

                            async for line in response.aiter_lines():
                                line_count += 1
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

                                        logger.debug(f"📦 解析数据块: {chunk_str[:1000]}..." if len(chunk_str) > 1000 else f"📦 解析数据块: {chunk_str}")

                                        try:
                                            chunk = json.loads(chunk_str)

                                            if chunk.get("type") == "chat:completion":
                                                data = chunk.get("data", {})
                                                phase = data.get("phase")

                                                # 记录每个阶段（只在阶段变化时记录）
                                                if phase and phase != getattr(stream_response, '_last_phase', None):
                                                    logger.info(f"📈 SSE 阶段: {phase}")
                                                    stream_response._last_phase = phase

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
                                                        output_data = f"data: {json.dumps(content_chunk)}\n\n"
                                                        logger.debug(f"➡️ 输出内容块到客户端: {output_data[:1000]}...")
                                                        yield output_data

                                                    # 处理完成
                                                    if data.get("usage"):
                                                        logger.info(f"📦 完成响应 - 使用统计: {json.dumps(data['usage'])}")

                                                        # 只有在非工具调用模式下才发送普通完成信号
                                                        if not tool_handler or not tool_handler.has_tool_call:
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
                                                            finish_output = f"data: {json.dumps(finish_chunk)}\n\n"
                                                            logger.debug(f"➡️ 发送完成信号: {finish_output[:1000]}...")
                                                            yield finish_output
                                                            logger.debug("➡️ 发送 [DONE]")
                                                            yield "data: [DONE]\n\n"

                                        except json.JSONDecodeError as e:
                                            logger.debug(f"❌ JSON解析错误: {e}, 内容: {chunk_str[:1000]}")
                                        except Exception as e:
                                            logger.error(f"❌ 处理chunk错误: {e}")

                            # 确保发送结束信号
                            if not tool_handler or not tool_handler.has_tool_call:
                                logger.debug("📤 发送最终 [DONE] 信号")
                                yield "data: [DONE]\n\n"

                            logger.info(f"✅ SSE 流处理完成，共处理 {line_count} 行数据")
                            # 成功处理完成，退出重试循环
                            return

                except Exception as e:
                    logger.error(f"❌ 流处理错误: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

                    # 标记token失败（如果不是匿名模式）
                    if current_token and not settings.ANONYMOUS_MODE:
                        transformer.mark_token_failure(current_token, e)

                    # 检查是否还可以重试
                    retry_count += 1
                    last_error = str(e)

                    if retry_count > settings.MAX_RETRIES:
                        # 达到最大重试次数，返回错误
                        logger.error(f"❌ 达到最大重试次数 ({settings.MAX_RETRIES})，流处理失败")
                        error_response = {
                            "error": {
                                "message": f"Stream processing failed after {settings.MAX_RETRIES} retries: {last_error}",
                                "type": "stream_error"
                            }
                        }
                        yield f"data: {json.dumps(error_response)}\n\n"
                        yield "data: [DONE]\n\n"
                        return

        # 返回流式响应
        logger.info("🚀 启动 SSE 流式响应")
        
        # 创建一个包装的生成器来追踪数据流
        async def logged_stream():
            chunk_count = 0
            try:
                logger.debug("📤 开始向客户端流式传输数据...")
                async for chunk in stream_response():
                    chunk_count += 1
                    logger.debug(f"📤 发送块[{chunk_count}]: {chunk[:1000]}..." if len(chunk) > 1000 else f"  📤 发送块[{chunk_count}]: {chunk}")
                    yield chunk
                logger.info(f"✅ 流式传输完成，共发送 {chunk_count} 个数据块")
            except Exception as e:
                logger.error(f"❌ 流式传输中断: {e}")
                raise
        
        return StreamingResponse(
            logged_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 处理请求时发生错误: {str(e)}")
        import traceback

        logger.error(f"❌ 错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/v1/token-pool/status")
async def get_token_pool_status():
    """获取token池状态信息"""
    try:
        token_pool = get_token_pool()
        if not token_pool:
            return {
                "status": "disabled",
                "message": "Token池未初始化，当前仅使用匿名模式",
                "anonymous_mode": settings.ANONYMOUS_MODE,
                "auth_tokens_file": settings.AUTH_TOKENS_FILE,
                "auth_tokens_configured": len(settings.auth_token_list) > 0
            }

        pool_status = token_pool.get_pool_status()
        return {
            "status": "active",
            "pool_info": pool_status,
            "config": {
                "anonymous_mode": settings.ANONYMOUS_MODE,
                "failure_threshold": settings.TOKEN_FAILURE_THRESHOLD,
                "recovery_timeout": settings.TOKEN_RECOVERY_TIMEOUT,
                "health_check_interval": settings.TOKEN_HEALTH_CHECK_INTERVAL
            }
        }
    except Exception as e:
        logger.error(f"获取token池状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get token pool status: {str(e)}")


@router.post("/v1/token-pool/health-check")
async def trigger_health_check():
    """手动触发token池健康检查"""
    try:
        token_pool = get_token_pool()
        if not token_pool:
            raise HTTPException(status_code=404, detail="Token池未初始化")

        # 记录开始时间
        import time
        start_time = time.time()

        logger.info("🔍 API触发Token池健康检查...")
        await token_pool.health_check_all()

        # 计算耗时
        duration = time.time() - start_time

        pool_status = token_pool.get_pool_status()

        # 统计健康检查结果 - 基于实际的健康状态
        total_tokens = pool_status['total_tokens']
        healthy_tokens = sum(1 for token_info in pool_status['tokens'] if token_info['is_healthy'])
        unhealthy_tokens = total_tokens - healthy_tokens

        # 构建响应
        response = {
            "status": "completed",
            "message": f"健康检查已完成，耗时 {duration:.2f} 秒",
            "summary": {
                "total_tokens": total_tokens,
                "healthy_tokens": healthy_tokens,
                "unhealthy_tokens": unhealthy_tokens,
                "health_rate": f"{(healthy_tokens/total_tokens*100):.1f}%" if total_tokens > 0 else "0%",
                "duration_seconds": round(duration, 2)
            },
            "pool_info": pool_status
        }

        # 添加建议
        if unhealthy_tokens > 0:
            response["recommendations"] = []
            if unhealthy_tokens == total_tokens:
                response["recommendations"].append("所有token都不健康，请检查token配置和网络连接")
            else:
                response["recommendations"].append(f"有 {unhealthy_tokens} 个token不健康，建议检查这些token的有效性")

        logger.info(f"✅ API健康检查完成: {healthy_tokens}/{total_tokens} 个token健康")
        return response
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.post("/v1/token-pool/update")
async def update_token_pool(tokens: List[str]):
    """动态更新token池"""
    try:
        from app.utils.token_pool import update_token_pool

        # 过滤空token
        valid_tokens = [token.strip() for token in tokens if token.strip()]
        if not valid_tokens:
            raise HTTPException(status_code=400, detail="至少需要提供一个有效的token")

        update_token_pool(valid_tokens)

        token_pool = get_token_pool()
        pool_status = token_pool.get_pool_status() if token_pool else None

        return {
            "status": "updated",
            "message": f"Token池已更新，共 {len(valid_tokens)} 个token",
            "pool_info": pool_status
        }
    except Exception as e:
        logger.error(f"更新token池失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update token pool: {str(e)}")
