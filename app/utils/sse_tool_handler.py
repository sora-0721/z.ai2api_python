#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SSE Tool Handler
基于 Z.AI 原生的 edit_index 和 edit_content 机制
"""

import json
import re
import time
from typing import Dict, Any, Optional, Generator

from app.utils.logger import get_logger

logger = get_logger()


class SSEToolHandler:
    """SSE 工具调用处理器"""

    def __init__(self, chat_id: str, model: str):
        self.chat_id = chat_id
        self.model = model

        # 核心状态
        self.has_tool_call = False
        self.tool_call_usage = None
        self.content_buffer = ""

        # 工具状态跟踪
        self.sent_tools = set()  # 已发送的工具ID，避免重复发送

    def process_tool_call_phase(self, data: Dict[str, Any], is_stream: bool = True) -> Generator[str, None, None]:
        """处理 tool_call 阶段"""
        if not self.has_tool_call:
            self.has_tool_call = True
            logger.debug("🔧 进入工具调用阶段")

        edit_content = data.get("edit_content", "")
        edit_index = data.get("edit_index", 0)

        if not edit_content:
            return

        # 更新内容缓冲区
        self._update_content_buffer(edit_index, edit_content)

        # 解析并发送工具调用
        if is_stream:
            yield from self._extract_and_send_tools()

    def _update_content_buffer(self, edit_index: int, edit_content: str):
        """更新内容缓冲区"""
        # 确保缓冲区足够长
        required_length = edit_index + len(edit_content)
        if len(self.content_buffer) < required_length:
            self.content_buffer += " " * (required_length - len(self.content_buffer))

        # 替换指定位置的内容
        self.content_buffer = (
            self.content_buffer[:edit_index] +
            edit_content +
            self.content_buffer[edit_index + len(edit_content):]
        )

    def _extract_and_send_tools(self) -> Generator[str, None, None]:
        """从缓冲区提取并发送工具调用"""
        # 查找所有完整的 glm_block
        pattern = r'<glm_block\s*>(.*?)</glm_block>'
        matches = re.findall(pattern, self.content_buffer, re.DOTALL)

        for block_content in matches:
            yield from self._process_tool_block(block_content)

    def _process_tool_block(self, block_content: str) -> Generator[str, None, None]:
        """处理单个工具块"""
        try:
            # 清理和修复 JSON 内容
            cleaned_content = self._clean_json_content(block_content)
            tool_data = json.loads(cleaned_content)
            metadata = tool_data.get("data", {}).get("metadata", {})

            tool_id = metadata.get("id", "")
            tool_name = metadata.get("name", "")
            arguments_str = metadata.get("arguments", "{}")

            if not tool_id or not tool_name or tool_id in self.sent_tools:
                return

            # 解析参数
            try:
                if isinstance(arguments_str, str):
                    # 处理转义的 JSON 字符串
                    cleaned_args = arguments_str.replace('\\"', '"')
                    arguments = json.loads(cleaned_args)
                else:
                    arguments = arguments_str
            except json.JSONDecodeError:
                arguments = {}

            # 发送工具调用
            logger.debug(f"🎯 发送工具调用: {tool_name}(id={tool_id})")
            yield self._create_tool_chunk(tool_id, tool_name, arguments)
            self.sent_tools.add(tool_id)

        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"📦 工具块解析失败: {e}")

    def _clean_json_content(self, content: str) -> str:
        """清理 JSON 内容，处理常见的格式问题"""
        if not content:
            return content

        # 移除可能的前缀空格
        content = content.strip()

        # 如果内容不是以 { 开头，尝试找到第一个 {
        if not content.startswith('{'):
            start_pos = content.find('{')
            if start_pos != -1:
                content = content[start_pos:]

        # 如果内容不是以 } 结尾，尝试找到最后一个 }
        if not content.endswith('}'):
            end_pos = content.rfind('}')
            if end_pos != -1:
                content = content[:end_pos + 1]

        # 尝试修复常见的转义问题
        try:
            # 先尝试直接解析
            json.loads(content)
            return content
        except json.JSONDecodeError:
            # 如果失败，尝试修复转义
            # 将 \\" 替换为 " 但要小心不要破坏正确的转义
            import re
            # 使用更安全的方法处理转义
            fixed_content = re.sub(r'\\+"', '"', content)
            try:
                json.loads(fixed_content)
                return fixed_content
            except json.JSONDecodeError:
                # 如果还是失败，返回原内容
                return content





    def process_other_phase(self, data: Dict[str, Any], is_stream: bool = True) -> Generator[str, None, None]:
        """处理 other 阶段"""
        edit_content = data.get("edit_content", "")
        edit_index = data.get("edit_index", 0)
        usage = data.get("usage")

        # 保存 usage 信息
        if self.has_tool_call and usage:
            self.tool_call_usage = usage
            logger.debug(f"💾 保存工具调用usage: {usage}")

        # 继续更新内容缓冲区（可能有更多工具调用）
        if edit_content:
            self._update_content_buffer(edit_index, edit_content)
            if is_stream:
                yield from self._extract_and_send_tools()

        # 检测工具调用结束
        if self.has_tool_call and self._is_tool_call_finished(edit_content, usage):
            logger.debug("🏁 检测到工具调用结束")

            if is_stream:
                # 发送工具完成信号
                yield self._create_tool_finish_chunk()
                yield "data: [DONE]"

            # 重置状态
            self._reset_state()

    def _is_tool_call_finished(self, edit_content: str, usage: Optional[Dict] = None) -> bool:
        """检测工具调用是否结束"""
        if not edit_content and usage:
            # 如果只有 usage 没有 edit_content，通常表示结束
            return True

        # 检测结束标记
        end_markers = [
            '"status": "completed"',
            '"is_error": false',
            "null,",
        ]

        return any(marker in edit_content for marker in end_markers)

    def _reset_state(self):
        """重置所有状态"""
        self.has_tool_call = False
        self.tool_call_usage = None
        self.content_buffer = ""
        self.sent_tools.clear()

    def _create_tool_chunk(self, tool_id: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """创建工具调用块"""
        chunk = {
            "choices": [{
                "delta": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(arguments, ensure_ascii=False)
                        }
                    }]
                },
                "finish_reason": None,
                "index": 0,
                "logprobs": None
            }],
            "created": int(time.time()),
            "id": self.chat_id,
            "model": self.model,
            "object": "chat.completion.chunk",
            "system_fingerprint": "fp_zai_001"
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    def _create_tool_finish_chunk(self) -> str:
        """创建工具完成块"""
        chunk = {
            "choices": [{
                "delta": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": []
                },
                "finish_reason": "tool_calls",
                "index": 0,
                "logprobs": None
            }],
            "created": int(time.time()),
            "id": self.chat_id,
            "model": self.model,
            "object": "chat.completion.chunk",
            "usage": self.tool_call_usage,
            "system_fingerprint": "fp_zai_001"
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


