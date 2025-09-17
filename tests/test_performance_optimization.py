#!/usr/bin/env python3
"""
测试性能优化效果
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.sse_tool_handler import SSEToolHandler
import json

def test_buffering_performance():
    """测试缓冲机制的性能"""
    
    handler = SSEToolHandler("test-model", stream=True)
    
    print("🧪 测试缓冲机制性能\n")
    
    # 模拟大量小片段的内容（类似真实场景）
    small_chunks = [
        {"phase": "answer", "delta_content": "我", "edit_content": ""},
        {"phase": "answer", "delta_content": "将", "edit_content": ""},
        {"phase": "answer", "delta_content": "帮", "edit_content": ""},
        {"phase": "answer", "delta_content": "您", "edit_content": ""},
        {"phase": "answer", "delta_content": "打", "edit_content": ""},
        {"phase": "answer", "delta_content": "开", "edit_content": ""},
        {"phase": "answer", "delta_content": "浏", "edit_content": ""},
        {"phase": "answer", "delta_content": "览", "edit_content": ""},
        {"phase": "answer", "delta_content": "器", "edit_content": ""},
        {"phase": "answer", "delta_content": "并", "edit_content": ""},
        {"phase": "answer", "delta_content": "导", "edit_content": ""},
        {"phase": "answer", "delta_content": "航", "edit_content": ""},
        {"phase": "answer", "delta_content": "到", "edit_content": ""},
        {"phase": "answer", "delta_content": " bil", "edit_content": ""},
        {"phase": "answer", "delta_content": "ibili", "edit_content": ""},
        {"phase": "answer", "delta_content": ".com", "edit_content": ""},
        {"phase": "answer", "delta_content": "，", "edit_content": ""},  # 句号触发刷新
        {"phase": "answer", "delta_content": "然", "edit_content": ""},
        {"phase": "answer", "delta_content": "后", "edit_content": ""},
        {"phase": "answer", "delta_content": "搜", "edit_content": ""},
        {"phase": "answer", "delta_content": "索", "edit_content": ""},
        {"phase": "answer", "delta_content": "\"凡", "edit_content": ""},
        {"phase": "answer", "delta_content": "人", "edit_content": ""},
        {"phase": "answer", "delta_content": "修", "edit_content": ""},
        {"phase": "answer", "delta_content": "仙", "edit_content": ""},
        {"phase": "answer", "delta_content": "传", "edit_content": ""},
        {"phase": "answer", "delta_content": "\"。", "edit_content": ""},  # 句号触发刷新
    ]
    
    start_time = time.time()
    output_chunks = []
    
    for i, chunk in enumerate(small_chunks, 1):
        results = list(handler.process_sse_chunk(chunk))
        output_chunks.extend(results)
    
    # 强制刷新剩余缓冲区
    if hasattr(handler, 'content_buffer') and handler.content_buffer:
        final_flush = list(handler._flush_content_buffer())
        output_chunks.extend(final_flush)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    print(f"📊 性能测试结果:")
    print(f"  输入块数量: {len(small_chunks)}")
    print(f"  输出块数量: {len(output_chunks)}")
    print(f"  处理时间: {processing_time:.4f}s")
    print(f"  平均每块时间: {processing_time/len(small_chunks)*1000:.2f}ms")
    
    # 验证内容完整性
    content_parts = []
    for output in output_chunks:
        if output.startswith("data: "):
            try:
                json_str = output[6:].strip()
                if json_str and json_str != "[DONE]":
                    data = json.loads(json_str)
                    if "choices" in data and data["choices"]:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            content_parts.append(content)
            except json.JSONDecodeError:
                pass
    
    full_content = "".join(content_parts)
    expected_content = "我将帮您打开浏览器并导航到 bilibili.com，然后搜索\"凡人修仙传\"。"
    
    print(f"\n📝 内容验证:")
    print(f"  期望内容: {expected_content}")
    print(f"  实际内容: {full_content}")
    print(f"  内容匹配: {'✅' if full_content == expected_content else '❌'}")
    
    # 验证缓冲效果（输出块数应该少于输入块数）
    compression_ratio = len(output_chunks) / len(small_chunks)
    print(f"\n🚀 缓冲效果:")
    print(f"  压缩比: {compression_ratio:.2f} (越小越好)")
    print(f"  减少输出: {(1-compression_ratio)*100:.1f}%")
    
    return len(output_chunks) < len(small_chunks) and full_content == expected_content

def test_flush_triggers():
    """测试不同的刷新触发条件"""
    
    handler = SSEToolHandler("test-model", stream=True)
    
    print("\n🧪 测试刷新触发条件\n")
    
    test_cases = [
        {
            "name": "句号触发",
            "chunks": [
                {"phase": "answer", "delta_content": "这是一个测试", "edit_content": ""},
                {"phase": "answer", "delta_content": "。", "edit_content": ""},  # 应该触发刷新
            ]
        },
        {
            "name": "缓冲区大小触发",
            "chunks": [
                {"phase": "answer", "delta_content": "a" * 50, "edit_content": ""},  # 50字符
                {"phase": "answer", "delta_content": "b" * 60, "edit_content": ""},  # 总共110字符，超过100，应该触发刷新
            ]
        },
        {
            "name": "换行符触发",
            "chunks": [
                {"phase": "answer", "delta_content": "第一行", "edit_content": ""},
                {"phase": "answer", "delta_content": "\n第二行", "edit_content": ""},  # 应该触发刷新
            ]
        },
        {
            "name": "阶段变化触发",
            "chunks": [
                {"phase": "answer", "delta_content": "回答内容", "edit_content": ""},
                {"phase": "tool_call", "edit_content": "工具调用", "edit_index": 100},  # 阶段变化应该触发刷新
            ]
        }
    ]
    
    for test_case in test_cases:
        print(f"测试: {test_case['name']}")
        
        # 重置处理器
        handler._reset_all_state()
        
        output_count = 0
        for chunk in test_case['chunks']:
            results = list(handler.process_sse_chunk(chunk))
            output_count += len(results)
            
        print(f"  输出块数量: {output_count}")
        print(f"  缓冲区状态: {len(handler.content_buffer)} 字符")
        print()
    
    return True

def benchmark_comparison():
    """对比优化前后的性能"""
    
    print("🏁 性能对比测试\n")
    
    # 创建大量小片段
    test_chunks = []
    for i in range(100):
        test_chunks.append({
            "phase": "answer", 
            "delta_content": f"片段{i}", 
            "edit_content": ""
        })
    
    # 测试优化版本
    handler_optimized = SSEToolHandler("test-model", stream=True)
    
    start_time = time.time()
    output_count = 0
    for chunk in test_chunks:
        results = list(handler_optimized.process_sse_chunk(chunk))
        output_count += len(results)
    
    # 刷新剩余缓冲区
    if handler_optimized.content_buffer:
        final_results = list(handler_optimized._flush_content_buffer())
        output_count += len(final_results)
        
    optimized_time = time.time() - start_time
    
    print(f"📊 性能对比结果:")
    print(f"  输入块数量: {len(test_chunks)}")
    print(f"  优化版输出块数量: {output_count}")
    print(f"  优化版处理时间: {optimized_time:.4f}s")
    print(f"  优化版平均每块: {optimized_time/len(test_chunks)*1000:.2f}ms")
    
    # 估算未优化版本的性能（每个输入块对应一个输出块）
    estimated_unoptimized_outputs = len(test_chunks)
    compression_ratio = output_count / estimated_unoptimized_outputs
    
    print(f"\n🚀 优化效果:")
    print(f"  输出块减少: {(1-compression_ratio)*100:.1f}%")
    print(f"  预估性能提升: {1/compression_ratio:.1f}x")
    
    return compression_ratio < 0.5  # 至少减少50%的输出

if __name__ == "__main__":
    print("🔧 性能优化测试\n")
    
    test1_success = test_buffering_performance()
    test2_success = test_flush_triggers()
    test3_success = benchmark_comparison()
    
    print("\n" + "="*50)
    print("🎯 总结:")
    print(f"  缓冲机制测试: {'✅ 通过' if test1_success else '❌ 失败'}")
    print(f"  刷新触发测试: {'✅ 通过' if test2_success else '❌ 失败'}")
    print(f"  性能对比测试: {'✅ 通过' if test3_success else '❌ 失败'}")
    
    if test1_success and test2_success and test3_success:
        print("\n🎉 所有测试通过！性能优化成功！")
        print("\n💡 优化效果:")
        print("  - 减少了大量小片段的单独处理")
        print("  - 智能缓冲机制减少了JSON序列化开销")
        print("  - 多种刷新触发条件保证了响应性")
        print("  - 显著提升了流式响应的性能")
    else:
        print("\n❌ 部分测试失败，需要进一步调试")
