#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SSE Tool Handler - 处理工具调用的SSE流
"""

import json
import time
from typing import Dict, Any, Optional, Generator

from app.utils.logger import get_logger

logger = get_logger()


class SSEToolHandler:

    def __init__(self, chat_id: str, model: str):
        self.chat_id = chat_id
        self.model = model

        self.has_tool_call = False
        self.tool_args = ""  # 当前工具的参数累积
        self.tool_id = ""  # 当前工具ID
        self.tool_name = ""  # 当前工具名称
        self.tool_call_usage = None  # 工具调用的usage信息
        self.content_index = 0
        self.has_thinking = False

    def process_tool_call_phase(self, data: Dict[str, Any], is_stream: bool = True) -> Generator[str, None, None]:
        """
        处理tool_call阶段
        参考JS的forEach逻辑，每个块独立处理
        """
        if not self.has_tool_call:
            self.has_tool_call = True
            logger.debug("进入工具调用阶段")

        edit_content = data.get("edit_content", "")
        if not edit_content:
            return

        # 分割glm_block块
        blocks = edit_content.split("<glm_block >")

        for index, block in enumerate(blocks):
            if not block:
                continue

            if "</glm_block>" not in block:
                # 这个块不完整，可能是参数片段
                if index == 0:
                    # 第一个块的参数片段
                    self.tool_args += block
                continue

            if index == 0:
                # 第一个块：提取参数片段（到"result"之前）
                if '"result"' in edit_content:
                    args_fragment = edit_content[: edit_content.index('"result"') - 3]
                    self.tool_args += args_fragment
                    logger.debug(f"从第一个块提取参数片段: {args_fragment}")
            else:
                # 后续块：新的工具调用
                # 如果当前有工具正在处理，先完成它
                if self.tool_id:
                    yield from self._finish_current_tool(is_stream)

                # 解析新工具信息
                try:
                    block_content = block[: block.index("</glm_block>")]
                    content = json.loads(block_content)
                    metadata = content.get("data", {}).get("metadata", {})

                    # 开始新工具
                    self.tool_id = metadata.get("id", "")
                    self.tool_name = metadata.get("name", "")
                    arguments = metadata.get("arguments", {})

                    # 累积参数（去掉最后的}以便后续累积）
                    self.tool_args = json.dumps(arguments, ensure_ascii=False)[:-1]

                    logger.debug(f"新工具调用: {self.tool_name}(id={self.tool_id})")
                    logger.debug(f"初始参数: {self.tool_args}")

                    if is_stream:
                        yield self._create_tool_start_chunk()

                    self.content_index += 1

                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"解析工具块失败: {e}")

    def _finish_current_tool(self, is_stream: bool) -> Generator[str, None, None]:
        """完成当前工具调用"""
        if not self.tool_id:
            return

        try:
            # 处理不同的参数状态
            if not self.tool_args or self.tool_args == "{":
                # 空参数或只有开始括号
                params = {}
            else:
                # 尝试补充结束符
                test_args = self.tool_args

                # 检查是否需要补充结束引号
                quote_count = test_args.count('"')
                if quote_count % 2 != 0:
                    test_args += '"'

                # 检查是否需要补充结束括号
                if not test_args.endswith("}"):
                    test_args += "}"

                params = json.loads(test_args)

            logger.debug(f"完成工具调用: {self.tool_name} with params: {params}")

            if is_stream:
                yield self._create_tool_arguments_chunk(params)

        except json.JSONDecodeError as e:
            logger.error(f"工具参数解析失败: {e}, 原始参数: {self.tool_args[:200]}")
            params = {}
            if is_stream:
                yield self._create_tool_arguments_chunk(params)
        finally:
            # 清理当前工具状态
            self.tool_args = ""
            self.tool_id = ""
            self.tool_name = ""

    def process_other_phase(self, data: Dict[str, Any], is_stream: bool = True) -> Generator[str, None, None]:
        """
        处理other阶段
        主要检测工具调用结束
        """
        edit_content = data.get("edit_content", "")
        usage = data.get("usage")

        # 保存usage信息
        if self.has_tool_call and usage:
            self.tool_call_usage = usage
            logger.debug(f"保存工具调用usage: {usage}")

        # 检测工具调用结束标记 "null,"
        if self.has_tool_call and edit_content and edit_content.startswith("null,"):
            logger.debug("检测到工具调用结束标记: null,")

            # 完成最后一个工具调用
            if self.tool_id:
                yield from self._finish_current_tool(is_stream)

            # 发送结束信号
            if is_stream:
                logger.info("    发送工具调用完成信号")
                yield self._create_tool_finish_chunk()
                yield "data: [DONE]\n\n"

            # 重置所有状态
            self._reset_all_state()

    def _reset_all_state(self):
        """重置所有状态"""
        self.has_tool_call = False
        self.tool_args = ""
        self.tool_id = ""
        self.tool_name = ""
        self.tool_call_usage = None
        self.content_index = 0

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
                                "id": self.tool_id,
                                "type": "function",
                                "function": {"name": self.tool_name, "arguments": ""},
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
                                "id": self.tool_id,
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
            "usage": self.tool_call_usage,
            "model": self.model,
            "object": "chat.completion.chunk",
            "system_fingerprint": "fp_zai_001",
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
