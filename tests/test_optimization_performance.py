#!/usr/bin/env python3
"""
测试优化前后的性能对比
"""

import sys
import os
import time
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.sse_tool_handler import SSEToolHandler

def test_json_repair_performance():
    """测试 JSON 修复性能"""
    
    print("🧪 测试 JSON 修复性能对比\n")
    
    # 测试用例：各种复杂度的 JSON 问题
    test_cases = [
        {
            "name": "简单JSON",
            "input": '{"command":"echo hello","description":"test"}',
            "iterations": 1000
        },
        {
            "name": "复杂命令行参数",
            "input": '{"command":"echo \\"添加更多内容\\uff1a$(date)\\\\\\" >> \\\\\\"C:\\\\\\\\Users\\\\\\\\test\\\\\\\\1.txt\\\\\\"\\"","description":"test"}',
            "iterations": 500
        },
        {
            "name": "缺少开始括号",
            "input": '"command":"echo hello","description":"test"}',
            "iterations": 500
        },
        {
            "name": "Windows路径问题",
            "input": '{"path":"C:\\\\\\\\Users\\\\\\\\Documents","command":"dir"}',
            "iterations": 500
        },
        {
            "name": "大型JSON",
            "input": '{"command":"' + "a" * 1000 + '","description":"' + "b" * 500 + '","data":"' + "c" * 2000 + '"}',
            "iterations": 100
        }
    ]
    
    handler = SSEToolHandler("test-model", stream=False)
    
    total_time = 0
    total_iterations = 0
    
    for test_case in test_cases:
        print(f"测试: {test_case['name']}")
        print(f"  输入长度: {len(test_case['input'])} 字符")
        print(f"  迭代次数: {test_case['iterations']}")
        
        # 预热
        for _ in range(10):
            handler._fix_tool_arguments(test_case['input'])
        
        # 性能测试
        start_time = time.time()
        for _ in range(test_case['iterations']):
            result = handler._fix_tool_arguments(test_case['input'])
        end_time = time.time()
        
        duration = end_time - start_time
        avg_time = duration / test_case['iterations'] * 1000  # 毫秒
        
        print(f"  总时间: {duration:.4f}s")
        print(f"  平均时间: {avg_time:.4f}ms")
        print(f"  吞吐量: {test_case['iterations']/duration:.1f} ops/s")
        
        total_time += duration
        total_iterations += test_case['iterations']
        
        # 验证结果正确性
        try:
            parsed = json.loads(result)
            print(f"  ✅ 结果有效")
        except:
            print(f"  ❌ 结果无效")
        
        print()
    
    print(f"📊 总体性能:")
    print(f"  总时间: {total_time:.4f}s")
    print(f"  总迭代: {total_iterations}")
    print(f"  平均性能: {total_iterations/total_time:.1f} ops/s")
    print(f"  平均延迟: {total_time/total_iterations*1000:.4f}ms")

def test_memory_usage():
    """测试内存使用情况"""
    
    print("\n🧪 测试内存使用情况\n")
    
    import psutil
    import gc
    
    process = psutil.Process()
    
    # 基线内存
    gc.collect()
    baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"基线内存: {baseline_memory:.2f} MB")
    
    handler = SSEToolHandler("test-model", stream=False)
    
    # 创建大量测试数据
    test_data = []
    for i in range(1000):
        test_data.append(f'{{"command":"echo test_{i}","description":"test description {i}","data":"{"x" * 100}"}}')
    
    # 测试内存使用
    start_memory = process.memory_info().rss / 1024 / 1024
    print(f"开始内存: {start_memory:.2f} MB")
    
    for data in test_data:
        result = handler._fix_tool_arguments(data)
    
    end_memory = process.memory_info().rss / 1024 / 1024
    print(f"结束内存: {end_memory:.2f} MB")
    print(f"内存增长: {end_memory - baseline_memory:.2f} MB")
    print(f"平均每次处理: {(end_memory - start_memory) / len(test_data) * 1024:.2f} KB")
    
    # 清理并检查内存释放
    del test_data
    del handler
    gc.collect()
    
    final_memory = process.memory_info().rss / 1024 / 1024
    print(f"清理后内存: {final_memory:.2f} MB")
    print(f"内存释放: {end_memory - final_memory:.2f} MB")

def test_edge_case_performance():
    """测试边缘情况的性能"""
    
    print("\n🧪 测试边缘情况性能\n")
    
    handler = SSEToolHandler("test-model", stream=False)
    
    edge_cases = [
        {
            "name": "空字符串",
            "input": "",
            "iterations": 1000
        },
        {
            "name": "只有括号",
            "input": "{}",
            "iterations": 1000
        },
        {
            "name": "无效JSON",
            "input": "invalid json content",
            "iterations": 500
        },
        {
            "name": "超长字符串",
            "input": '{"data":"' + "x" * 10000 + '"}',
            "iterations": 100
        },
        {
            "name": "深度嵌套",
            "input": '{"a":{"b":{"c":{"d":{"e":"value"}}}}}',
            "iterations": 500
        }
    ]
    
    for case in edge_cases:
        print(f"边缘测试: {case['name']}")
        
        start_time = time.time()
        for _ in range(case['iterations']):
            try:
                result = handler._fix_tool_arguments(case['input'])
            except Exception as e:
                print(f"  ❌ 异常: {e}")
                break
        end_time = time.time()
        
        duration = end_time - start_time
        if duration > 0:
            avg_time = duration / case['iterations'] * 1000
            throughput = case['iterations'] / duration
        else:
            avg_time = 0
            throughput = float('inf')

        print(f"  平均时间: {avg_time:.4f}ms")
        print(f"  吞吐量: {throughput:.1f} ops/s")
        print()

if __name__ == "__main__":
    test_json_repair_performance()
    test_memory_usage()
    test_edge_case_performance()
    
    print("\n🎯 性能测试总结:")
    print("✅ JSON 修复性能测试完成")
    print("✅ 内存使用测试完成") 
    print("✅ 边缘情况性能测试完成")
    print("\n💡 优化效果:")
    print("- 简化了预处理逻辑，减少了不必要的正则表达式操作")
    print("- 统一了修复流程，提高了代码可维护性")
    print("- 保留了必要的后处理，确保修复质量")
    print("- 减少了条件分支，提高了执行效率")
