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
    DONE = "done"


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
        self.content_index = 0  # 工具调用索引

        # 性能优化：内容缓冲
        self.content_buffer = ""
        self.buffer_size = 0
        self.last_flush_time = time.time()
        self.flush_interval = 0.05  # 50ms 刷新间隔
        self.max_buffer_size = 100  # 最大缓冲字符数

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
                # 阶段变化时强制刷新缓冲区
                if hasattr(self, 'content_buffer') and self.content_buffer:
                    yield from self._flush_content_buffer()

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
                yield from self._process_other_phase(usage, edit_content)

            elif phase == SSEPhase.ANSWER.value:
                yield from self._process_answer_phase(delta_content)

            elif phase == SSEPhase.DONE.value:
                yield from self._process_done_phase(chunk_data)
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
        else:
            # 没有 glm_block 标记，可能是参数补充
            if self.has_tool_call:
                # 只累积参数部分，找到第一个 ", "result"" 之前的内容
                result_pos = edit_content.find('", "result"')
                if result_pos > 0:
                    param_fragment = edit_content[:result_pos]
                    self.tool_args += param_fragment
                    logger.debug(f"📦 累积参数片段: {param_fragment}")
                else:
                    # 如果没有找到结束标记，累积整个内容（可能是中间片段）
                    self.tool_args += edit_content
                    logger.debug(f"📦 累积参数片段: {edit_content[:100]}...")

    def _handle_glm_blocks(self, edit_content: str) -> Generator[str, None, None]:
        """处理 glm_block 标记的内容"""
        blocks = edit_content.split('<glm_block ')
        logger.debug(f"📦 分割得到 {len(blocks)} 个块")

        for index, block in enumerate(blocks):
            if not block.strip():
                continue

            if index == 0:
                # 第一个块：提取参数片段
                if self.has_tool_call:
                    logger.debug(f"📦 从第一个块提取参数片段")
                    # 找到 "result" 的位置，提取之前的参数片段
                    result_pos = edit_content.find('"result"')
                    if result_pos > 0:
                        # 往前退3个字符去掉 ", "
                        param_fragment = edit_content[:result_pos - 3]
                        self.tool_args += param_fragment
                        logger.debug(f"📦 累积参数片段: {param_fragment}")
                else:
                    # 没有活跃工具调用，跳过第一个块
                    continue
            else:
                # 后续块：处理新工具调用
                if "</glm_block>" not in block:
                    continue

                # 如果有活跃的工具调用，先完成它
                if self.has_tool_call:
                    # 补全参数并完成工具调用
                    self.tool_args += '"'  # 补全最后的引号
                    yield from self._finish_current_tool()

                # 处理新工具调用
                yield from self._process_metadata_block(block)

    def _process_metadata_block(self, block: str) -> Generator[str, None, None]:
        """处理包含工具元数据的块"""
        try:
            # 提取 JSON 内容
            start_pos = block.find('>')
            end_pos = block.rfind('</glm_block>')

            if start_pos == -1 or end_pos == -1:
                logger.warning(f"❌ 无法找到 JSON 内容边界: {block[:1000]}...")
                return

            json_content = block[start_pos + 1:end_pos]
            logger.debug(f"📦 提取的 JSON 内容: {json_content[:1000]}...")

            # 解析工具元数据
            metadata_obj = json.loads(json_content)

            if "data" in metadata_obj and "metadata" in metadata_obj["data"]:
                metadata = metadata_obj["data"]["metadata"]

                # 开始新的工具调用
                self.tool_id = metadata.get("id", f"call_{int(time.time() * 1000000)}")
                self.tool_name = metadata.get("name", "unknown")
                self.has_tool_call = True

                # 只有在这是第二个及以后的工具调用时才递增 index
                # 第一个工具调用应该使用 index 0

                # 从 metadata.arguments 获取参数起始部分
                if "arguments" in metadata:
                    arguments_str = metadata["arguments"]
                    # 去掉最后一个字符
                    self.tool_args = arguments_str[:-1] if arguments_str.endswith('"') else arguments_str
                    logger.debug(f"🎯 新工具调用: {self.tool_name}(id={self.tool_id}), 初始参数: {self.tool_args}")
                else:
                    self.tool_args = "{}"
                    logger.debug(f"🎯 新工具调用: {self.tool_name}(id={self.tool_id}), 空参数")

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"❌ 解析工具元数据失败: {e}, 块内容: {block[:1000]}...")

        # 确保返回生成器（即使为空）
        if False:  # 永远不会执行，但确保函数是生成器
            yield

    def _process_other_phase(self, usage: Dict[str, Any], edit_content: str = "") -> Generator[str, None, None]:
        """处理其他阶段"""
        # 保存使用统计信息
        if usage:
            self.tool_call_usage = usage
            logger.debug(f"📊 保存使用统计: {usage}")

        # 工具调用完成判断：检测到 "null," 开头的 edit_content
        if self.has_tool_call and edit_content and edit_content.startswith("null,"):
            logger.info(f"🏁 检测到工具调用结束标记")

            # 完成当前工具调用
            yield from self._finish_current_tool()

            # 发送流结束标记
            if self.stream:
                yield "data: [DONE]\n\n"

            # 重置状态
            self._reset_all_state()

    def _process_answer_phase(self, edit_content: str) -> Generator[str, None, None]:
        """处理回答阶段（优化版本）"""
        if not edit_content:
            return

        # 添加到缓冲区
        self.content_buffer += edit_content
        self.buffer_size += len(edit_content)

        current_time = time.time()
        time_since_last_flush = current_time - self.last_flush_time

        # 检查是否需要刷新缓冲区
        should_flush = (
            self.buffer_size >= self.max_buffer_size or  # 缓冲区满了
            time_since_last_flush >= self.flush_interval or  # 时间间隔到了
            '\n' in edit_content or  # 包含换行符
            '。' in edit_content or '！' in edit_content or '？' in edit_content  # 包含句子结束符
        )

        if should_flush and self.content_buffer:
            yield from self._flush_content_buffer()

    def _flush_content_buffer(self) -> Generator[str, None, None]:
        """刷新内容缓冲区"""
        if not self.content_buffer:
            return

        logger.debug(f"💬 刷新缓冲区: {self.buffer_size} 字符")

        if self.stream:
            chunk = self._create_content_chunk(self.content_buffer)
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        # 清空缓冲区
        self.content_buffer = ""
        self.buffer_size = 0
        self.last_flush_time = time.time()

    def _process_done_phase(self, chunk_data: Dict[str, Any]) -> Generator[str, None, None]:
        """处理完成阶段"""
        logger.info("🏁 对话完成")

        # 先刷新任何剩余的缓冲内容
        if self.content_buffer:
            yield from self._flush_content_buffer()

        # 完成任何未完成的工具调用
        if self.has_tool_call:
            yield from self._finish_current_tool()

        # 发送流结束标记
        if self.stream:
            # 创建最终的完成块
            final_chunk = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": self.model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }

            # 如果有 usage 信息，添加到最终块中
            if "usage" in chunk_data:
                final_chunk["usage"] = chunk_data["usage"]

            yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        # 重置所有状态
        self._reset_all_state()

    def _finish_current_tool(self) -> Generator[str, None, None]:
        """完成当前工具调用"""
        if not self.has_tool_call:
            return

        # 修复参数格式
        fixed_args = self._fix_tool_arguments(self.tool_args)
        logger.debug(f"✅ 完成工具调用: {self.tool_name}, 参数: {fixed_args}")

        # 输出工具调用（开始 + 参数 + 完成）
        if self.stream:
            # 发送工具开始块
            start_chunk = self._create_tool_start_chunk()
            yield f"data: {json.dumps(start_chunk, ensure_ascii=False)}\n\n"

            # 发送参数块
            args_chunk = self._create_tool_arguments_chunk(fixed_args)
            yield f"data: {json.dumps(args_chunk, ensure_ascii=False)}\n\n"

            # 发送完成块
            finish_chunk = self._create_tool_finish_chunk()
            yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"

        # 重置工具状态
        self._reset_tool_state()

    def _fix_tool_arguments(self, raw_args: str) -> str:
        """使用 json-repair 库修复工具参数格式"""
        if not raw_args or raw_args == "{}":
            return "{}"

        logger.debug(f"🔧 开始修复参数: {raw_args[:1000]}{'...' if len(raw_args) > 1000 else ''}")

        # 尝试直接解析
        try:
            args_obj = json.loads(raw_args)
            result = json.dumps(args_obj, ensure_ascii=False)
            logger.debug(f"✅ 参数无需修复: {result}")
            return result
        except json.JSONDecodeError:
            pass

        # 预处理：提取纯 JSON 部分和修复转义引号
        processed_args = self._preprocess_json_string(raw_args.strip())

        # 使用 json-repair 库进行修复
        from json_repair import repair_json

        try:
            repaired_json = repair_json(processed_args)
            logger.debug(f"🔧 json-repair 修复结果: {repaired_json}")

            # 验证修复结果
            args_obj = json.loads(repaired_json)
            fixed_result = json.dumps(args_obj, ensure_ascii=False)

            # 记录修复前后对比
            logger.info(f"✅ JSON 修复成功:")
            logger.info(f"   修复前: {raw_args[:1000]}{'...' if len(raw_args) > 1000 else ''}")
            logger.info(f"   修复后: {fixed_result}")

            return fixed_result

        except Exception as e:
            logger.error(f"❌ JSON 修复失败: {e}, 原始参数: {raw_args[:1000]}..., 使用空参数")
            return "{}"

    def _preprocess_json_string(self, text: str) -> str:
        """预处理 JSON 字符串，修复转义引号和提取纯 JSON 部分"""
        import re

        # 1. 如果包含额外内容（如 "result" 字段），提取纯 JSON 部分
        if '"result"' in text:
            brace_count = 0
            json_end = -1
            for i, char in enumerate(text):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break

            if json_end > 0:
                text = text[:json_end]
                logger.debug(f"🔧 提取纯 JSON 部分: {text[:1000]}...")

        # 2. 修复缺少开始括号的情况
        if not text.startswith('{') and text.endswith('}'):
            text = '{' + text
            logger.debug(f"🔧 补全开始括号")

        # 3. 修复转义引号问题
        # 处理 "key:\"value\"," 模式 -> "key":"value",
        pattern = r'(["\w]+):\\"([^"\\]*)\\"'
        if re.search(pattern, text):
            text = re.sub(pattern, r'\1:"\2"', text)
            logger.debug(f"🔧 修复字段转义引号模式")

        # 处理剩余的转义引号 \" -> "
        if '\\"' in text:
            text = text.replace('\\"', '"')
            logger.debug(f"🔧 替换剩余转义引号")

        return text

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
                        "index": self.content_index,
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
                        "index": self.content_index,
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
        # content_index 在单次对话中应该保持不变，只有在新的工具调用开始时才递增

    def _reset_all_state(self):
        """重置所有状态"""
        # 先刷新任何剩余的缓冲内容
        if hasattr(self, 'content_buffer') and self.content_buffer:
            list(self._flush_content_buffer())  # 消费生成器

        self._reset_tool_state()
        self.current_phase = None
        self.tool_call_usage = {}

        # 重置缓冲区
        self.content_buffer = ""
        self.buffer_size = 0
        self.last_flush_time = time.time()

        # content_index 重置为 0，为下一轮对话做准备
        self.content_index = 0
        logger.debug("🔄 重置所有处理器状态")
