#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SSE Tool Handler - 处理工具调用的SSE流
实现glm_block分割和工具参数累积逻辑
"""

import json
import time
import uuid
from typing import Dict, Any, Optional, Generator, List
from dataclasses import dataclass, field

from app.utils.logger import get_logger

logger = get_logger()


@dataclass
class ToolCallState:
    """工具调用状态管理"""

    has_tool_call: bool = False
    tool_args: str = ""
    tool_id: str = ""
    tool_name: str = ""
    tool_calls: List[Dict] = field(default_factory=list)
    tool_call_index: int = 0
    tool_call_usage: Optional[Dict] = None
    tool_call_buffer: str = ""  # 累积buffer用于处理分割的内容
    is_first_block: bool = True  # 是否是第一个块


class SSEToolHandler:
    """
    SSE工具处理器 - 实现工具调用逻辑
    包含glm_block分割解析和参数累积机制
    """

    def __init__(self, chat_id: str, model: str):
        self.chat_id = chat_id
        self.model = model
        self.state = ToolCallState()
        self.has_thinking = False
        self.content_index = 0

    def process_tool_call_phase(self, data: Dict[str, Any], is_stream: bool = True) -> Generator[str, None, None]:
        """
        处理tool_call阶段
        """
        if not self.state.has_tool_call:
            self.state.has_tool_call = True
            logger.debug("进入工具调用阶段")

        edit_content = data.get("edit_content", "")
        if not edit_content:
            return

        # 分割glm_block块
        blocks = edit_content.split("<glm_block >")

        for index, block in enumerate(blocks):
            if not block or "</glm_block>" not in block:
                continue

            if index == 0:
                # 第一个块：提取到"result"之前的内容作为参数片段
                if '"result"' in edit_content:
                    # 提取到result之前的内容（去掉", "result"）
                    args_fragment = edit_content[: edit_content.index('"result"') - 3]
                    self.state.tool_args += args_fragment
                    logger.debug(f"从第一个块提取参数片段: {args_fragment}")
                else:
                    # 如果没有result字段，这是一个分片的参数
                    # 提取到</glm_block>之前的所有内容（但不包括</glm_block>）
                    if "</glm_block>" in block:
                        end_idx = block.index("</glm_block>")
                        args_fragment = block[:end_idx]
                    else:
                        args_fragment = block

                    # 直接累积参数片段，不做修改
                    self.state.tool_args += args_fragment
                    logger.debug(f"累积参数片段: {args_fragment}")
            else:
                # 后续块：包含工具元数据
                try:
                    # 提取块内容（去掉</glm_block>）
                    block_content = block[: block.index("</glm_block>")]
                    content = json.loads(block_content)
                    metadata = content.get("data", {}).get("metadata", {})

                    # 新工具调用
                    tool_id = metadata.get("id", "")
                    tool_name = metadata.get("name", "")
                    arguments = metadata.get("arguments", {})

                    if tool_id and tool_id != self.state.tool_id:
                        # 如果有前一个工具调用未完成，先完成它
                        if self.state.tool_id and self.state.tool_args:
                            # 补充最后的引号
                            if not self.state.tool_args.endswith("}"):
                                self.state.tool_args += '"'
                            yield from self._complete_tool_call(is_stream)

                        # 保存新工具信息s
                        self.state.tool_id = tool_id
                        self.state.tool_name = tool_name
                        # 开始新的参数累积（去掉最后的}以便后续累积）
                        self.state.tool_args = json.dumps(arguments, ensure_ascii=False)[:-1]

                        logger.debug(f"新工具调用: {tool_name}(id={tool_id})")
                        logger.debug(f"初始参数: {self.state.tool_args}")

                        if is_stream:
                            yield self._create_tool_start_chunk()

                        self.content_index += 1

                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"解析工具块失败: {e}, block: {block_content}")

        # 检查参数是否完整
        if self.state.tool_args:
            try:
                # 尝试补充}并解析
                test_args = (
                    self.state.tool_args + "}" if not self.state.tool_args.endswith("}") else self.state.tool_args
                )
                json.loads(test_args)
                self.state.tool_args_complete = True
                logger.debug(f"参数完整: {test_args}")
            except json.JSONDecodeError:
                logger.debug(f"参数未完整，当前长度: {len(self.state.tool_args)}")

    def _complete_tool_call(self, is_stream: bool) -> Generator[str, None, None]:
        """完成当前工具调用"""
        try:
            # 尝试解析参数
            # 参数应该已经在process_other_phase中补充完整
            params = None

            try:
                params = json.loads(self.state.tool_args)
                logger.debug(f"参数解析成功: {json.dumps(params, ensure_ascii=False)[:100]}")
            except json.JSONDecodeError as e:
                logger.error(f"解析失败: {e}")
                logger.error(f"原始参数: {self.state.tool_args[:200]}")
                # 使用空参数
                params = {}

            logger.debug(f"完成工具调用: {self.state.tool_name} with params: {params}")

            if is_stream:
                # 发送参数
                yield self._create_tool_arguments_chunk(params)

        except Exception as e:
            logger.error(f"处理工具参数异常: {e}")
        finally:
            # 重置状态
            self.state.tool_args = ""
            self.state.tool_id = ""
            self.state.tool_name = ""
            self.state.tool_args_complete = False

    def process_other_phase(self, data: Dict[str, Any], is_stream: bool = True) -> Generator[str, None, None]:
        """
        处理other阶段
        主要处理工具调用的结束
        """
        edit_content = data.get("edit_content", "")
        usage = data.get("usage")

        # 保存usage（如果在工具调用模式）
        if self.state.has_tool_call and usage:
            self.state.tool_call_usage = usage
            logger.debug(f"保存工具调用usage: {usage}")

        # 检查工具调用结束标记
        if self.state.has_tool_call and edit_content and edit_content.startswith("null,"):
            logger.debug("检测到工具调用结束标记: null,")

            # 如果有未完成的工具调用，完成它
            if self.state.tool_id and self.state.tool_args:
                # 补充结束引号
                self.state.tool_args += '"'

                logger.debug(f"准备完成工具调用，当前参数: {self.state.tool_args}")
                yield from self._complete_tool_call(is_stream)

            # 发送完成信号
            if is_stream:
                yield self._create_tool_finish_chunk()
                yield "data: [DONE]\n\n"

            # 重置所有状态
            self.state.has_tool_call = False
            self.state.tool_call_usage = None
            self.state.tool_call_buffer = ""
            self.state.tool_args = ""
            self.state.tool_id = ""
            self.state.tool_name = ""
            self.state.tool_args_complete = False
            self.state.is_first_block = True

    def _create_tool_start_chunk(self) -> str:
        """创建工具调用开始的chunk"""
        chunk = {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": self.state.tool_id,
                                "type": "function",
                                "function": {"name": self.state.tool_name, "arguments": ""},
                            }
                        ],
                    },
                    "finish_reason": None,
                    "index": self.content_index,
                    "logprobs": None,
                }
            ],
            "created": int(time.time()),
            "id": self.chat_id,
            "model": self.model,
            "object": "chat.completion.chunk",
            "system_fingerprint": "fp_zai_001",
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    def _create_tool_arguments_chunk(self, arguments: Dict) -> str:
        """创建工具参数的chunk"""
        chunk = {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": self.state.tool_id,
                                "type": "function",
                                "function": {"name": None, "arguments": json.dumps(arguments, ensure_ascii=False)},
                            }
                        ],
                    },
                    "finish_reason": None,
                    "index": 0,
                    "logprobs": None,
                }
            ],
            "created": int(time.time()),
            "id": self.chat_id,
            "model": self.model,
            "object": "chat.completion.chunk",
            "system_fingerprint": "fp_zai_001",
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    def _create_tool_finish_chunk(self) -> str:
        """创建工具调用完成的chunk"""
        chunk = {
            "choices": [
                {
                    "delta": {"role": "assistant", "content": None, "tool_calls": []},
                    "finish_reason": "tool_calls",
                    "index": 0,
                    "logprobs": None,
                }
            ],
            "created": int(time.time()),
            "id": self.chat_id,
            "usage": self.state.tool_call_usage,
            "model": self.model,
            "object": "chat.completion.chunk",
            "system_fingerprint": "fp_zai_001",
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
