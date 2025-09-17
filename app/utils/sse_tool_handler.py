#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SSE Tool Handler

处理 Z.AI SSE 流数据并转换为 OpenAI 兼容格式的工具调用处理器。

主要功能：
- 解析 glm_block 格式的工具调用
- 从 metadata.arguments 提取完整参数
- 支持多阶段处理：thinking → tool_call → other → answer
- 输出符合 OpenAI API 规范的流式响应
"""

import json
import time
from typing import Dict, Any, Generator
from enum import Enum

from app.utils.logger import get_logger

logger = get_logger()


class SSEPhase(Enum):
    """SSE 处理阶段枚举"""
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    OTHER = "other"
    ANSWER = "answer"


class SSEToolHandler:
    """SSE 工具调用处理器"""

    def __init__(self, model: str, stream: bool = True):
        self.model = model
        self.stream = stream

        # 状态管理
        self.current_phase = None
        self.has_tool_call = False

        # 工具调用状态
        self.tool_id = ""
        self.tool_name = ""
        self.tool_args = ""
        self.tool_call_usage = {}

        # 内容缓冲（简化版）
        self.content_buffer = {}

        logger.debug(f"🔧 初始化工具处理器: model={model}, stream={stream}")

    def process_sse_chunk(self, chunk_data: Dict[str, Any]) -> Generator[str, None, None]:
        """
        处理 SSE 数据块，返回 OpenAI 格式的流式响应

        Args:
            chunk_data: Z.AI SSE 数据块

        Yields:
            str: OpenAI 格式的 SSE 响应行
        """
        try:
            phase = chunk_data.get("phase")
            edit_content = chunk_data.get("edit_content", "")
            delta_content = chunk_data.get("delta_content", "")
            edit_index = chunk_data.get("edit_index")
            usage = chunk_data.get("usage", {})

            # 数据验证
            if not phase:
                logger.warning("⚠️ 收到无效的 SSE 块：缺少 phase 字段")
                return

            # 阶段变化检测和日志
            if phase != self.current_phase:
                logger.info(f"📈 SSE 阶段变化: {self.current_phase} → {phase}")
                content_preview = edit_content or delta_content
                if content_preview:
                    logger.debug(f"   📝 内容预览: {content_preview[:1000]}{'...' if len(content_preview) > 1000 else ''}")
                if edit_index is not None:
                    logger.debug(f"   📍 edit_index: {edit_index}")
                self.current_phase = phase

            # 根据阶段处理
            if phase == SSEPhase.THINKING.value:
                yield from self._process_thinking_phase(delta_content)

            elif phase == SSEPhase.TOOL_CALL.value:
                yield from self._process_tool_call_phase(edit_content)

            elif phase == SSEPhase.OTHER.value:
                yield from self._process_other_phase(usage)

            elif phase == SSEPhase.ANSWER.value:
                yield from self._process_answer_phase(edit_content)
            else:
                logger.warning(f"⚠️ 未知的 SSE 阶段: {phase}")

        except Exception as e:
            logger.error(f"❌ 处理 SSE 块时发生错误: {e}")
            logger.debug(f"   📦 错误块数据: {chunk_data}")
            # 不中断流，继续处理后续块

    def _process_thinking_phase(self, delta_content: str) -> Generator[str, None, None]:
        """处理思考阶段"""
        if not delta_content:
            return

        logger.debug(f"🤔 思考内容: +{len(delta_content)} 字符")

        # 在流模式下输出思考内容
        if self.stream:
            chunk = self._create_content_chunk(delta_content)
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    def _process_tool_call_phase(self, edit_content: str) -> Generator[str, None, None]:
        """处理工具调用阶段"""
        if not edit_content:
            return

        logger.debug(f"🔧 进入工具调用阶段，内容长度: {len(edit_content)}")

        # 检测 glm_block 标记
        if "<glm_block " in edit_content:
            yield from self._handle_glm_blocks(edit_content)

    def _handle_glm_blocks(self, edit_content: str) -> Generator[str, None, None]:
        """处理 glm_block 标记的内容"""
        blocks = edit_content.split('<glm_block ')
        logger.debug(f"📦 分割得到 {len(blocks)} 个块")

        # 处理包含工具元数据的块（跳过第一个空块）
        for index, block in enumerate(blocks):
            if not block.strip() or index == 0:
                continue
            yield from self._process_metadata_block(block)

    def _process_metadata_block(self, block: str) -> Generator[str, None, None]:
        """处理包含工具元数据的块"""
        try:
            # 查找 glm_block 的结束标记
            if '</glm_block>' not in block:
                logger.warning(f"❌ 块格式不正确，缺少结束标记: {block[:50]}...")
                return

            # 提取 JSON 内容
            start_pos = block.find('>')
            end_pos = block.rfind('</glm_block>')

            if start_pos == -1 or end_pos == -1:
                logger.warning(f"❌ 无法找到 JSON 内容边界: {block[:50]}...")
                return

            json_content = block[start_pos + 1:end_pos]
            logger.debug(f"📦 提取的 JSON 内容: {json_content[:100]}...")

            # 解析工具元数据
            metadata_obj = json.loads(json_content)

            if "data" in metadata_obj and "metadata" in metadata_obj["data"]:
                metadata = metadata_obj["data"]["metadata"]

                # 如果已有工具调用，先完成它
                if self.has_tool_call:
                    yield from self._finish_current_tool()

                # 开始新的工具调用
                self.tool_id = metadata.get("id", f"call_{int(time.time() * 1000000)}")
                self.tool_name = metadata.get("name", "unknown")
                self.has_tool_call = True

                # 从 metadata.arguments 获取完整参数
                if "arguments" in metadata:
                    arguments_str = metadata["arguments"]
                    try:
                        # 确保参数格式正确
                        args_obj = json.loads(arguments_str)
                        self.tool_args = json.dumps(args_obj, ensure_ascii=False)
                        logger.debug(f"🎯 新工具调用: {self.tool_name}(id={self.tool_id}), 参数: {self.tool_args}")
                    except json.JSONDecodeError:
                        self.tool_args = arguments_str
                        logger.debug(f"🎯 新工具调用: {self.tool_name}(id={self.tool_id}), 原始参数: {arguments_str}")
                else:
                    self.tool_args = "{}"
                    logger.debug(f"🎯 新工具调用: {self.tool_name}(id={self.tool_id}), 空参数")

                # 输出工具开始信号和参数
                if self.stream:
                    start_chunk = self._create_tool_start_chunk()
                    yield f"data: {json.dumps(start_chunk, ensure_ascii=False)}\n\n"

                    args_chunk = self._create_tool_arguments_chunk(self.tool_args)
                    yield f"data: {json.dumps(args_chunk, ensure_ascii=False)}\n\n"

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"❌ 解析工具元数据失败: {e}, 块内容: {block[:100]}...")

    def _process_other_phase(self, usage: Dict[str, Any]) -> Generator[str, None, None]:
        """处理其他阶段"""
        # 保存使用统计信息
        if usage:
            self.tool_call_usage = usage
            logger.debug(f"📊 保存使用统计: {usage}")

        # 工具调用完成判断：存在 usage 信息且有活跃的工具调用
        if self.has_tool_call and usage:
            logger.info(f"🏁 检测到工具调用完成（基于 usage 信息）")

            # 完成当前工具调用
            yield from self._finish_current_tool()

            # 发送流结束标记
            if self.stream:
                yield "data: [DONE]\n\n"

            # 重置状态
            self._reset_all_state()

    def _process_answer_phase(self, edit_content: str) -> Generator[str, None, None]:
        """处理回答阶段"""
        if not edit_content:
            return

        logger.debug(f"💬 回答内容: +{len(edit_content)} 字符")

        # 输出回答内容
        if self.stream:
            chunk = self._create_content_chunk(edit_content)
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    def _finish_current_tool(self) -> Generator[str, None, None]:
        """完成当前工具调用"""
        if not self.has_tool_call:
            return

        logger.debug(f"✅ 完成工具调用: {self.tool_name}, 参数: {self.tool_args}")

        # 输出完成信号（参数已经在 metadata 解析时输出）
        if self.stream:
            # 发送完成块
            finish_chunk = self._create_tool_finish_chunk()
            yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"

        # 重置工具状态
        self._reset_tool_state()

    def _create_content_chunk(self, content: str) -> Dict[str, Any]:
        """创建内容块"""
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": None
            }]
        }

    def _create_tool_start_chunk(self) -> Dict[str, Any]:
        """创建工具开始块"""
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk", 
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": self.tool_id,
                        "type": "function",
                        "function": {
                            "name": self.tool_name,
                            "arguments": ""
                        }
                    }]
                },
                "finish_reason": None
            }]
        }

    def _create_tool_arguments_chunk(self, arguments: str) -> Dict[str, Any]:
        """创建工具参数块"""
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {
                    "tool_calls": [{
                        "id": self.tool_id,
                        "function": {
                            "arguments": arguments
                        }
                    }]
                },
                "finish_reason": None
            }]
        }

    def _create_tool_finish_chunk(self) -> Dict[str, Any]:
        """创建工具完成块"""
        chunk = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {
                    "tool_calls": []
                },
                "finish_reason": "tool_calls"
            }]
        }
        
        # 添加使用统计（如果有）
        if self.tool_call_usage:
            chunk["usage"] = self.tool_call_usage
            
        return chunk

    def _reset_tool_state(self):
        """重置工具状态"""
        self.tool_id = ""
        self.tool_name = ""
        self.tool_args = ""
        self.has_tool_call = False

    def _reset_all_state(self):
        """重置所有状态"""
        self._reset_tool_state()
        self.current_phase = None
        self.tool_call_usage = {}
        self.content_buffer = {}
        logger.debug("🔄 重置所有处理器状态")
