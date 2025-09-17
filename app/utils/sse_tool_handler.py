#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SSE Tool Handler
"""

import json
import re
import time
from typing import Dict, Any, Optional, List

from app.utils.logger import get_logger

logger = get_logger()

# 工具调用提取模式
TOOL_CALL_FENCE_PATTERN = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
TOOL_CALL_INLINE_PATTERN = re.compile(r"(\{[^{}]{0,10000}\"tool_calls\".*?\})", re.DOTALL)
FUNCTION_CALL_PATTERN = re.compile(r"调用函数\s*[：:]\s*([\w\-\.]+)\s*(?:参数|arguments)[：:]\s*(\{.*?\})", re.DOTALL)
GLM_BLOCK_PATTERN = re.compile(r"<glm_block[^>]*>(\{.*?\})</glm_block>", re.DOTALL)

# 扫描限制（性能优化）
SCAN_LIMIT = 200000


def extract_tool_invocations(text: str) -> Optional[List[Dict[str, Any]]]:
    """提取工具调用"""
    if not text:
        return None

    # 限制扫描大小以提高性能
    scannable_text = text[:SCAN_LIMIT]

    # 方法1: 从 glm_block 标签中提取（Z.AI 新格式）
    glm_blocks = GLM_BLOCK_PATTERN.findall(scannable_text)
    for glm_block in glm_blocks:
        try:
            parsed_data = json.loads(glm_block)
            if parsed_data.get("type") == "mcp" and "data" in parsed_data:
                metadata = parsed_data["data"].get("metadata", {})
                if "id" in metadata and "name" in metadata:
                    # 转换为 OpenAI tool_calls 格式
                    tool_call = {
                        "id": metadata["id"],
                        "type": "function",
                        "function": {
                            "name": metadata["name"],
                            "arguments": metadata.get("arguments", "{}")
                        }
                    }
                    return [tool_call]
        except (json.JSONDecodeError, AttributeError, KeyError):
            continue

    # 方法2: 从JSON代码块中提取
    json_blocks = TOOL_CALL_FENCE_PATTERN.findall(scannable_text)
    for json_block in json_blocks:
        try:
            parsed_data = json.loads(json_block)
            tool_calls = parsed_data.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                return tool_calls
        except (json.JSONDecodeError, AttributeError):
            continue

    # 方法3: 使用平衡括号算法提取内联JSON对象
    tool_calls_pos = scannable_text.find('"tool_calls"')
    if tool_calls_pos != -1:
        # 从 "tool_calls" 位置向前查找最近的 '{'
        start_pos = -1
        for i in range(tool_calls_pos, -1, -1):
            if scannable_text[i] == '{':
                start_pos = i
                break

        if start_pos != -1:
            # 使用平衡括号算法找到匹配的 '}'
            bracket_count = 0
            end_pos = -1

            for i in range(start_pos, len(scannable_text)):
                if scannable_text[i] == '{':
                    bracket_count += 1
                elif scannable_text[i] == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_pos = i
                        break

            if end_pos != -1:
                # 提取JSON字符串并解析
                json_str = scannable_text[start_pos:end_pos + 1]
                try:
                    parsed_data = json.loads(json_str)
                    tool_calls = parsed_data.get("tool_calls")
                    if tool_calls and isinstance(tool_calls, list):
                        return tool_calls
                except json.JSONDecodeError:
                    pass

    # 方法4: 解析自然语言函数调用
    natural_lang_match = FUNCTION_CALL_PATTERN.search(scannable_text)
    if natural_lang_match:
        function_name = natural_lang_match.group(1).strip()
        arguments_str = natural_lang_match.group(2).strip()
        try:
            # 验证JSON格式
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
    """移除工具JSON内容"""
    def remove_tool_call_block(match: re.Match) -> str:
        json_content = match.group(1)
        try:
            parsed_data = json.loads(json_content)
            if "tool_calls" in parsed_data:
                return ""
        except (json.JSONDecodeError, AttributeError):
            pass
        return match.group(0)

    # 移除 glm_block 标签（Z.AI 新格式）
    cleaned_text = GLM_BLOCK_PATTERN.sub("", text)
    # 移除围栏式工具JSON块
    cleaned_text = TOOL_CALL_FENCE_PATTERN.sub(remove_tool_call_block, cleaned_text)
    # 移除内联工具JSON
    cleaned_text = TOOL_CALL_INLINE_PATTERN.sub("", cleaned_text)
    return cleaned_text.strip()


class SSEToolHandler:
    """SSE 工具调用处理器"""

    def __init__(self, model: str):
        self.model = model
        self.buffered_content = ""
        self.tool_calls = None

    def buffer_content(self, content: str):
        """缓冲内容"""
        if content:
            self.buffered_content += content
            logger.debug(f"📦 缓冲内容: +{len(content)} 字符，总计: {len(self.buffered_content)}")

    def extract_tools_at_end(self) -> Optional[List[Dict[str, Any]]]:
        """在流结束时提取工具调用"""
        if not self.buffered_content:
            return None

        logger.debug(f"📦 开始提取工具调用，内容长度: {len(self.buffered_content)}")
        self.tool_calls = extract_tool_invocations(self.buffered_content)

        if self.tool_calls:
            logger.info(f"🎯 提取到 {len(self.tool_calls)} 个工具调用")
        else:
            logger.debug("📦 未找到工具调用")

        return self.tool_calls

    def get_cleaned_content(self) -> str:
        """获取清理后的内容（移除工具JSON）"""
        if not self.buffered_content:
            return ""
        return remove_tool_json_content(self.buffered_content)

    def has_tools(self) -> bool:
        """是否有工具调用"""
        return self.tool_calls is not None and len(self.tool_calls) > 0


