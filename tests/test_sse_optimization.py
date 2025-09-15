#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试 SSE 工具调用处理器的优化效果
"""

import json
import time
from app.utils.sse_tool_handler import SSEToolHandler
from app.utils.logger import get_logger

logger = get_logger()

def test_tool_call_processing():
    """测试工具调用处理的优化效果"""
    
    # 创建处理器
    handler = SSEToolHandler("test_chat_id", "GLM-4.5")
    
    # 模拟 Z.AI 的原始响应数据（基于文档中的示例）
    test_data_sequence = [
        # 第一个数据块 - 工具调用开始
        {
            "edit_index": 22,
            "edit_content": '\n\n<glm_block >{"type": "mcp", "data": {"metadata": {"id": "call_fyh97tn03ow", "name": "playwri-browser_navigate", "arguments": "{\\"url\\":\\"https://www.goo',
            "phase": "tool_call"
        },
        # 第二个数据块 - 参数补全
        {
            "edit_index": 176,
            "edit_content": 'gle.com\\"}", "result": "", "display_result": "", "duration": "...", "status": "completed", "is_error": false, "mcp_server": {"name": "mcp-server"}}, "thought": null, "ppt": null, "browser": null}}</glm_block>',
            "phase": "tool_call"
        },
        # 第三个数据块 - 工具调用结束
        {
            "edit_index": 199,
            "edit_content": 'null, "display_result": "", "duration": "...", "status": "completed", "is_error": false, "mcp_server": {"name": "mcp-server"}}, "thought": null, "ppt": null, "browser": null}}</glm_block>',
            "phase": "other"
        }
    ]
    
    print("🧪 开始测试 SSE 工具调用处理器优化...")
    
    # 处理数据序列
    all_chunks = []
    for i, data in enumerate(test_data_sequence):
        print(f"\n📦 处理数据块 {i+1}: phase={data['phase']}, edit_index={data['edit_index']}")
        
        if data["phase"] == "tool_call":
            chunks = list(handler.process_tool_call_phase(data, is_stream=True))
        else:
            chunks = list(handler.process_other_phase(data, is_stream=True))
        
        all_chunks.extend(chunks)
        
        # 打印生成的块
        for j, chunk in enumerate(chunks):
            if chunk.strip():
                print(f"  📤 输出块 {j+1}: {chunk[:100]}...")
    
    print(f"\n✅ 测试完成，共生成 {len(all_chunks)} 个输出块")
    
    # 验证工具调用是否正确解析
    print(f"🔧 活跃工具数: {len(handler.active_tools)}")
    print(f"✅ 完成工具数: {len(handler.completed_tools)}")
    
    # 打印最终的内容缓冲区
    try:
        final_content = handler.content_buffer.decode('utf-8', errors='ignore')
        print(f"\n📝 最终内容缓冲区长度: {len(final_content)}")
        print(f"📝 内容预览: {final_content[:200]}...")
    except Exception as e:
        print(f"❌ 内容缓冲区解析失败: {e}")

def test_partial_arguments_parsing():
    """测试部分参数解析功能"""
    
    handler = SSEToolHandler("test_chat_id", "GLM-4.5")
    
    # 测试各种不完整的参数
    test_cases = [
        '{"url":"https://www.goo',  # 不完整的URL
        '{"city":"北京',  # 缺少引号和括号
        '{"query":"test", "limit":',  # 不完整的数值
        '{"name":"test"',  # 缺少结束括号
        '',  # 空字符串
        '{',  # 只有开始括号
    ]
    
    print("\n🧪 测试部分参数解析...")
    
    for i, test_arg in enumerate(test_cases):
        print(f"\n📦 测试用例 {i+1}: {test_arg}")
        result = handler._parse_partial_arguments(test_arg)
        print(f"  ✅ 解析结果: {result}")

def test_performance():
    """测试性能优化效果"""
    
    print("\n🚀 测试性能优化效果...")
    
    # 创建大量数据进行性能测试
    handler = SSEToolHandler("test_chat_id", "GLM-4.5")
    
    # 模拟大量的编辑操作
    start_time = time.time()
    
    for i in range(1000):
        edit_data = {
            "edit_index": i * 10,
            "edit_content": f"test_content_{i}",
            "phase": "tool_call"
        }
        list(handler.process_tool_call_phase(edit_data, is_stream=False))
    
    end_time = time.time()
    
    print(f"⏱️ 处理1000次编辑操作耗时: {end_time - start_time:.3f}秒")
    print(f"📊 平均每次操作耗时: {(end_time - start_time) * 1000 / 1000:.3f}毫秒")

if __name__ == "__main__":
    try:
        test_tool_call_processing()
        test_partial_arguments_parsing()
        test_performance()
        print("\n🎉 所有测试完成！")
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
